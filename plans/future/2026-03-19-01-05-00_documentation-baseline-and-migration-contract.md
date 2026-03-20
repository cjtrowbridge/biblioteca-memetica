---
plan_id: 2026-03-19-01-05-00_documentation-baseline-and-migration-contract
title: Documentation Baseline and Migration Contract
summary: Audit existing repo documentation and establish an authoritative migration contract for the static-site and Python build transition.
status: future
created_at: 2026-03-19-01-05-00
---

# Documentation Baseline and Migration Contract

Key: `[ ]` pending task, `[x]` completed task, `[?]` needs validation, `[-]` closed task

- [x] 1. Produce a current-state documentation baseline for the repository.
  - [x] 1.1 Inventory current documented behavior in `README.md`, notebooks, and generated artifacts.
    - [x] 1.1.1 Capture source-of-truth inputs/outputs for `ai.ipynb` and `build.ipynb`.
      - [x] 1.1.1.1 Record artifact map (`memes.json`, per-meme pages, category indexes, root index, sidebar, layout dependencies).
  - [x] 1.2 Identify inconsistencies and technical debt in existing docs.
    - [x] 1.2.1 Document accuracy gaps and encoding/readability issues in root docs.
      - [x] 1.2.1.1 Propose exact doc fixes and required structural changes.

- [ ] 2. Define the target architecture contract for static HTML generation.
  - [ ] 2.1 Specify required outputs for the new static model.
    - [ ] 2.1.1 Define per-meme static pages and per-topic paginated indexes.
      - [ ] 2.1.1.1 Define homepage all-topics pagination and canonical URL rules.
  - [ ] 2.2 Define metadata and summary lifecycle requirements.
    - [ ] 2.2.1 Specify required metadata sidecars and fallback behavior.
      - [ ] 2.2.1.1 Define migration rules from legacy summary formats to new model output conventions.

- [ ] 3. Publish and enforce migration documentation updates.
  - [ ] 3.1 Update root docs to describe new script-driven workflow.
    - [ ] 3.1.1 Replace notebook-first instructions with script-first command paths.
      - [ ] 3.1.1.1 Include operational notes for local-only meme assets and ignored settings files.
  - [ ] 3.2 Add explicit verification checklist for docs-to-code parity.
    - [ ] 3.2.1 Include regeneration commands and expected outputs.
      - [ ] 3.2.1.1 Validate that examples, paths, and filenames match implemented scripts.

