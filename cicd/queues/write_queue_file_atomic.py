from __future__ import annotations

from pathlib import Path


def write_queue_file_atomic(path: Path, lines: list[str], dry_run: bool) -> None:
    payload = "\n".join(lines).strip()
    content = (payload + "\n") if payload else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"[dry-run] write queue {path} entries={len(lines)}")
        return
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)
