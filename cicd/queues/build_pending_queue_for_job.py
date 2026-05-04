from __future__ import annotations

from typing import Any

import legacy_build


def build_pending_queue_for_job(image_assets: list[Any], job: dict[str, Any]) -> list[tuple[Any, Any]]:
    return legacy_build.pending_assets_for_job(image_assets, job)
