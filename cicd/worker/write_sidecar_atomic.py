from __future__ import annotations

from pathlib import Path


def write_sidecar_atomic(path: Path, text: str, dry_run: bool) -> None:
    content = text.strip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"[dry-run] write sidecar {path}")
        return
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)
