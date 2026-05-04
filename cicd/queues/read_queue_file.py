from __future__ import annotations

from pathlib import Path


def read_queue_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out
