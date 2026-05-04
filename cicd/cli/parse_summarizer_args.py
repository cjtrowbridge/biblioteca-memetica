from __future__ import annotations

import argparse


def parse_summarizer_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue-driven AI summarizer worker.")
    parser.add_argument("--settings-file", default="settings.local.json")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--queue-output-dir", default="cicd/queues/pending")
    parser.add_argument("--simple-limit", type=int, default=20)
    parser.add_argument("--detailed-limit", type=int, default=5)
    parser.add_argument("--lock-file", default="cicd/worker/summarize.lock")
    parser.add_argument("--disable-lock", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)
