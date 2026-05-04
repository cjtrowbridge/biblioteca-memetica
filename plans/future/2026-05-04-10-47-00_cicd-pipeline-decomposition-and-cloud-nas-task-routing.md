---
plan_id: 2026-05-04-10-47-00_cicd-pipeline-decomposition-and-cloud-nas-task-routing
title: CI/CD Pipeline Decomposition and Cloud/NAS Task Routing
summary: Refactor build orchestration into a modular cicd pipeline, add cloud-generated AI task queues, add a race-safe NAS summarizer worker, and enforce script modularity with governance checks.
status: future
created_at: 2026-05-04-10-47-00
---

# CI/CD Pipeline Decomposition and Cloud/NAS Task Routing

Key: `[ ]` pending task, `[x]` completed task, `[?]` needs validation, `[-]` closed task

- [ ] 1. Establish governing plan and lifecycle state for this checkpoint.
  - [ ] 1.1 Keep this plan in `plans/future/` until implementation approval is confirmed.
    - [ ] 1.1.1 Promote this plan to `plans/current/` immediately before first non-trivial implementation edits.
      - [ ] 1.1.1.1 Regenerate plan indexes after any plan create/update/move/archive step.

- [ ] 2. Define CI/CD module architecture and boundaries under `cicd/`.
  - [ ] 2.1 Create `cicd/` subdirectories for entrypoints, cli, router, settings, discovery, queues, ai, worker, site, io, model, and util.
    - [ ] 2.1.1 Ensure each script file contains exactly one primary method/function/subroutine.
      - [ ] 2.1.1.1 Keep each script concise (target less than a few hundred lines per file).
  - [ ] 2.2 Define dependency direction to avoid cyclic orchestration coupling.
    - [ ] 2.2.1 Ensure `build.py` becomes CLI-only and delegates orchestration to a cicd router entrypoint.
      - [ ] 2.2.1.1 Ensure `summarize.py` delegates queue-consumer work to a cicd summarizer entrypoint.

- [ ] 3. Refactor `build.py` into command input and routing only.
  - [ ] 3.1 Preserve the existing CLI contract (`--summaries`, `--jekyll`, `--page-size`, `--max-topics`, `--max-inference-tasks`, `--dry-run`, `--log-file`).
    - [ ] 3.1.1 Move implementation internals into single-function cicd modules while maintaining behavior parity.
      - [ ] 3.1.1.1 Confirm backward-compatible invocation semantics for existing scripts and cron jobs.
  - [ ] 3.2 Move settings parsing/normalization into `cicd/settings/*`.
    - [ ] 3.2.1 Move asset discovery/classification into `cicd/discovery/*`.
      - [ ] 3.2.1.1 Move site rendering stages into `cicd/site/*`.
  - [ ] 3.3 Move shared I/O, logging, and utility helpers into `cicd/io/*` and `cicd/util/*`.
    - [ ] 3.3.1 Move data structures into `cicd/model/*`.
      - [ ] 3.3.1.1 Keep naming and output contracts stable for generated site artifacts and sidecars.

- [ ] 4. Add cloud-build queue generation for pending AI work.
  - [ ] 4.1 Add a queue-generation stage that runs during cloud build without requiring inference on cloud.
    - [ ] 4.1.1 Generate one queue for pending simple descriptions and one queue for pending detailed descriptions.
      - [ ] 4.1.1.1 Sort both queues by recency descending (newest first) based on canonical asset recency ordering.
  - [ ] 4.2 Ensure queue entries map deterministically to sidecar targets using existing sanitized model + analysis suffix rules.
    - [ ] 4.2.1 Ensure queue output omits completed tasks with non-empty existing sidecars at generation time.
      - [ ] 4.2.1.1 Write queue files atomically (temp file + replace) to avoid partial reads during sync.
  - [ ] 4.3 Add configuration/CLI controls for queue paths and enable/disable behavior.
    - [ ] 4.3.1 Keep defaults suitable for Resilio-synced cloud-to-NAS workflows.
      - [ ] 4.3.1.1 Preserve current site build behavior when queue generation is disabled.

