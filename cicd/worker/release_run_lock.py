from __future__ import annotations

from pathlib import Path


def release_run_lock(path: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] release lock {path}")
        return
    if path.exists():
        path.unlink()
