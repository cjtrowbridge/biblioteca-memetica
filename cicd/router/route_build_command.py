from __future__ import annotations

from pathlib import Path

from cicd.cli.parse_build_args import parse_build_args
from cicd.queues.write_all_ai_task_queues import write_all_ai_task_queues
from cicd.router.run_legacy_build_subprocess import run_legacy_build_subprocess


def route_build_command(argv: list[str] | None = None) -> int:
    args = parse_build_args(argv)
    repo_root = Path(__file__).resolve().parents[2]

    if args.generate_ai_task_queues == "on":
        write_all_ai_task_queues(
            settings_file=args.settings_file,
            non_interactive=bool(args.non_interactive),
            queue_analyses_csv=args.queue_analyses,
            queue_output_dir=args.queue_output_dir,
            dry_run=bool(args.dry_run),
        )

    legacy_args: list[str] = [
        "--settings-file",
        str(args.settings_file),
        "--log-file",
        str(args.log_file),
        "--summaries",
        str(args.summaries),
        "--jekyll",
        str(args.jekyll),
    ]

    if args.non_interactive:
        legacy_args.append("--non-interactive")
    if args.page_size is not None:
        legacy_args.extend(["--page-size", str(args.page_size)])
    if args.max_topics is not None:
        legacy_args.extend(["--max-topics", str(args.max_topics)])
    if args.max_inference_tasks is not None:
        legacy_args.extend(["--max-inference-tasks", str(args.max_inference_tasks)])
    if args.dry_run:
        legacy_args.append("--dry-run")

    return run_legacy_build_subprocess(legacy_args, repo_root)
