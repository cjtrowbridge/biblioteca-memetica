---
plan_id: 2026-05-04-10-47-00_cicd-pipeline-decomposition-and-cloud-nas-task-routing
title: CI/CD Pipeline Decomposition and Cloud/NAS Task Routing
summary: Refactor build orchestration into a modular cicd pipeline, add cloud-generated AI task queues, add a race-safe NAS summarizer worker, and enforce script modularity with governance checks.
status: current
created_at: 2026-05-04-10-47-00
---

# CI/CD Pipeline Decomposition and Cloud/NAS Task Routing

Key: `[ ]` pending task, `[x]` completed task, `[?]` needs validation, `[-]` closed task

- [x] 1. Establish governing plan and lifecycle state for this checkpoint.
  - [x] 1.1 Keep this plan in `plans/future/` until implementation approval is confirmed.
    - [x] 1.1.1 Promote this plan to `plans/current/` immediately before first non-trivial implementation edits.
      - [x] 1.1.1.1 Regenerate plan indexes after any plan create/update/move/archive step.

- [x] 2. Define CI/CD module architecture and boundaries under `cicd/`.
  - [x] 2.1 Create `cicd/` subdirectories for entrypoints, cli, router, settings, discovery, queues, ai, worker, site, io, model, and util.
    - [x] 2.1.1 Ensure each script file contains exactly one primary method/function/subroutine.
      - [x] 2.1.1.1 Keep each script concise (target less than a few hundred lines per file).
  - [x] 2.2 Define dependency direction to avoid cyclic orchestration coupling.
    - [x] 2.2.1 Ensure `build.py` becomes CLI-only and delegates orchestration to a cicd router entrypoint.
      - [x] 2.2.1.1 Ensure `summarize.py` delegates queue-consumer work to a cicd summarizer entrypoint.

- [ ] 3. Refactor `build.py` into command input and routing only.
  - [x] 3.1 Preserve the existing CLI contract (`--summaries`, `--jekyll`, `--page-size`, `--max-topics`, `--max-inference-tasks`, `--dry-run`, `--log-file`).
    - [?] 3.1.1 Move implementation internals into single-function cicd modules while maintaining behavior parity.
      - [?] 3.1.1.1 Confirm backward-compatible invocation semantics for existing scripts and cron jobs.
  - [ ] 3.2 Move settings parsing/normalization into `cicd/settings/*`.
    - [ ] 3.2.1 Move asset discovery/classification into `cicd/discovery/*`.
      - [ ] 3.2.1.1 Move site rendering stages into `cicd/site/*`.
  - [ ] 3.3 Move shared I/O, logging, and utility helpers into `cicd/io/*` and `cicd/util/*`.
    - [ ] 3.3.1 Move data structures into `cicd/model/*`.
      - [ ] 3.3.1.1 Keep naming and output contracts stable for generated site artifacts and sidecars.

- [x] 4. Add cloud-build queue generation for pending AI work.
  - [x] 4.1 Add a queue-generation stage that runs during cloud build without requiring inference on cloud.
    - [x] 4.1.1 Generate one queue for pending simple descriptions and one queue for pending detailed descriptions.
      - [x] 4.1.1.1 Sort both queues by recency descending (newest first) based on canonical asset recency ordering.
  - [x] 4.2 Ensure queue entries map deterministically to sidecar targets using existing sanitized model + analysis suffix rules.
    - [x] 4.2.1 Ensure queue output omits completed tasks with non-empty existing sidecars at generation time.
      - [x] 4.2.1.1 Write queue files atomically (temp file + replace) to avoid partial reads during sync.
  - [x] 4.3 Add configuration/CLI controls for queue paths and enable/disable behavior.
    - [x] 4.3.1 Keep defaults suitable for Resilio-synced cloud-to-NAS workflows.
      - [x] 4.3.1.1 Preserve current site build behavior when queue generation is disabled.

