from __future__ import annotations

from pathlib import Path

from cicd.cli.parse_summarizer_args import parse_summarizer_args
from cicd.worker.acquire_run_lock import acquire_run_lock
from cicd.worker.release_run_lock import release_run_lock
from cicd.worker.run_queue_tasks import run_queue_tasks


def route_summarizer_command(argv: list[str] | None = None) -> int:
    args = parse_summarizer_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    lock_path = repo_root / args.lock_file
    owns_lock = True

    if not args.disable_lock:
        owns_lock = acquire_run_lock(lock_path, dry_run=bool(args.dry_run))
        if not owns_lock:
            print(f"Another summarizer run is active (lock exists): {lock_path}")
            return 2

    try:
        return run_queue_tasks(
            settings_file=args.settings_file,
            non_interactive=bool(args.non_interactive),
            queue_output_dir=args.queue_output_dir,
            simple_limit=max(0, int(args.simple_limit)),
            detailed_limit=max(0, int(args.detailed_limit)),
            dry_run=bool(args.dry_run),
        )
    finally:
        if not args.disable_lock and owns_lock:
            release_run_lock(lock_path, dry_run=bool(args.dry_run))
