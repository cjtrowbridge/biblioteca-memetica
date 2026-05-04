# CI/CD Pipeline Modules

This folder contains the decomposed CI/CD-style build and summarization pipeline.

## Design Rules

- `build.py` and `summarize.py` are thin wrappers that route into this package.
- Each Python script in `cicd/` contains one primary function/subroutine.
- Keep files concise; enforce with `python scripts/check_cicd_script_length.py`.
- Queue files are generated atomically and consumed with race-safe sidecar rechecks.

## Pipeline Flow

1. `build.py` calls `cicd.entrypoints.run_build_pipeline`.
2. Build router optionally generates AI task queues (`simple`/`detailed`).
3. Build router executes the legacy site-render pipeline for full site output.
4. `summarize.py` calls `cicd.entrypoints.run_summarizer_pipeline`.
5. Summarizer router acquires lock, consumes queues, rechecks sidecars, writes outputs atomically.

## Module Index

- `entrypoints/run_build_pipeline.py`: Build pipeline entrypoint called by root `build.py`.
- `entrypoints/run_summarizer_pipeline.py`: Summarizer pipeline entrypoint called by root `summarize.py`.
- `cli/parse_build_args.py`: Build CLI parser (legacy build options + queue-generation options).
- `cli/parse_summarizer_args.py`: Summarizer CLI parser (limits, queue path, lock controls).
- `router/route_build_command.py`: Build command orchestration (queue generation + legacy build execution).
- `router/run_legacy_build_subprocess.py`: Executes `legacy_build.py` as the rendering/inference engine.
- `router/route_summarizer_command.py`: Summarizer orchestration with lock lifecycle.
- `queues/build_pending_queue_for_job.py`: Selects pending assets per analysis job.
- `queues/write_queue_file_atomic.py`: Writes queue files with temp-file replace semantics.
- `queues/read_queue_file.py`: Reads queue entries while skipping blank/comment lines.
- `queues/write_all_ai_task_queues.py`: Generates simple/detailed pending queues from current repository state.
- `worker/acquire_run_lock.py`: Creates exclusive lock files for single-run worker behavior.
- `worker/release_run_lock.py`: Releases worker lock files.
- `worker/should_skip_existing_sidecar.py`: Race-safe pre-check for pre-existing completed sidecars.
- `worker/write_sidecar_atomic.py`: Writes AI sidecars atomically.
- `worker/run_queue_tasks.py`: Executes queue-driven summarization with per-analysis limits.

## Governance

- Run after any script changes:
  - `python scripts/check_cicd_script_length.py`
- Pass criteria:
  - No `cicd/**/*.py` file exceeds `MAX_LINES_PER_SCRIPT` defined in the checker.
- Failure criteria:
  - Any file exceeds the maximum; split and modularize before moving forward.
