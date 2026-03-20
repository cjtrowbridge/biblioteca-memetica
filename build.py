#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shutil
import re
import sys
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import escape
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import markdown as markdown_lib
except ImportError:
    markdown_lib = None

TRACKED_EXTS = {".gif", ".jfif", ".jpeg", ".jpg", ".mp4", ".png", ".svg", ".webp", ".avif", ".bmp", ".mov", ".m4v", ".webm"}
IMAGE_EXTS = {".avif", ".bmp", ".gif", ".jfif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
VIDEO_EXTS = {".m4v", ".mov", ".mp4", ".webm"}
INCLUDE_PATTERN = re.compile(r"{%\s*include\s+'([^']+)'\s*%}")
DEFAULT_SETTINGS_FILE = "settings.local.json"
AI_KIND_SIMPLE = "simple-description"
AI_KIND_DETAILED = "detailed-analysis"
LEGACY_SIMPLE_LABELS = {"llama3.2-vision", "llama-3.2-vision", "qwen2.5vl", "vision", "qwen3.5-9b"}
LEGACY_DETAILED_LABELS = {"gemma3-27b-vision"}
SIMPLE_PROMPT = "Category context: {category}. Explain the meme from the perspective of this category (for example, an Anti-Elon meme should be described as criticism of Elon). In 2-3 sentences, describe this meme for someone who cannot see it. Include any text that appears in the image."
DETAILED_PROMPT = (
    "Category context: {category}. Explain this meme from the perspective of this category (for example, an Anti-Elon meme should be interpreted as criticism of Elon). "
    "Describe this in several sections with headings on the following topics (only if each topic applies): "
    "Visual Description, Foucauldian Genealogical Discourse Analysis, Critical Theory, Marxist Conflict Theory, "
    "Postmodernism, Queer Feminist Intersectional Analysis."
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "site": {"name": "Biblioteca Memetica", "url": "https://bibliotecamemetica.com"},
    "paths": {"memes_root": "memes", "layouts_dir": "_layout", "includes_dir": "_includes", "catalog_path": "memes.json"},
    "build": {"page_size": 30, "new_days": 14},
    "ai": {
        "enabled": False,
        "url": "http://xavier:11434/api/generate",
        "timeout_seconds": 300,
        "retries": 3,
        "retry_backoff_seconds": 2,
        "analyses": {
            "simple": {
                "enabled": True,
                "analysis_type": AI_KIND_SIMPLE,
                "model": "gemma3:27b-it-q8_0",
                "prompt": SIMPLE_PROMPT,
                "timeout_seconds": 300,
            },
            "detailed": {
                "enabled": True,
                "analysis_type": AI_KIND_DETAILED,
                "model": "gemma3:27b-it-q8_0",
                "prompt": DETAILED_PROMPT,
                "timeout_seconds": 600,
            },
        },
    },
}


@dataclass
class MetadataArtifact:
    label: str
    path: Path
    text: str
    mtime_dt: datetime
    render_markdown: bool = False
    kind: str = "other"


@dataclass
class Asset:
    topic: str
    abs_path: Path
    rel_path: Path
    first_seen: str
    first_seen_dt: datetime
    first_seen_path: Path | None
    simple_path: Path | None = None
    simple_text: str = ""
    simple_label: str = ""
    ocr_path: Path | None = None
    ocr_text: str = ""
    metadata_artifacts: list[MetadataArtifact] = field(default_factory=list)

    @property
    def rel_html_path(self) -> Path:
        return self.rel_path.parent / f"{self.rel_path.name}.html"


class TeeWriter:
    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            try:
                stream.write(data)
            except UnicodeEncodeError:
                encoding = getattr(stream, "encoding", None) or "utf-8"
                safe_data = data.encode(encoding, errors="replace").decode(encoding, errors="replace")
                stream.write(safe_data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def isatty(self) -> bool:
        return any(getattr(stream, "isatty", lambda: False)() for stream in self.streams)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build static meme pages from local meme folders.")
    p.add_argument("--settings-file", default=DEFAULT_SETTINGS_FILE)
    p.add_argument("--log-file", default="build.log")
    p.add_argument("--non-interactive", action="store_true")
    p.add_argument("--summaries", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--jekyll", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--page-size", type=int, default=None)
    p.add_argument("--max-topics", type=int, default=None, help="Limit AI summary generation to first N topics (site rendering still uses all topics).")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def setup_run_logging(repo_root: Path, raw_log_file: str) -> Callable[[int], None]:
    log_path = Path(str(raw_log_file).strip() or "build.log")
    if not log_path.is_absolute():
        log_path = repo_root / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_handle = log_path.open("a", encoding="utf-8", buffering=1)

    tee_stdout = TeeWriter(original_stdout, log_handle)
    tee_stderr = TeeWriter(original_stderr, log_handle)
    sys.stdout = tee_stdout
    sys.stderr = tee_stderr

    start_wall = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    print("=" * 80)
    print(f"Build started: {start_wall.isoformat()}")
    print(f"Command: {' '.join(sys.argv)}")
    print(f"Working directory: {Path.cwd()}")
    print(f"Log file: {log_path}")
    print("-" * 80)

    def finalize(exit_code: int) -> None:
        finish_wall = datetime.now(timezone.utc)
        duration = time.perf_counter() - start_perf
        status = "success" if exit_code == 0 else f"failure ({exit_code})"
        print("-" * 80)
        print(f"Build finished: {finish_wall.isoformat()} | duration_seconds={duration:.2f} | status={status}")
        print("=" * 80)
        try:
            tee_stdout.flush()
            tee_stderr.flush()
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            log_handle.close()

    return finalize


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def prompt_text(prompt: str, default: str, non_interactive: bool) -> str:
    if non_interactive or not sys.stdin.isatty():
        return default
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def prompt_int(prompt: str, default: int, non_interactive: bool) -> int:
    try:
        return int(prompt_text(prompt, str(default), non_interactive))
    except ValueError:
        return default


def prompt_bool(prompt: str, default: bool, non_interactive: bool) -> bool:
    if non_interactive or not sys.stdin.isatty():
        return default
    hint = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "t", "y", "yes"}


def normalize_ollama_url(raw_url: str) -> str:
    url = str(raw_url).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    url = url.rstrip("/")
    if "/api/" in url:
        return url
    if url.endswith("/api"):
        return url + "/generate"
    return url + "/api/generate"


def normalize_sidecar_suffix(raw_suffix: str) -> str:
    suffix = str(raw_suffix).strip()
    if not suffix:
        return ""
    if not suffix.startswith("."):
        suffix = "." + suffix
    suffix = re.sub(r'[:<>""/\\|?*\s]+', '-', suffix)
    suffix = re.sub(r'-+', '-', suffix)
    if not suffix.endswith(".txt"):
        suffix += ".txt"
    return suffix


def suffix_label(suffix: str) -> str:
    if not suffix:
        return ""
    out = suffix[1:] if suffix.startswith(".") else suffix
    if out.endswith(".txt"):
        out = out[:-4]
    return out


def sanitize_model_name(model: str) -> str:
    out = re.sub(r"\s+", "_", str(model).strip())
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", out)
    out = re.sub(r"_+", "_", out)
    out = out.strip("._-")
    return out or "model"


def sanitize_analysis_type(raw_value: str, fallback: str) -> str:
    value = str(raw_value).strip().lower()
    if not value:
        value = fallback
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or fallback


def analysis_configs(settings: dict[str, Any]) -> list[dict[str, Any]]:
    ai = settings.get("ai", {})
    analyses = ai.get("analyses", {}) if isinstance(ai, dict) else {}
    if not isinstance(analyses, dict):
        return []
    default_timeout = positive_int(ai.get("timeout_seconds", 300), 300)

    ordered_keys = [k for k in ("simple", "detailed") if k in analyses]
    ordered_keys.extend(sorted(k for k in analyses if k not in {"simple", "detailed"}))

    configs: list[dict[str, Any]] = []
    for key in ordered_keys:
        raw_cfg = analyses.get(key)
        if not isinstance(raw_cfg, dict):
            continue
        default_kind = AI_KIND_SIMPLE if key == "simple" else AI_KIND_DETAILED if key == "detailed" else key
        kind = sanitize_analysis_type(raw_cfg.get("analysis_type", default_kind), default_kind)
        model = str(raw_cfg.get("model", "")).strip()
        prompt = str(raw_cfg.get("prompt", "")).strip()
        timeout_seconds = positive_int(raw_cfg.get("timeout_seconds", default_timeout), default_timeout)
        if not model or not prompt:
            continue
        model_root = sanitize_model_name(model)
        configs.append(
            {
                "key": key,
                "enabled": bool(raw_cfg.get("enabled", True)),
                "kind": kind,
                "model": model,
                "model_root": model_root,
                "prompt": prompt,
                "timeout_seconds": timeout_seconds,
                "suffix": f".{model_root}.{kind}.txt",
                "display_label": f"{kind} ({model_root})",
            }
        )
    return configs


def compose_prompt_for_asset(prompt_template: str, asset: Asset) -> str:
    category = str(asset.topic).strip() or "uncategorized"
    template = str(prompt_template).replace("{category}", category).strip()
    context = (
        f"Category context: \"{category}\". Explain and frame the meme from the perspective of this category. "
        "For example, an Anti-Elon category implies criticism of Elon."
    )

    lower_template = template.lower()
    has_category_hint = category.lower() in lower_template or "category" in lower_template
    has_perspective_hint = "perspective" in lower_template

    if template and has_category_hint and has_perspective_hint:
        return template
    if template:
        return context + "\n\n" + template
    return context


def analysis_type_priority(settings: dict[str, Any]) -> list[str]:
    configured = {cfg["kind"] for cfg in analysis_configs(settings)}
    configured.update({AI_KIND_SIMPLE, AI_KIND_DETAILED})
    return sorted(configured, key=lambda value: (-len(value), value))


def legacy_simple_labels(settings: dict[str, Any]) -> set[str]:
    labels = set(LEGACY_SIMPLE_LABELS)
    legacy = settings.get("summaries")
    if isinstance(legacy, dict):
        label = suffix_label(normalize_sidecar_suffix(str(legacy.get("suffix", ""))))
        if label:
            labels.add(label)
    return labels


def positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def format_duration(total_seconds: float) -> str:
    seconds = max(0, int(total_seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def estimate_remaining_seconds(elapsed_seconds: float, completed: int, total: int) -> float | None:
    if total <= 0:
        return 0.0
    if completed <= 0:
        return None
    if completed >= total:
        return 0.0
    avg_seconds = elapsed_seconds / completed
    return max(0.0, avg_seconds * (total - completed))


def normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    s = deep_merge(DEFAULT_SETTINGS, settings)
    s["build"]["page_size"] = max(1, int(s["build"].get("page_size", 30)))
    s["build"]["new_days"] = max(0, int(s["build"].get("new_days", 14)))

    site_url = str(s["site"].get("url", "")).strip("/")
    if site_url and not site_url.startswith(("http://", "https://")):
        site_url = "https://" + site_url
    s["site"]["url"] = site_url

    ai = s.get("ai")
    if not isinstance(ai, dict):
        ai = {}
    s["ai"] = ai

    raw_had_ai = isinstance(settings.get("ai"), dict)
    legacy = s.get("summaries") if isinstance(s.get("summaries"), dict) else {}

    if not raw_had_ai and legacy:
        ai["enabled"] = bool(legacy.get("enabled", ai.get("enabled", False)))
        if str(legacy.get("url", "")).strip():
            ai["url"] = str(legacy.get("url", "")).strip()
        if "timeout_seconds" in legacy:
            ai["timeout_seconds"] = legacy.get("timeout_seconds")
        if "retries" in legacy:
            ai["retries"] = legacy.get("retries")
        if "retry_backoff_seconds" in legacy:
            ai["retry_backoff_seconds"] = legacy.get("retry_backoff_seconds")

    ai["enabled"] = bool(ai.get("enabled", False))
    ai["timeout_seconds"] = positive_int(ai.get("timeout_seconds", 300), 300)
    ai["retries"] = positive_int(ai.get("retries", 3), 3)
    ai["retry_backoff_seconds"] = positive_int(ai.get("retry_backoff_seconds", 2), 2)
    ai_url = normalize_ollama_url(ai.get("url", ""))
    if not ai_url:
        ai_url = normalize_ollama_url(DEFAULT_SETTINGS["ai"]["url"])
    ai["url"] = ai_url

    raw_analyses = ai.get("analyses")
    if not isinstance(raw_analyses, dict):
        raw_analyses = {}

    default_analyses = DEFAULT_SETTINGS["ai"]["analyses"]
    merged_analyses: dict[str, dict[str, Any]] = {}
    ordered_keys = ["simple", "detailed"]
    ordered_keys.extend(sorted(k for k in raw_analyses if k not in {"simple", "detailed"}))

    for key in ordered_keys:
        default_cfg = default_analyses.get(
            key,
            {
                "enabled": True,
                "analysis_type": key,
                "model": "gemma3:27b-it-q8_0",
                "prompt": SIMPLE_PROMPT if key == "simple" else DETAILED_PROMPT,
            },
        )
        raw_cfg = raw_analyses.get(key)
        if not isinstance(raw_cfg, dict):
            raw_cfg = {}
        cfg = deep_merge(default_cfg, raw_cfg)
        default_kind = default_cfg.get("analysis_type", key)
        cfg["enabled"] = bool(cfg.get("enabled", True))
        cfg["analysis_type"] = sanitize_analysis_type(cfg.get("analysis_type", default_kind), default_kind)
        cfg["model"] = str(cfg.get("model", default_cfg.get("model", ""))).strip() or str(default_cfg.get("model", "")).strip()
        cfg["prompt"] = str(cfg.get("prompt", default_cfg.get("prompt", ""))).strip() or str(default_cfg.get("prompt", "")).strip()
        cfg["timeout_seconds"] = positive_int(cfg.get("timeout_seconds", ai["timeout_seconds"]), ai["timeout_seconds"])
        merged_analyses[key] = cfg

    ai["analyses"] = merged_analyses

    if isinstance(s.get("summaries"), dict):
        summary_url = normalize_ollama_url(s["summaries"].get("url", ""))
        if summary_url:
            s["summaries"]["url"] = summary_url
        suffix = normalize_sidecar_suffix(str(s["summaries"].get("suffix", "")))
        if suffix:
            s["summaries"]["suffix"] = suffix

    return s


def write_if_changed(path: Path, content: str, dry_run: bool = False) -> bool:
    data = content.replace("\r\n", "\n")
    if path.exists() and path.read_text(encoding="utf-8").replace("\r\n", "\n") == data:
        return False
    if dry_run:
        print(f"[dry-run] write {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return True


def create_settings(settings_path: Path, non_interactive: bool, dry_run: bool) -> dict[str, Any]:
    settings = deep_merge(
        DEFAULT_SETTINGS,
        {
            "site": {
                "name": prompt_text("Site title", DEFAULT_SETTINGS["site"]["name"], non_interactive),
                "url": prompt_text("Site URL", DEFAULT_SETTINGS["site"]["url"], non_interactive),
            },
            "paths": {"memes_root": prompt_text("Memes root directory", DEFAULT_SETTINGS["paths"]["memes_root"], non_interactive)},
            "build": {
                "page_size": prompt_int("Items per page", DEFAULT_SETTINGS["build"]["page_size"], non_interactive),
                "new_days": prompt_int("New badge window in days", DEFAULT_SETTINGS["build"]["new_days"], non_interactive),
            },
            "ai": {
                "enabled": prompt_bool("Enable AI analysis generation by default?", DEFAULT_SETTINGS["ai"]["enabled"], non_interactive),
                "url": prompt_text("Ollama API URL", DEFAULT_SETTINGS["ai"]["url"], non_interactive),
                "analyses": {
                    "simple": {
                        "enabled": True,
                        "analysis_type": AI_KIND_SIMPLE,
                        "model": prompt_text(
                            "Simple analysis model",
                            DEFAULT_SETTINGS["ai"]["analyses"]["simple"]["model"],
                            non_interactive,
                        ),
                        "prompt": DEFAULT_SETTINGS["ai"]["analyses"]["simple"]["prompt"],
                    },
                    "detailed": {
                        "enabled": True,
                        "analysis_type": AI_KIND_DETAILED,
                        "model": prompt_text(
                            "Detailed analysis model",
                            DEFAULT_SETTINGS["ai"]["analyses"]["detailed"]["model"],
                            non_interactive,
                        ),
                        "prompt": DEFAULT_SETTINGS["ai"]["analyses"]["detailed"]["prompt"],
                    },
                },
            },
        },
    )
    settings = normalize_settings(settings)
    payload = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(settings_path, payload, dry_run=dry_run)
    return settings

def load_settings(repo_root: Path, settings_file: str, non_interactive: bool, dry_run: bool) -> tuple[dict[str, Any], Path]:
    path = repo_root / settings_file
    if path.exists():
        return normalize_settings(json.loads(path.read_text(encoding="utf-8-sig"))), path
    print(f"Creating {path} ...")
    return create_settings(path, non_interactive, dry_run), path

def read_text_multi(path: Path, encodings: tuple[str, ...] = ("utf-8", "utf-8-sig", "cp1252", "latin-1")) -> str:
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="replace")


def parse_dt(value: str, fallback: datetime) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = fallback
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_first_seen(asset_path: Path, dry_run: bool) -> Path:
    sidecar = asset_path.with_name(asset_path.name + ".first-seen.txt")
    if sidecar.exists():
        return sidecar
    stamp = datetime.fromtimestamp(asset_path.stat().st_mtime, tz=timezone.utc).isoformat()
    if dry_run:
        print(f"[dry-run] create {sidecar}")
        return sidecar
    sidecar.write_text(stamp + "\n", encoding="utf-8")
    return sidecar


def metadata_sort_key(artifact: MetadataArtifact) -> tuple[float, str]:
    return (-artifact.mtime_dt.timestamp(), str(artifact.path).lower())


def sort_metadata_artifacts(artifacts: list[MetadataArtifact]) -> None:
    artifacts.sort(key=metadata_sort_key)


def pick_latest_simple_artifact(asset: Asset) -> None:
    for artifact in asset.metadata_artifacts:
        if artifact.kind == AI_KIND_SIMPLE:
            asset.simple_path = artifact.path
            asset.simple_text = artifact.text
            asset.simple_label = artifact.label
            return
    asset.simple_path = None
    asset.simple_text = ""
    asset.simple_label = ""


def classify_sidecar_label(
    label: str,
    analysis_kind_order: list[str],
    legacy_simple: set[str],
    legacy_detailed: set[str],
) -> tuple[str, str, bool]:
    for kind in analysis_kind_order:
        suffix = "." + kind
        if label.endswith(suffix) and len(label) > len(suffix):
            model_root = label[: -len(suffix)]
            return kind, f"{kind} ({model_root})", True

    if label in legacy_simple:
        return AI_KIND_SIMPLE, f"{AI_KIND_SIMPLE} ({label})", True
    if label in legacy_detailed:
        return AI_KIND_DETAILED, f"{AI_KIND_DETAILED} ({label})", True
    return "other", label, False


def to_url(path: Path | str) -> str:
    raw = str(path).replace("\\", "/")
    parts = [p for p in raw.split("/") if p not in {"", "."}]
    return "/" + "/".join(quote(p, safe="-_.~") for p in parts)


def collect_assets(repo_root: Path, settings: dict[str, Any], max_topics: int | None, dry_run: bool) -> dict[str, list[Asset]]:
    memes_root = repo_root / settings["paths"]["memes_root"]
    if not memes_root.exists():
        print(f"Memes root does not exist: {memes_root}")
        return {}

    topic_dirs = sorted([d for d in memes_root.iterdir() if d.is_dir()], key=lambda p: p.name.lower())
    if max_topics is not None:
        topic_dirs = topic_dirs[:max_topics]

    kind_order = analysis_type_priority(settings)
    simple_labels = legacy_simple_labels(settings)
    detailed_labels = set(LEGACY_DETAILED_LABELS)
    out: dict[str, list[Asset]] = {}

    for topic_dir in topic_dirs:
        topic_assets: list[Asset] = []
        for candidate in sorted(topic_dir.rglob("*"), key=lambda p: str(p).lower()):
            if not candidate.is_file() or candidate.suffix.lower() not in TRACKED_EXTS:
                continue

            first_seen_path = ensure_first_seen(candidate, dry_run=dry_run)
            fallback = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
            first_seen = fallback.isoformat()
            if first_seen_path.exists():
                raw = read_text_multi(first_seen_path).strip()
                if raw:
                    first_seen = raw
            first_seen_dt = parse_dt(first_seen, fallback)
            first_seen = first_seen_dt.isoformat()

            ocr_path = candidate.with_name(candidate.name + ".txt")
            ocr_text = read_text_multi(ocr_path).strip() if ocr_path.exists() else ""

            metadata_artifacts: list[MetadataArtifact] = []
            if ocr_text:
                ocr_mtime = datetime.fromtimestamp(ocr_path.stat().st_mtime, tz=timezone.utc)
                metadata_artifacts.append(
                    MetadataArtifact(
                        label="tesseract-ocr",
                        path=ocr_path,
                        text=ocr_text,
                        mtime_dt=ocr_mtime,
                        render_markdown=False,
                        kind="ocr",
                    )
                )

            for meta in sorted(candidate.parent.glob(candidate.name + ".*.txt"), key=lambda p: p.name.lower()):
                if meta == first_seen_path:
                    continue
                body = read_text_multi(meta).strip()
                if not body:
                    continue
                label = meta.name[len(candidate.name) + 1 :]
                if label.endswith(".txt"):
                    label = label[:-4]
                kind, display_label, markdown = classify_sidecar_label(label, kind_order, simple_labels, detailed_labels)
                mtime_dt = datetime.fromtimestamp(meta.stat().st_mtime, tz=timezone.utc)
                metadata_artifacts.append(
                    MetadataArtifact(
                        label=display_label,
                        path=meta,
                        text=body,
                        mtime_dt=mtime_dt,
                        render_markdown=markdown,
                        kind=kind,
                    )
                )

            sort_metadata_artifacts(metadata_artifacts)

            simple_path: Path | None = None
            simple_text = ""
            simple_label = ""
            for artifact in metadata_artifacts:
                if artifact.kind == AI_KIND_SIMPLE:
                    simple_path = artifact.path
                    simple_text = artifact.text
                    simple_label = artifact.label
                    break

            rel_from_memes = candidate.relative_to(memes_root)
            rel_path = Path(settings["paths"]["memes_root"]) / rel_from_memes
            topic_assets.append(
                Asset(
                    topic=topic_dir.name,
                    abs_path=candidate,
                    rel_path=rel_path,
                    first_seen=first_seen,
                    first_seen_dt=first_seen_dt,
                    first_seen_path=first_seen_path if first_seen_path.exists() else None,
                    simple_path=simple_path,
                    simple_text=simple_text,
                    simple_label=simple_label,
                    ocr_path=ocr_path if ocr_path.exists() else None,
                    ocr_text=ocr_text,
                    metadata_artifacts=metadata_artifacts,
                )
            )

        topic_assets.sort(key=lambda a: (a.first_seen_dt, str(a.rel_path).lower()), reverse=True)
        out[topic_dir.name] = topic_assets

    return out


def request_ai_analysis(asset: Asset, settings: dict[str, Any], model: str, prompt: str, timeout_seconds: int | None = None) -> str:
    image_b64 = base64.b64encode(asset.abs_path.read_bytes()).decode("ascii")
    ai_settings = settings["ai"]
    url = str(ai_settings["url"]).strip()
    api_is_chat = url.rstrip("/").endswith("/api/chat")

    if api_is_chat:
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
        }
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "images": [image_b64],
        }

    body = json.dumps(payload).encode("utf-8")
    retries = int(ai_settings["retries"])
    backoff = int(ai_settings["retry_backoff_seconds"])
    timeout = positive_int(timeout_seconds if timeout_seconds is not None else ai_settings["timeout_seconds"], 300)

    for attempt in range(1, retries + 1):
        req = Request(url=url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if api_is_chat:
                text = str((data.get("message") or {}).get("content", "")).strip()
            else:
                text = str(data.get("response", "")).strip()
                if not text:
                    text = str((data.get("message") or {}).get("content", "")).strip()
            if text:
                return text
            raise RuntimeError("empty model response")
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected, ConnectionError, OSError, json.JSONDecodeError, RuntimeError) as exc:
            if attempt == retries:
                raise RuntimeError(f"Failed analysis for {asset.abs_path}: {exc}") from exc
            wait = backoff * attempt
            print(f"  retry {attempt}/{retries} after error: {exc}")
            time.sleep(wait)

    raise RuntimeError(f"Failed analysis for {asset.abs_path}")


def flatten_image_assets(assets_by_topic: dict[str, list[Asset]]) -> list[Asset]:
    assets = [
        asset
        for topic_assets in assets_by_topic.values()
        for asset in topic_assets
        if asset.abs_path.suffix.lower() in IMAGE_EXTS
    ]
    assets.sort(key=lambda a: (a.first_seen_dt, str(a.rel_path).lower()), reverse=True)
    return assets


def analysis_job_priority(job: dict[str, Any]) -> tuple[int, str, str]:
    rank = {AI_KIND_SIMPLE: 0, AI_KIND_DETAILED: 1}
    return (rank.get(job.get("kind", ""), 2), str(job.get("key", "")), str(job.get("kind", "")))


def pending_assets_for_job(image_assets: list[Asset], job: dict[str, Any]) -> list[tuple[Asset, Path]]:
    pending: list[tuple[Asset, Path]] = []
    for asset in image_assets:
        out_path = asset.abs_path.with_name(asset.abs_path.name + job["suffix"])
        if out_path.exists() and read_text_multi(out_path).strip():
            continue
        pending.append((asset, out_path))
    return pending


def process_analysis_job(
    phase_name: str,
    pending: list[tuple[Asset, Path]],
    job: dict[str, Any],
    settings: dict[str, Any],
    dry_run: bool,
) -> tuple[int, int, int]:
    total = len(pending)
    if total == 0:
        print(f"{phase_name}: 0 missing artifacts.")
        return (0, 0, 0)

    print(f"{phase_name}: {total} missing artifacts (newest to oldest).")
    phase_start = time.perf_counter()
    attempted = 0
    written = 0
    failed = 0

    for index, (asset, out_path) in enumerate(pending, start=1):
        attempted += 1
        status = "skipped"
        print(f"Analyzing ({job['kind']}) {index}/{total}: {asset.rel_path}")

        if dry_run:
            status = "dry-run"
            print(f"[dry-run] analyze -> {out_path}")
        else:
            prompt = compose_prompt_for_asset(job["prompt"], asset)
            try:
                text = request_ai_analysis(asset, settings, job["model"], prompt, timeout_seconds=job["timeout_seconds"]).strip()
            except RuntimeError as exc:
                failed += 1
                status = "failed"
                print(f"  failed ({job['kind']}) {asset.rel_path}: {exc}")
            else:
                out_path.write_text(text + "\n", encoding="utf-8")
                mtime_dt = datetime.fromtimestamp(out_path.stat().st_mtime, tz=timezone.utc)
                artifact = MetadataArtifact(
                    label=job["display_label"],
                    path=out_path,
                    text=text,
                    mtime_dt=mtime_dt,
                    render_markdown=True,
                    kind=job["kind"],
                )
                asset.metadata_artifacts = [item for item in asset.metadata_artifacts if item.path != out_path]
                asset.metadata_artifacts.append(artifact)
                sort_metadata_artifacts(asset.metadata_artifacts)
                pick_latest_simple_artifact(asset)
                written += 1
                status = "wrote"

        elapsed = time.perf_counter() - phase_start
        eta_seconds = estimate_remaining_seconds(elapsed, index, total)
        eta_display = format_duration(eta_seconds) if eta_seconds is not None else "unknown"
        print(
            f"  progress {index}/{total} ({index/total:.1%}) elapsed={format_duration(elapsed)} eta={eta_display} status={status}"
        )

    total_elapsed = time.perf_counter() - phase_start
    print(
        f"{phase_name} complete: attempted {attempted}; wrote {written}; failed {failed}; elapsed={format_duration(total_elapsed)}"
    )
    return (attempted, written, failed)


def maybe_generate_ai_artifacts(
    assets_by_topic: dict[str, list[Asset]],
    settings: dict[str, Any],
    enabled: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    if not enabled:
        return (0, 0, 0)

    analysis_jobs = [cfg for cfg in analysis_configs(settings) if cfg["enabled"]]
    if not analysis_jobs:
        return (0, 0, 0)

    analysis_jobs.sort(key=analysis_job_priority)
    image_assets = flatten_image_assets(assets_by_topic)
    if not image_assets:
        return (0, 0, 0)

    attempted_total = 0
    written_total = 0
    failed_total = 0

    for job in analysis_jobs:
        if job["kind"] == AI_KIND_SIMPLE:
            phase_name = "Basic descriptions"
        elif job["kind"] == AI_KIND_DETAILED:
            phase_name = "Detailed summaries"
        else:
            phase_name = f"{job['kind']} summaries"

        pending = pending_assets_for_job(image_assets, job)
        print(f"{phase_name} pending count: {len(pending)}")
        attempted, written, failed = process_analysis_job(phase_name, pending, job, settings, dry_run)
        attempted_total += attempted
        written_total += written
        failed_total += failed

    return (attempted_total, written_total, failed_total)


def resolve_jekyll_command(repo_root: Path) -> list[str] | None:
    has_gemfile = (repo_root / "Gemfile").exists()
    if has_gemfile and shutil.which("bundle"):
        return ["bundle", "exec", "jekyll", "build"]
    if shutil.which("jekyll"):
        return ["jekyll", "build"]
    return None


def run_command_with_live_output(command: list[str], cwd: Path) -> int:
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        if proc.stdout is not None:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
        return proc.wait()


def maybe_run_jekyll_rebuild(repo_root: Path, mode: str, dry_run: bool) -> bool:
    selected = str(mode or "auto").strip().lower()
    if selected not in {"auto", "on", "off"}:
        selected = "auto"

    if selected == "off":
        print("Jekyll rebuild skipped (--jekyll off).")
        return False

    config_path = repo_root / "_config.yml"
    if not config_path.exists():
        message = "Jekyll rebuild skipped: _config.yml not found."
        if selected == "on":
            raise RuntimeError(message)
        print(message)
        return False

    command = resolve_jekyll_command(repo_root)
    if not command:
        message = "Jekyll rebuild skipped: jekyll command not found."
        if selected == "on":
            raise RuntimeError(message)
        print(message)
        return False

    print(f"Running Jekyll rebuild: {' '.join(command)}")
    if dry_run:
        print("[dry-run] jekyll rebuild")
        return True

    return_code = run_command_with_live_output(command, repo_root)
    if return_code != 0:
        raise RuntimeError(f"Jekyll rebuild failed with exit code {return_code}")

    print("Jekyll rebuild complete.")
    return True


def write_catalog(repo_root: Path, settings: dict[str, Any], assets_by_topic: dict[str, list[Asset]], dry_run: bool) -> None:
    catalog: dict[str, dict[int, dict[str, Any]]] = {}
    for topic in sorted(assets_by_topic.keys(), key=lambda t: t.lower()):
        entries: dict[int, dict[str, Any]] = {}
        for idx, asset in enumerate(assets_by_topic[topic], start=1):
            metadata: dict[str, str] = {}
            if asset.first_seen_path:
                metadata["first-seen"] = asset.first_seen_path.relative_to(repo_root).as_posix()
            for artifact in asset.metadata_artifacts:
                metadata[artifact.label] = artifact.path.relative_to(repo_root).as_posix()
            entries[idx] = {"file": asset.rel_path.as_posix(), "filemtime": asset.first_seen, "metadata": metadata}
        catalog[topic] = entries
    out = repo_root / settings["paths"]["catalog_path"]
    write_if_changed(out, json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", dry_run=dry_run)


def apply_placeholders(text: str, context: dict[str, Any]) -> str:
    out = text
    for key, value in context.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def render_includes(text: str, includes_dir: Path, context: dict[str, Any], stack: list[str] | None = None) -> str:
    stack = stack or []

    def repl(match: re.Match[str]) -> str:
        include_name = match.group(1)
        include_path = includes_dir / include_name
        if include_name in stack:
            raise RuntimeError(f"Circular include: {' -> '.join(stack + [include_name])}")
        if not include_path.exists():
            return f"<!-- missing include: {escape(include_name)} -->"
        body = include_path.read_text(encoding="utf-8")
        rendered = render_includes(body, includes_dir, context, stack + [include_name])
        return apply_placeholders(rendered, context)

    return INCLUDE_PATTERN.sub(repl, text)


def render_layout(repo_root: Path, settings: dict[str, Any], layout: str, content: str, context: dict[str, Any]) -> str:
    layout_path = repo_root / settings["paths"]["layouts_dir"] / f"{layout}.html"
    includes_dir = repo_root / settings["paths"]["includes_dir"]
    template = layout_path.read_text(encoding="utf-8")
    base = {
        "content": content,
        "title": settings["site"]["name"],
        "site_name": settings["site"]["name"],
        "site_url": settings["site"]["url"],
        "category": "",
        "category_url": "",
    }
    base.update(context)
    with_includes = render_includes(template, includes_dir, base)
    return apply_placeholders(with_includes, base)


def ensure_sidebar_include(repo_root: Path, settings: dict[str, Any], dry_run: bool) -> None:
    includes_dir = repo_root / settings["paths"]["includes_dir"]
    includes_dir.mkdir(parents=True, exist_ok=True)
    write_if_changed(includes_dir / "sidebar.html", "{% include 'categories.html' %}\n", dry_run=dry_run)


def build_categories_include(repo_root: Path, settings: dict[str, Any], assets_by_topic: dict[str, list[Asset]], dry_run: bool) -> None:
    ensure_sidebar_include(repo_root, settings, dry_run)
    includes_dir = repo_root / settings["paths"]["includes_dir"]
    target = includes_dir / "categories.html"
    now = datetime.now(timezone.utc)
    new_window = timedelta(days=int(settings["build"]["new_days"]))
    memes_root = settings["paths"]["memes_root"]
    site_url = escape(str(settings["site"].get("url", "")).strip() or "/")
    site_name = escape(str(settings["site"].get("name", "")).strip() or "Site Home")
    logo_alt = escape("a neon cyberpunk cat, generated by cj with stable diffusion")

    category_rows: list[dict[str, Any]] = []
    for topic in sorted(assets_by_topic.keys(), key=lambda t: t.lower()):
        assets = assets_by_topic[topic]
        count = len(assets)
        new_count = sum(1 for a in assets if (now - a.first_seen_dt) <= new_window)
        url = to_url(Path(memes_root) / topic / "index.html")
        category_rows.append({"topic": topic, "url": url, "count": count, "new_count": new_count})

    freshest_rows = sorted(
        [row for row in category_rows if int(row["new_count"]) > 0],
        key=lambda row: (-int(row["new_count"]), str(row["topic"]).lower()),
    )

    lines = [
        "<div class=\"sidebar-brand\">",
        f"  <a class=\"sidebar-logo-link\" href=\"{site_url}\" aria-label=\"{site_name}\">",
        f"    <img class=\"sidebar-logo\" src=\"/logo.png\" alt=\"{logo_alt}\" />",
        "  </a>",
        "</div>",
        "<h2>Freshest Memes:</h2>",
    ]

    if freshest_rows:
        lines.append("<ul>")
        for row in freshest_rows:
            lines.append(
                f"  <li><a href=\"{row['url']}\">{escape(str(row['topic']))}</a> <span style=\"color:red\">({int(row['new_count'])} New)</span></li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p class=\"text-muted small\">No new memes in this window.</p>")

    lines += [
        "<h2>All Categories:</h2>",
        "<button class=\"btn btn-secondary btn-sm d-md-none mb-2\" type=\"button\" data-bs-toggle=\"collapse\" data-bs-target=\"#sidebarCategories\" aria-expanded=\"false\" aria-controls=\"sidebarCategories\">Show Categories</button>",
        "<div id=\"sidebarCategories\" class=\"collapse d-md-block\">",
        "<ul>",
    ]

    for row in category_rows:
        line = f"  <li><a href=\"{row['url']}\">{escape(str(row['topic']))}</a> ({int(row['count'])})"
        if int(row["new_count"]) > 0:
            line += f" <span style=\"color:red\">({int(row['new_count'])} New)</span>"
        line += "</li>"
        lines.append(line)

    lines += ["</ul>", "</div>"]
    write_if_changed(target, "\n".join(lines) + "\n", dry_run=dry_run)


def truncate(text: str, limit: int = 320) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def render_markdown_inline_fallback(text: str) -> str:
    safe = escape(text)
    safe = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f"<a href=\"{escape(m.group(2), quote=True)}\">{m.group(1)}</a>",
        safe,
    )
    safe = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", safe)
    safe = re.sub(r"\*\*([^*\n][^*\n]*?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"__([^_\n][^_\n]*?)__", r"<strong>\1</strong>", safe)
    safe = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", safe)
    safe = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<em>\1</em>", safe)
    return safe


def render_markdown_summary(text: str) -> str:
    safe_source = text.replace("\r\n", "\n").strip()
    if not safe_source:
        return ""
    if markdown_lib is not None:
        return markdown_lib.markdown(
            escape(safe_source),
            extensions=["extra", "nl2br", "sane_lists"],
            output_format="html5",
        )
    blocks = [block.strip() for block in safe_source.split("\n\n") if block.strip()]
    return "\n".join(f"<p>{render_markdown_inline_fallback(block).replace('\n', '<br />')}</p>" for block in blocks)


def relative_age_label(timestamp: datetime, now: datetime) -> str:
    delta_seconds = int((now - timestamp).total_seconds())
    if delta_seconds < 0:
        return "just now"
    if delta_seconds < 60:
        return "just now"

    units = [
        ("year", 365 * 24 * 60 * 60),
        ("month", 30 * 24 * 60 * 60),
        ("day", 24 * 60 * 60),
        ("hour", 60 * 60),
        ("minute", 60),
    ]
    for label, size in units:
        value = delta_seconds // size
        if value >= 1:
            suffix = "" if value == 1 else "s"
            return f"{value} {label}{suffix} ago"
    return "just now"

def media_card(asset: Asset, meme_url: str) -> str:
    media_url = to_url(asset.rel_path)
    alt_text = escape(truncate(asset.simple_text or asset.abs_path.stem, 220))
    ext = asset.abs_path.suffix.lower()
    if ext in IMAGE_EXTS:
        return f"<a href=\"{meme_url}\"><img class=\"card-img-top\" loading=\"lazy\" src=\"{media_url}\" alt=\"{alt_text}\" /></a>"
    if ext in VIDEO_EXTS:
        return f"<a href=\"{meme_url}\"><video class=\"card-img-top\" controls preload=\"metadata\" src=\"{media_url}\"></video></a>"
    return f"<p><a href=\"{meme_url}\">Open {escape(asset.abs_path.name)}</a></p>"


def render_asset_card(asset: Asset, render_now: datetime) -> str:
    meme_url = to_url(asset.rel_html_path)
    topic_url = to_url(Path(asset.rel_path.parts[0]) / asset.topic / "index.html")
    posted_iso = escape(asset.first_seen)
    posted_label = escape(relative_age_label(asset.first_seen_dt, render_now))
    lines = [
        f"<div class=\"card mb-4\" data-category=\"{escape(asset.topic)}\" data-pubdate=\"{posted_iso}\">",
        media_card(asset, meme_url),
        "  <div class=\"card-body\">",
        f"    <p class=\"card-text card-meta-line\"><b>Topic:</b> <a href=\"{topic_url}\">{escape(asset.topic)}</a> <b>Posted:</b> <time class=\"firstseen\" datetime=\"{posted_iso}\" title=\"{posted_iso}\">{posted_label}</time></p>",
        "  </div>",
        "</div>",
    ]
    return "\n".join(lines)


def render_meme_content(asset: Asset) -> str:
    media_url = to_url(asset.rel_path)
    topic_url = to_url(Path(asset.rel_path.parts[0]) / asset.topic / "index.html")
    ext = asset.abs_path.suffix.lower()
    alt_text = escape(truncate(asset.simple_text or asset.abs_path.stem, 220))
    lines = ["<article class=\"meme-entry\">", "  <section class=\"meme-media\">"]
    if ext in IMAGE_EXTS:
        lines.append(
            f"    <a class=\"meme-media-link\" href=\"{media_url}\"><img class=\"photo\" src=\"{media_url}\" alt=\"{alt_text}\" /></a>"
        )
    elif ext in VIDEO_EXTS:
        lines.append(f"    <video class=\"photo\" controls preload=\"metadata\" src=\"{media_url}\"></video>")
    else:
        lines.append(f"    <p><a href=\"{media_url}\">Download {escape(asset.abs_path.name)}</a></p>")
    lines.append("  </section>")
    lines.append("  <section class=\"meme-metadata\">")
    lines.append(f"    <section class=\"meme-meta-section\"><h3>First Seen</h3><p>{escape(asset.first_seen)}</p></section>")
    for artifact in asset.metadata_artifacts:
        if artifact.render_markdown:
            rendered = render_markdown_summary(artifact.text)
            lines.append(f"    <section class=\"meme-meta-section\"><h3>{escape(artifact.label)}</h3>{rendered}</section>")
        else:
            lines.append(f"    <section class=\"meme-meta-section\"><h3>{escape(artifact.label)}</h3><p>{escape(artifact.text)}</p></section>")
    lines.append(f"    <p class=\"meme-backlink\"><a href=\"{topic_url}\">Back to {escape(asset.topic)}</a></p>")
    lines.append("  </section>")
    lines.append("</article>")
    return "\n".join(lines)


def page_window(current: int, total: int, radius: int = 2) -> list[int | None]:
    pages = {1, total}
    for page in range(current - radius, current + radius + 1):
        if 1 <= page <= total:
            pages.add(page)
    ordered = sorted(pages)
    out: list[int | None] = []
    prev: int | None = None
    for page in ordered:
        if prev is not None and page - prev > 1:
            out.append(None)
        out.append(page)
        prev = page
    return out


def render_pagination(current: int, total: int, path_for_page: Callable[[int], Path]) -> str:
    if total <= 1:
        return ""

    lines = ["<nav aria-label=\"Page navigation\">", "  <ul class=\"pagination flex-wrap\">"]
    prev_page = current - 1
    next_page = current + 1

    if prev_page >= 1:
        lines.append(f"    <li class=\"page-item\"><a class=\"page-link\" href=\"{to_url(path_for_page(prev_page))}\">Previous</a></li>")
    else:
        lines.append("    <li class=\"page-item disabled\"><span class=\"page-link\">Previous</span></li>")

    for page in page_window(current, total):
        if page is None:
            lines.append("    <li class=\"page-item disabled\"><span class=\"page-link\">...</span></li>")
            continue
        cls = "page-item active" if page == current else "page-item"
        lines.append(f"    <li class=\"{cls}\"><a class=\"page-link\" href=\"{to_url(path_for_page(page))}\">{page}</a></li>")

    if next_page <= total:
        lines.append(f"    <li class=\"page-item\"><a class=\"page-link\" href=\"{to_url(path_for_page(next_page))}\">Next</a></li>")
    else:
        lines.append("    <li class=\"page-item disabled\"><span class=\"page-link\">Next</span></li>")

    lines += ["  </ul>", "</nav>"]
    return "\n".join(lines)


def chunks(items: list[Asset], size: int) -> list[list[Asset]]:
    if not items:
        return [[]]
    return [items[i : i + size] for i in range(0, len(items), size)]


def homepage_path(page: int) -> Path:
    return Path("index.html") if page == 1 else Path("pages") / str(page) / "index.html"


def category_path(memes_root: str, topic: str, page: int) -> Path:
    if page == 1:
        return Path(memes_root) / topic / "index.html"
    return Path(memes_root) / topic / "pages" / str(page) / "index.html"


def build_homepage(repo_root: Path, settings: dict[str, Any], all_assets: list[Asset], dry_run: bool) -> None:
    pages = chunks(all_assets, int(settings["build"]["page_size"]))
    total = len(pages)
    render_now = datetime.now(timezone.utc)
    for idx, page_assets in enumerate(pages, start=1):
        cards = "\n\n".join(render_asset_card(asset, render_now) for asset in page_assets)
        nav = render_pagination(idx, total, homepage_path)
        content = cards + ("\n\n" + nav if nav else "")
        title = settings["site"]["name"] if idx == 1 else f"{settings['site']['name']} - Page {idx}"
        html = render_layout(repo_root, settings, "homepage", content, {"title": title})
        write_if_changed(repo_root / homepage_path(idx), html, dry_run=dry_run)


def build_category_pages(repo_root: Path, settings: dict[str, Any], assets_by_topic: dict[str, list[Asset]], dry_run: bool) -> None:
    page_size = int(settings["build"]["page_size"])
    memes_root = settings["paths"]["memes_root"]
    render_now = datetime.now(timezone.utc)
    for topic in sorted(assets_by_topic.keys(), key=lambda t: t.lower()):
        pages = chunks(assets_by_topic[topic], page_size)
        total = len(pages)

        def path_for_page(page: int) -> Path:
            return category_path(memes_root, topic, page)

        for idx, page_assets in enumerate(pages, start=1):
            cards = "\n\n".join(render_asset_card(asset, render_now) for asset in page_assets)
            nav = render_pagination(idx, total, path_for_page)
            content = cards + ("\n\n" + nav if nav else "")
            html = render_layout(
                repo_root,
                settings,
                "category",
                content,
                {
                    "title": f"{topic} | {settings['site']['name']}",
                    "category": escape(topic),
                    "category_url": to_url(Path(memes_root) / topic / "index.html"),
                },
            )
            write_if_changed(repo_root / path_for_page(idx), html, dry_run=dry_run)


def build_meme_pages(repo_root: Path, settings: dict[str, Any], assets_by_topic: dict[str, list[Asset]], dry_run: bool) -> None:
    memes_root = settings["paths"]["memes_root"]
    for topic in sorted(assets_by_topic.keys(), key=lambda t: t.lower()):
        for asset in assets_by_topic[topic]:
            content = render_meme_content(asset)
            html = render_layout(
                repo_root,
                settings,
                "meme",
                content,
                {
                    "title": f"{asset.abs_path.name} | {topic} | {settings['site']['name']}",
                    "category": escape(topic),
                    "category_url": to_url(Path(memes_root) / topic / "index.html"),
                },
            )
            write_if_changed(repo_root / asset.rel_html_path, html, dry_run=dry_run)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    finalize_logging = setup_run_logging(repo_root, args.log_file)

    exit_code = 1
    try:
        settings, settings_path = load_settings(repo_root, args.settings_file, args.non_interactive, args.dry_run)
        if args.page_size is not None:
            settings["build"]["page_size"] = max(1, int(args.page_size))

        analysis_enabled = bool(settings.get("ai", {}).get("enabled", False))
        if not analysis_enabled and isinstance(settings.get("summaries"), dict):
            analysis_enabled = bool(settings["summaries"].get("enabled", False))
        if args.summaries == "on":
            analysis_enabled = True
        elif args.summaries == "off":
            analysis_enabled = False

        print(f"Using settings: {settings_path}")
        print(f"Site: {settings['site']['name']} ({settings['site']['url']})")

        if analysis_enabled:
            ai_settings = settings.get("ai", {}) if isinstance(settings.get("ai"), dict) else {}
            retries = positive_int(ai_settings.get("retries", 3), 3)
            backoff = positive_int(ai_settings.get("retry_backoff_seconds", 2), 2)
            for job in [cfg for cfg in analysis_configs(settings) if cfg["enabled"]]:
                print(
                    f"AI job: kind={job['kind']} model={job['model']} timeout_seconds={job['timeout_seconds']} retries={retries} backoff_seconds={backoff}"
                )

        assets_by_topic = collect_assets(repo_root, settings, None, args.dry_run)
        topic_count = len(assets_by_topic)
        asset_count = sum(len(v) for v in assets_by_topic.values())
        print(f"Collected {asset_count} assets across {topic_count} topics")

        analysis_assets_by_topic = assets_by_topic
        if args.max_topics is not None:
            max_topics = max(0, int(args.max_topics))
            scoped_topics = list(assets_by_topic.keys())[:max_topics]
            analysis_assets_by_topic = {topic: assets_by_topic[topic] for topic in scoped_topics}
            scoped_asset_count = sum(len(v) for v in analysis_assets_by_topic.values())
            print(
                f"Summary scope limited by --max-topics={max_topics}: {scoped_asset_count} assets across {len(analysis_assets_by_topic)} topics"
            )

        attempted, written, failed = maybe_generate_ai_artifacts(analysis_assets_by_topic, settings, analysis_enabled, args.dry_run)
        if analysis_enabled:
            print(f"AI analysis generation attempted for {attempted} artifacts; wrote {written} files; failed {failed} files")

        write_catalog(repo_root, settings, assets_by_topic, args.dry_run)
        build_categories_include(repo_root, settings, assets_by_topic, args.dry_run)
        build_meme_pages(repo_root, settings, assets_by_topic, args.dry_run)
        build_category_pages(repo_root, settings, assets_by_topic, args.dry_run)

        all_assets = sorted(
            [asset for topic_assets in assets_by_topic.values() for asset in topic_assets],
            key=lambda a: (a.first_seen_dt, str(a.rel_path).lower()),
            reverse=True,
        )
        build_homepage(repo_root, settings, all_assets, args.dry_run)
        maybe_run_jekyll_rebuild(repo_root, args.jekyll, args.dry_run)

        print("Build complete.")
        exit_code = 0
        return 0
    except Exception:
        print("Build failed with unhandled exception:")
        traceback.print_exc()
        return 1
    finally:
        finalize_logging(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
















