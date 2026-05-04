---
plan_id: 2026-04-21-12-48-37_per-analysis-ollama-host-configuration
title: Per-Analysis Ollama Host Configuration
summary: Allow simple and detailed analysis jobs to define separate Ollama hosts/providers while preserving global URL fallback behavior.
status: current
created_at: 2026-04-21-12-48-37
---

# Per-Analysis Ollama Host Configuration

Key: `[ ]` pending task, `[x]` completed task, `[?]` needs validation, `[-]` closed task

- [x] 1. Extend analysis config schema for per-analysis host selection.
  - [x] 1.1 Add a per-analysis URL field to normalized/simple+detailed analysis config.
    - [x] 1.1.1 Keep backward compatibility by defaulting each analysis URL to global `ai.url`.
      - [x] 1.1.1.1 Ensure URL normalization applies to per-analysis URL values.

- [x] 2. Use per-analysis host at request time.
  - [x] 2.1 Flow per-analysis URL through analysis job config into API request execution.
    - [x] 2.1.1 Ensure simple and detailed jobs can independently target different Ollama providers.
      - [x] 2.1.1.1 Keep retry/timeout/profiler behavior unchanged.

- [x] 3. Document and verify provider split behavior.
  - [x] 3.1 Update README and bootstrap prompts to describe per-analysis host fields.
    - [x] 3.1.1 Validate with a targeted syntax/runtime check that job logs show per-analysis host values.
      - [x] 3.1.1.1 Regenerate plan indexes after plan/doc updates.
