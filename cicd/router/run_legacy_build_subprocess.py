from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_legacy_build_subprocess(argv: list[str], repo_root: Path) -> int:
    command = [sys.executable, str(repo_root / "legacy_build.py"), *argv]
    print(f"Running legacy build pipeline: {' '.join(command)}")
    completed = subprocess.run(command, cwd=repo_root, check=False)
    return int(completed.returncode)
