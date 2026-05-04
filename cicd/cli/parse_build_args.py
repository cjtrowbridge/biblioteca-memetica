from __future__ import annotations

import argparse


def parse_build_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CI/CD build router for static meme site generation.")
    parser.add_argument("--settings-file", default="settings.local.json")
    parser.add_argument("--log-file", default="build.log")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--summaries", default="off", help="CSV: simple,detailed or off.")
    parser.add_argument("--jekyll", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--page-size", type=int, default=None)
    parser.add_argument("--max-topics", type=int, default=None)
    parser.add_argument("--max-inference-tasks", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--generate-ai-task-queues", choices=["on", "off"], default="off")
    parser.add_argument("--queue-output-dir", default="cicd/queues/pending")
    parser.add_argument("--queue-analyses", default="simple,detailed", help="CSV analyses for queue generation.")
    return parser.parse_args(argv)
