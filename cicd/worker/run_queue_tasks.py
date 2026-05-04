from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import legacy_build

from cicd.queues.read_queue_file import read_queue_file
from cicd.worker.should_skip_existing_sidecar import should_skip_existing_sidecar
from cicd.worker.write_sidecar_atomic import write_sidecar_atomic


def run_queue_tasks(
    settings_file: str,
    non_interactive: bool,
    queue_output_dir: str,
    simple_limit: int,
    detailed_limit: int,
    dry_run: bool,
) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    settings, _ = legacy_build.load_settings(repo_root, settings_file, non_interactive, dry_run)
    limits = {"simple": max(0, int(simple_limit)), "detailed": max(0, int(detailed_limit))}
    selected_keys = {key for key, limit in limits.items() if limit > 0}
    if not selected_keys:
        print("No summarizer work requested: both limits are zero.")
        return 0

    jobs = legacy_build.selected_analysis_jobs(settings, selected_keys)
    output_root = repo_root / queue_output_dir
    total_failed = 0

    for job in jobs:
        key = str(job["key"])
        limit = limits.get(key, 0)
        queue_path = output_root / f"{key}.txt"
        entries = read_queue_file(queue_path)
        print(f"Queue {key}: total_entries={len(entries)} run_limit={limit}")
        attempted = 0
        wrote = 0
        skipped_existing = 0
        skipped_missing = 0
        failed = 0

        for rel_text in entries:
            if attempted >= limit:
                break
            attempted += 1
            rel_path = Path(rel_text)
            abs_path = repo_root / rel_path
            if not abs_path.exists():
                skipped_missing += 1
                print(f"  skip missing asset: {rel_path}")
                continue

            out_path = abs_path.with_name(abs_path.name + job["suffix"])
            if should_skip_existing_sidecar(out_path):
                skipped_existing += 1
                print(f"  skip existing sidecar: {out_path.relative_to(repo_root)}")
                continue

            topic = rel_path.parts[1] if len(rel_path.parts) > 1 else "uncategorized"
            asset = legacy_build.Asset(
                topic=topic,
                abs_path=abs_path,
                rel_path=rel_path,
                first_seen="",
                first_seen_dt=datetime.now(timezone.utc),
                first_seen_path=None,
            )
            prompt = legacy_build.compose_prompt_for_asset(job["prompt"], asset)

            if dry_run:
                print(f"  [dry-run] summarize {job['kind']} -> {out_path.relative_to(repo_root)}")
                wrote += 1
                continue

            try:
                text = legacy_build.request_ai_analysis(
                    asset,
                    settings,
                    job["url"],
                    job["model"],
                    prompt,
                    job["kind"],
                    timeout_seconds=job["timeout_seconds"],
                ).strip()
                write_sidecar_atomic(out_path, text, dry_run=False)
                wrote += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  failed {job['kind']} {rel_path}: {exc}")

        total_failed += failed
        print(
            f"Queue {key} complete: attempted={attempted} wrote={wrote} skipped_existing={skipped_existing} "
            f"skipped_missing={skipped_missing} failed={failed}"
        )

    return 1 if total_failed else 0
