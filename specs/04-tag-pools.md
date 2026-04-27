# SPEC-04 — Tag pools

## Goal

Implement tag pool loading and validation for plain pools and ID-based explained pools.

After this stage, prompts and response normalization can rely on canonical pool objects.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Tag pools README](../pools/README.md)
- [Tag pool conversion report](../TAG_POOL_CONVERSION.md)
- [SPEC-02](./02-config-validation.md)

Expected files:

- `src/tag_pools.py`
- `tests/test_tag_pools.py`
- `pools/README.md`

## Tasks

- Load plain pools from:
  - `pools/ru_plain.txt`;
  - `pools/en_plain.txt`.
- Plain parser rules:
  - trim lines;
  - skip empty lines;
  - skip lines starting with `#`;
  - preserve original tag spelling.
- Load explained ID pools from:
  - `pools/ru_explained_ids.tsv`;
  - `pools/en_explained_ids.tsv`.
- TSV parser format: `id<TAB>tag<TAB>explanation`.
- Validate that IDs are unique.
- Validate that tags are non-empty.
- Generate prompt-ready explained pool text at runtime in the form `[ID] tag — explanation`.
- Provide helpers for mapping accepted IDs back to canonical tag names.
- Do not store generated prompt files in `pools/`.

## Check

Automated check:

```bash
pytest
```

Tests should cover:

- comments and empty lines are skipped in plain pools;
- plain tags preserve spelling;
- explained TSV entries parse correctly;
- duplicate explained IDs fail;
- ID-to-tag mapping works;
- generated prompt text contains IDs, tags, and explanations.

## Agent report

Fill this after implementation:

- Done: Implemented plain and explained-ID pool loaders, validation (duplicate IDs, empty tags), prompt-ready explained text generation, and ID-to-tag mapping helpers.
- Changed files: `src/tag_pools.py`, `tests/test_tag_pools.py`, `tests/helpers.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`.
- Notes: Prompt-ready explained text is generated in memory at runtime; no generated files are stored under `pools/`.
