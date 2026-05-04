from __future__ import annotations

from pathlib import Path

MAX_LINES_PER_SCRIPT = 220


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    target_root = repo_root / "cicd"
    failures: list[tuple[int, Path]] = []
    scanned = 0
    print(f"Checking CI/CD script length limit: MAX_LINES_PER_SCRIPT={MAX_LINES_PER_SCRIPT}")
    for path in sorted(target_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES_PER_SCRIPT:
            failures.append((line_count, path))
            print(f"FAIL lines={line_count:4d} path={path.relative_to(repo_root).as_posix()}")
        else:
            print(f"PASS lines={line_count:4d} path={path.relative_to(repo_root).as_posix()}")

    if failures:
        print("")
        print(f"Result: FAIL ({len(failures)}/{scanned} scripts exceed {MAX_LINES_PER_SCRIPT} lines)")
        return 1

    print("")
    print(f"Result: PASS ({scanned} scripts checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
