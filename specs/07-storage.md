# SPEC-07 — Result storage

## Goal

Create the per-run result folder and save raw responses, normalized responses, run config, model metadata, and errors.

The runner will use this storage layer in later specs.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-06](./06-prompts-and-parsing.md)

Expected files:

- `src/storage.py`
- `tests/test_storage.py`
- `README.md`

## Tasks

- Create one run folder under `results/<run_id>/`.
- Use a stable and readable `run_id`, for example timestamp-based.
- Create subfolders:
  - `raw/`;
  - `normalized/`;
  - `assets/thumbs/`;
  - `models/`.
- Store per-model metadata under `models/<model_label>/`, for example:
  - `load.json`;
  - `smoke_test.json`;
  - `gpu_before_load.json`;
  - `gpu_after_load.json`.
- Save `run_config.yaml`.
- Save `models.json` with model entries used for the run.
- Save raw model outputs under `raw/`.
- Save normalized JSON outputs under `normalized/`.
- Save or append errors to `errors.log`.
- Define a deterministic `request_id` based on:
  - `model_label`;
  - `image_id`;
  - `mode`;
  - `prompt_version`;
  - `response_format_requested`.
- Keep `request_id` and all generated file names safe for Windows.
- Include request metadata in normalized JSON, including model identity, image identity, mode, `prompt_version`, and response format requested.
- Do not build `summary.csv` or `report.html` in this stage.

## Check

Automated check:

```bash
pytest
```

Tests should cover:

- run folder structure is created;
- model subfolders can be created safely;
- config and model metadata are saved;
- raw and normalized outputs are written;
- request IDs are deterministic;
- changing `prompt_version` changes the `request_id`;
- changing `response_format_requested` changes the `request_id`;
- generated filenames are Windows-safe;
- error log appends messages.

## Agent report

Fill this after implementation:

- Done: Implemented run storage with deterministic `run_id`/`request_id`, Windows-safe file naming, run folder structure, config/model metadata saving, raw/normalized result writes, error log append, and summary CSV bootstrap.
- Changed files: `src/storage.py`, `tests/test_storage.py`, `tests/test_summary_csv.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`.
- Notes: `request_id` depends on `model_label`, `image_id`, `mode`, `prompt_version`, and `response_format_requested`.
