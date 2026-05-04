# Biblioteca Memetica

Static meme library generator.

## Overview

This project builds a static website from local meme folders.

- Input: `memes/<Topic>/...` (images/videos and sidecar metadata files)
- Output:
  - `memes.json` master catalog
  - static meme pages: `memes/<Topic>/<asset>.html`
  - static category index pages with pagination: `memes/<Topic>/index.html`, `memes/<Topic>/pages/<n>/index.html`
  - static homepage feed with pagination: `index.html`, `pages/<n>/index.html`
  - sidebar include generated at build time: `_includes/categories.html` (Freshest Memes section + All Categories section)
  - homepage/category cards show one-line metadata: topic link + relative posted-time link to the meme detail page (hover on posted time to see exact timestamp); meme detail pages render all metadata artifacts with First Seen pinned first

## Build Script

Main entrypoint: `build.py` (now a thin CI/CD router wrapper)

Legacy rendering/inference implementation: `legacy_build.py`

Modular orchestration package: `cicd/` (see `cicd/README.md` for module index)

First run creates `settings.local.json` (ignored by git) and prompts for:

- site name and URL
- memes root path
- pagination size
- Ollama API URL plus per-analysis host/model settings (simple + detailed) for optional AI artifact generation

Run:

```bash
python build.py
```

Useful options:

```bash
python build.py --summaries off
python build.py --summaries simple
python build.py --summaries detailed
python build.py --summaries simple,detailed
python build.py --page-size 48
python build.py --max-topics 5
python build.py --dry-run
python build.py --log-file build-cron.log
python build.py --jekyll on
python build.py --generate-ai-task-queues on
python build.py --queue-output-dir cicd/queues/pending
python build.py --queue-analyses simple,detailed
```

## Queue-Driven Cloud/NAS Workflow

Cloud build host (hourly):

```bash
python build.py --non-interactive --summaries off --generate-ai-task-queues on --queue-output-dir cicd/queues/pending --jekyll on --log-file build-cron.log
```

NAS/Xavier summarizer host (periodic):

```bash
python summarize.py --settings-file settings.local.json --queue-output-dir cicd/queues/pending --simple-limit 20 --detailed-limit 5
```

Behavior:
- Cloud build generates newest-first pending task queues for `simple` and `detailed` analyses.
- NAS summarizer consumes queue heads up to the configured limits.
- Summarizer re-checks target sidecars immediately before inference to avoid race-condition duplicates.
- New sidecars sync back and are included on the next cloud build.

## Generate Missing AI Artifacts

Run this to generate any missing simple/detailed AI artifacts across the full library:

```bash
python build.py --non-interactive --summaries simple,detailed --log-file build-cron.log
```

Behavior:
- The script processes simple descriptions first, then detailed summaries (when both analysis types are enabled).
- Each phase starts by counting missing artifacts for that phase.
- Processing order is newest to oldest across all image posts.
- Progress is printed for every item with elapsed time and ETA.
- `--max-topics` now only limits summary generation scope; site rendering/rebuild still uses all topics.
- Failures are isolated per artifact (the build continues).
- Any artifact that fails remains missing, so the next run retries it automatically.
- `--summaries` accepts a CSV list of analysis types to run: `simple`, `detailed`, or `simple,detailed`.

Queue-only generation (no inference calls from cloud):

```bash
python build.py --non-interactive --summaries off --generate-ai-task-queues on --queue-analyses simple,detailed --queue-output-dir cicd/queues/pending
```

Optional Jekyll stage:

```bash
python build.py --non-interactive --summaries simple,detailed --jekyll on --log-file build-cron.log
```

- `--jekyll auto` (default): run only when `_config.yml` exists and a jekyll command is available.
- `--jekyll on`: require Jekyll rebuild and fail if it cannot run.
- `--jekyll off`: skip Jekyll rebuild.

## Logging and Timeout Tuning

- Every build run writes to `build.log` by default while still printing to the console.
- Terminal output is flushed to the log immediately (line-by-line/live) during execution.
- Use `--log-file <path>` to override the output path (useful for cron jobs).
- Every Ollama API call appends one CSV row to `profiler.txt` in repo root: `analysis_type,provider_fqdn,model,response_code,runtime_seconds`.
- The profiler records one row per call attempt, so retries are captured as additional rows.
- `profiler.txt` includes a CSV header row on first write.
- `ai.timeout_seconds` is the global timeout fallback.
- `ai.analyses.simple.url` overrides the Ollama host for simple-description calls.
- `ai.analyses.detailed.url` overrides the Ollama host for detailed-analysis calls.
- `ai.analyses.simple.timeout_seconds` overrides the simple-description timeout.
- `ai.analyses.detailed.timeout_seconds` overrides the detailed-analysis timeout.
- For `gemma3:27b-it-q8_0`, detailed analysis can take several minutes. A tested run completed in about 512 seconds, so `600` is safer than `300`.

## CI/CD Script Governance

Run this after script changes:

```bash
python scripts/check_cicd_script_length.py
```

Rules:
- The checker recursively scans `cicd/**/*.py`.
- `MAX_LINES_PER_SCRIPT` is defined at the top of the checker as canonical limit.
- Any file over the limit is a hard failure and must be decomposed before moving on.

Example config snippet:

```json
"ai": {
  "timeout_seconds": 300,
  "analyses": {
    "simple": {
      "timeout_seconds": 300
    },
    "detailed": {
      "timeout_seconds": 600
    }
  }
}
```

## Metadata Conventions
For each asset file (`.jpg`, `.png`, `.mp4`, etc), the builder supports sidecars:

- `asset.ext.first-seen.txt` (created automatically if missing)
- `asset.ext.txt` (OCR text)
- `asset.ext.<sanitized_model>.<analysis_type>.txt` (AI artifacts, default analysis types: `simple-description` and `detailed-analysis`)
- legacy sidecars like `.llama3.2-vision.txt` and `.gemma3-27b-vision.txt` remain discoverable during migration
- AI analysis sidecars are interpreted as Markdown when rendered on meme detail pages; the newest simple-description artifact is used as image alt/search text

## Templates and Includes

- Layouts: `_layout/`
- Includes: `_includes/`

The builder resolves include directives like:

```html
{% include 'sidebar.html' %}
```

`_includes/categories.html` is regenerated at build time from current topics and counts.

## Domain

This repo now targets:

- `https://bibliotecamemetica.com`




