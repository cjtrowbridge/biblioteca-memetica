from __future__ import annotations

from cicd.router.route_build_command import route_build_command


def run_build_pipeline(argv: list[str] | None = None) -> int:
    return route_build_command(argv)