- [x] 5. Add NAS summarizer queue-consumer pipeline.
  - [x] 5.1 Implement `summarize.py` wrapper and cicd summarizer entrypoint.
    - [x] 5.1.1 Accept per-run limits for simple and detailed task counts.
      - [x] 5.1.1.1 Process queue items in listed order (newest first from queue head).
  - [x] 5.2 Add race-condition-safe pre-check before inference for each queue task.
    - [x] 5.2.1 Re-check target sidecar existence and non-empty content immediately before model call.
      - [x] 5.2.1.1 Skip stale queue entries that were completed since queue file generation.
  - [x] 5.3 Add atomic sidecar writes and queue-consumer metrics logging.
    - [x] 5.3.1 Track attempted/written/skipped/failed counts separately for simple and detailed analyses.
      - [x] 5.3.1.1 Reuse existing retry/backoff/timeout/profiler conventions for inference calls.
  - [x] 5.4 Add optional single-run lock handling for periodic NAS scheduling.
    - [x] 5.4.1 Prevent overlapping summarizer runs from double-processing work.
      - [x] 5.4.1.1 Ensure lock cleanup occurs on normal exit and failure paths.

- [x] 6. Add CI/CD-style orchestration flow documentation and operator runbooks.
  - [x] 6.1 Create `cicd/README.md` with pipeline overview and control flow.
    - [x] 6.1.1 Include a module index listing every file with a brief purpose statement.
      - [x] 6.1.1.1 Document one-function-per-file standard and expected file-size constraints.
  - [x] 6.2 Update root `README.md` with the decomposed pipeline architecture.
    - [x] 6.2.1 Document cloud hourly build command and NAS summarizer periodic command examples.
      - [x] 6.2.1.1 Document queue file contracts, sidecar race checks, and sync assumptions.
  - [x] 6.3 Update `RULES.md` and any relevant playbook/reference/template indexes only if framework inventory or workflow policy changes require it.
    - [x] 6.3.1 Keep documentation integrity aligned with implementation changes.
      - [x] 6.3.1.1 Ensure all changed workflow behavior is reflected in documentation in the same checkpoint.

- [x] 7. Add script modularity governance tooling and enforcement policy.
  - [x] 7.1 Create a governance checker script that recursively scans `cicd/` scripts and reports line counts.
    - [x] 7.1.1 Define canonical `MAX_LINES_PER_SCRIPT` (or equivalent) at the top of the governance script as the single source of truth.
      - [x] 7.1.1.1 Emit pass/fail output and non-zero exit status when any file exceeds the configured limit.
  - [x] 7.2 Ensure governance output clearly identifies violating files and their measured line counts.
    - [x] 7.2.1 Ensure output is concise and automation-friendly for local runs and future CI integration.
      - [x] 7.2.1.1 Exclude non-script artifacts as needed to avoid false failures.
  - [x] 7.3 Add process enforcement requiring this governance checker after any `scripts/` changes.
    - [x] 7.3.1 Update workflow documentation/playbooks to require decomposition/modularization before proceeding when violations exist.
      - [x] 7.3.1.1 Require a clean governance pass before checkpoint completion on script-changing tasks.
  - [x] 7.4 Extend documentation to describe how to run the governance checker and interpret pass/fail results.
    - [x] 7.4.1 Document remediation expectations for over-limit files (split into smaller modules/functions).
      - [x] 7.4.1.1 Keep governance guidance synchronized across `cicd/README.md`, root `README.md`, and policy files as applicable.

- [ ] 8. Verify functional parity and new queue/worker behavior.
  - [x] 8.1 Run targeted validation for `build.py` wrapper routing and site-generation outputs.
    - [x] 8.1.1 Run targeted validation for queue generation content and recency ordering.
      - [x] 8.1.1.1 Confirm queue files exclude already-complete sidecars at generation time.
  - [x] 8.2 Run targeted validation for `summarize.py` queue consumption with limits.
    - [x] 8.2.1 Validate stale-entry skipping by creating sidecars between queue generation and task execution.
      - [x] 8.2.1.1 Validate sidecar write locations and naming parity with current conventions.
  - [x] 8.3 Run syntax/import checks for new cicd modules and entrypoints.
    - [?] 8.3.1 Confirm no regression in Jekyll rebuild stage control modes (`auto|on|off`).
      - [x] 8.3.1.1 Report verification evidence tied to checklist items in checkpoint summary.

- [ ] 9. Complete checkpoint governance and closeout artifacts.
  - [x] 9.1 Update plan checklist statuses as work is completed or intentionally closed.
    - [x] 9.1.1 Regenerate plan indexes after plan status updates and lifecycle moves.
      - [ ] 9.1.1.1 Include active plan path and checklist deltas in checkpoint summaries.
  - [ ] 9.2 Perform required completion checks before final summary.
    - [x] 9.2.1 Check `downtime/reports/pending/` for pending reports and report paths if present.
      - [ ] 9.2.1.1 Prompt for journal checkpoint update and commit/push approval per playbooks.
