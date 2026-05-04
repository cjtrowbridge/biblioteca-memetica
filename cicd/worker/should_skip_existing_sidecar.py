from __future__ import annotations

from pathlib import Path


def should_skip_existing_sidecar(path: Path) -> bool:
    if not path.exists():
        return False
    return bool(path.read_text(encoding="utf-8").strip())
