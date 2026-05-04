from __future__ import annotations

from cicd.router.route_summarizer_command import route_summarizer_command


def run_summarizer_pipeline(argv: list[str] | None = None) -> int:
    return route_summarizer_command(argv)
