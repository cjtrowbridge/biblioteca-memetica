from __future__ import annotations

from pathlib import Path

import legacy_build

from cicd.queues.build_pending_queue_for_job import build_pending_queue_for_job
from cicd.queues.write_queue_file_atomic import write_queue_file_atomic


def write_all_ai_task_queues(
    settings_file: str,
    non_interactive: bool,
    queue_analyses_csv: str,
    queue_output_dir: str,
    dry_run: bool,
) -> dict[str, int]:
    repo_root = Path(__file__).resolve().parents[2]
    settings, _ = legacy_build.load_settings(repo_root, settings_file, non_interactive, dry_run)
    selected_keys = {token.strip().lower() for token in str(queue_analyses_csv).split(",") if token.strip()}
    if not selected_keys:
        selected_keys = {"simple", "detailed"}
    jobs = legacy_build.selected_analysis_jobs(settings, selected_keys)
    assets_by_topic = legacy_build.collect_assets(repo_root, settings, None, dry_run)
    image_assets = legacy_build.flatten_image_assets(assets_by_topic)
    output_root = repo_root / queue_output_dir
    stats: dict[str, int] = {}

    for job in jobs:
        pending = build_pending_queue_for_job(image_assets, job)
        rel_paths = [asset.rel_path.as_posix() for asset, _ in pending]
        out_path = output_root / f"{job['key']}.txt"
        write_queue_file_atomic(out_path, rel_paths, dry_run=dry_run)
        stats[str(job["key"])] = len(rel_paths)
        print(f"Queue generated: {out_path} pending={len(rel_paths)}")

    return stats
