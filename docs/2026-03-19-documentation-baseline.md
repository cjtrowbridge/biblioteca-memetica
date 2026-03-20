# Documentation Baseline - 2026-03-19

## Scope

- Repository baseline for current build/documentation state before migration to script-first static generation.
- Sources reviewed: `README.md`, `ai.ipynb`, `build.ipynb`, generated root artifacts, and current repo layout.
- Note: `biblioteca-memetica/README.md` is not present in this repository snapshot.

## Current Pipeline Snapshot

1. Media source is `./memes/<Topic>/...` with topic folders as category keys.
2. `ensure_first_seen_files()` creates `.first-seen.txt` sidecars for tracked media types.
3. Metadata aggregation builds `memes.json` ordered by descending first-seen/file time.
4. Vision summaries are generated via Ollama endpoints and saved as sidecar text files.
5. Markdown artifacts are generated for per-meme pages, per-topic indexes, and site root index.
6. Sidebar category include is generated into `_includes/categories.html`.
7. HTML rendering logic exists in notebooks (`render_html`) and README also references a Jekyll build step.

## Artifact Map (Observed)

- Input tree: `memes/<topic>/<asset>`.
- Sidecars: `*.first-seen.txt`, `*.txt` (OCR), `*.llama-3.2-vision.txt` or related model-specific summary files.
- Catalog: `memes.json`.
- Content pages: `memes/<topic>/<asset>.md` and rendered `memes/<topic>/<asset>.html`.
- Topic index pages: `memes/<topic>/index.md` and rendered `memes/<topic>/index.html`.
- Root index: `index.md` and `index.html`.
- Shared include: `_includes/categories.html`.

## Dependencies and Runtime Assumptions (Observed)

- Python environment with notebook-era package installs (for example `requests`, `html5lib`, `python-frontmatter`, `markdown`).
- Local Ollama endpoint currently hardcoded in notebook cells (`http://docker-ai:11434/api/generate`).
- Existing template/layout files under `_layout/` and include fragments under `_includes/` are used during HTML rendering.

## Documentation Gaps and Debt

- README encoding issues and mojibake reduce readability (for example smart quotes and dashes rendered incorrectly).
- README says final build is Jekyll-driven, while notebooks also contain direct markdown-to-HTML rendering logic.
- README references dynamic-JavaScript future direction, which conflicts with current project decision to stay static.
- README still assumes meme assets are committed, but repository policy now ignores `memes/**` except `.placeholder`.
- No script-first runbook exists yet for planned `build.py` + local settings bootstrap.
- Pagination behavior for per-topic and global indexes is not yet documented as an explicit contract.

## Proposed Documentation Structure Changes

- Rewrite root `README.md` as a script-first contract for `build.py` and static outputs.
- Add a dedicated build contract doc describing required outputs, naming, and pagination conventions.
- Add a local configuration doc for `settings.local.json` creation, fields, and security expectations.
- Add a migration note mapping notebook functions to future Python modules/scripts.

## Baseline Completion Note

- This baseline covers plan objective `1.x` for `2026-03-19-01-05-00_documentation-baseline-and-migration-contract`.
- Next phase is objective `2.x`: target static architecture contract and pagination/output definitions.
