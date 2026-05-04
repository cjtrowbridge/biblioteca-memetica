from __future__ import annotations

import os
from pathlib import Path


def acquire_run_lock(path: Path, dry_run: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"[dry-run] acquire lock {path}")
        return True
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()) + "\n")
        return True
    except FileExistsError:
        return False
