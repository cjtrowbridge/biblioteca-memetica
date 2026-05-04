---
plan_id: 2026-04-21-12-19-08_ollama-call-profiler-csv-logging
title: Ollama Call Profiler CSV Logging
summary: Add per-call Ollama profiling output that appends analysis type, model, and runtime to profiler.txt for every API request.
status: current
created_at: 2026-04-21-12-19-08
---

# Ollama Call Profiler CSV Logging

Key: `[ ]` pending task, `[x]` completed task, `[?]` needs validation, `[-]` closed task

- [x] 1. Add per-call profiling output for Ollama requests.
  - [x] 1.1 Implement a profiler writer that appends one CSV line per API call.
    - [x] 1.1.1 Include `analysis_type`, `provider_fqdn`, `model`, `response_code`, and `runtime_seconds` fields in stable order.
      - [x] 1.1.1.1 Wire profiling writes directly at the Ollama request path so retries create independent rows.
  - [x] 1.2 Ensure profiling behavior is resilient.
    - [x] 1.2.1 Keep build execution flow unchanged when profiler logging succeeds.
      - [x] 1.2.1.1 Ensure profiler output path is deterministic (`profiler.txt` in repo root).

- [x] 2. Document the profiler behavior for operators.
  - [x] 2.1 Update runbook guidance for profiling output.
    - [x] 2.1.1 Describe row format and when rows are emitted.
      - [x] 2.1.1.1 Clarify that one line is emitted for each Ollama API call attempt.

- [x] 3. Verify profiler output correctness.
  - [x] 3.1 Run targeted validation on profiling format and append behavior.
    - [x] 3.1.1 Confirm generated lines are CSV and include expected values per request.
      - [x] 3.1.1.1 Report verification evidence in checkpoint summary.