- [ ] 5. Add NAS summarizer queue-consumer pipeline.
  - [ ] 5.1 Implement `summarize.py` wrapper and cicd summarizer entrypoint.
    - [ ] 5.1.1 Accept per-run limits for simple and detailed task counts.
      - [ ] 5.1.1.1 Process queue items in listed order (newest first from queue head).
  - [ ] 5.2 Add race-condition-safe pre-check before inference for each queue task.
    - [ ] 5.2.1 Re-check target sidecar existence and non-empty content immediately before model call.
      - [ ] 5.2.1.1 Skip stale queue entries that were completed since queue file generation.
  - [ ] 5.3 Add atomic sidecar writes and queue-consumer metrics logging.
    - [ ] 5.3.1 Track attempted/written/skipped/failed counts separately for simple and detailed analyses.
      - [ ] 5.3.1.1 Reuse existing retry/backoff/timeout/profiler conventions for inference calls.
  - [ ] 5.4 Add optional single-run lock handling for periodic NAS scheduling.
    - [ ] 5.4.1 Prevent overlapping summarizer runs from double-processing work.
      - [ ] 5.4.1.1 Ensure lock cleanup occurs on normal exit and failure paths.

- [ ] 6. Add CI/CD-style orchestration flow documentation and operator runbooks.
  - [ ] 6.1 Create `cicd/README.md` with pipeline overview and control flow.
    - [ ] 6.1.1 Include a module index listing every file with a brief purpose statement.
      - [ ] 6.1.1.1 Document one-function-per-file standard and expected file-size constraints.
  - [ ] 6.2 Update root `README.md` with the decomposed pipeline architecture.
    - [ ] 6.2.1 Document cloud hourly build command and NAS summarizer periodic command examples.
      - [ ] 6.2.1.1 Document queue file contracts, sidecar race checks, and sync assumptions.
  - [ ] 6.3 Update `RULES.md` and any relevant playbook/reference/template indexes only if framework inventory or workflow policy changes require it.
    - [ ] 6.3.1 Keep documentation integrity aligned with implementation changes.
      - [ ] 6.3.1.1 Ensure all changed workflow behavior is reflected in documentation in the same checkpoint.

- [ ] 7. Add script modularity governance tooling and enforcement policy.
  - [ ] 7.1 Create a governance checker script that recursively scans `cicd/` scripts and reports line counts.
    - [ ] 7.1.1 Define canonical `MAX_LINES_PER_SCRIPT` (or equivalent) at the top of the governance script as the single source of truth.
      - [ ] 7.1.1.1 Emit pass/fail output and non-zero exit status when any file exceeds the configured limit.
  - [ ] 7.2 Ensure governance output clearly identifies violating files and their measured line counts.
    - [ ] 7.2.1 Ensure output is concise and automation-friendly for local runs and future CI integration.
      - [ ] 7.2.1.1 Exclude non-script artifacts as needed to avoid false failures.
  - [ ] 7.3 Add process enforcement requiring this governance checker after any `scripts/` changes.
    - [ ] 7.3.1 Update workflow documentation/playbooks to require decomposition/modularization before proceeding when violations exist.
      - [ ] 7.3.1.1 Require a clean governance pass before checkpoint completion on script-changing tasks.
  - [ ] 7.4 Extend documentation to describe how to run the governance checker and interpret pass/fail results.
    - [ ] 7.4.1 Document remediation expectations for over-limit files (split into smaller modules/functions).
      - [ ] 7.4.1.1 Keep governance guidance synchronized across `cicd/README.md`, root `README.md`, and policy files as applicable.

- [ ] 8. Verify functional parity and new queue/worker behavior.
  - [ ] 8.1 Run targeted validation for `build.py` wrapper routing and site-generation outputs.
    - [ ] 8.1.1 Run targeted validation for queue generation content and recency ordering.
      - [ ] 8.1.1.1 Confirm queue files exclude already-complete sidecars at generation time.
  - [ ] 8.2 Run targeted validation for `summarize.py` queue consumption with limits.
    - [ ] 8.2.1 Validate stale-entry skipping by creating sidecars between queue generation and task execution.
      - [ ] 8.2.1.1 Validate sidecar write locations and naming parity with current conventions.
  - [ ] 8.3 Run syntax/import checks for new cicd modules and entrypoints.
    - [ ] 8.3.1 Confirm no regression in Jekyll rebuild stage control modes (`auto|on|off`).
      - [ ] 8.3.1.1 Report verification evidence tied to checklist items in checkpoint summary.

- [ ] 9. Complete checkpoint governance and closeout artifacts.
  - [ ] 9.1 Update plan checklist statuses as work is completed or intentionally closed.
    - [ ] 9.1.1 Regenerate plan indexes after plan status updates and lifecycle moves.
      - [ ] 9.1.1.1 Include active plan path and checklist deltas in checkpoint summaries.
  - [ ] 9.2 Perform required completion checks before final summary.
    - [ ] 9.2.1 Check `downtime/reports/pending/` for pending reports and report paths if present.
      - [ ] 9.2.1.1 Prompt for journal checkpoint update and commit/push approval per playbooks.
