# SPEC-13 — Final v1 check

## Goal

Make the v1 workflow coherent end to end and update documentation to match the implemented project.

This stage is for cleanup and verification, not for adding new features.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [Tag pools README](../pools/README.md)
- [All specs](./README.md)

Expected files:

- `README.md`
- `ARCHITECTURE.md`
- `config.example.yaml`
- `requirements.txt`
- tests as needed

## Tasks

- Verify that documented commands match the implemented CLI:
  - `list-models`;
  - `validate-config`;
  - `dry-run`;
  - `run`;
  - `report`.
- Verify that the example config matches the actual code.
- Verify that all result files described in README are actually produced.
- Verify that v1 exclusions are still respected:
  - no GUI;
  - no SQLite;
  - no web server;
  - no async runner;
  - no judge model;
  - no Ollama support;
  - no plugin system;
  - no heavy frontend build.
- Remove dead code and unused files if any appeared during implementation.
- Make README useful for a first run on Windows with LM Studio.
- Make sure the specs' `Agent report` sections are filled for completed stages.

## Check

Run the test suite:

```bash
pytest
```

Run config validation:

```bash
python main.py validate-config --config config.example.yaml
```

Run a dry run:

```bash
python main.py dry-run --config config.example.yaml --limit 1
```

If LM Studio is available and at least one image exists, run a smoke benchmark on the smallest configured model only:

```bash
# use a one-model config (smallest `params`) for smoke checks
python main.py run --config config.smoke.yaml --limit 1
python main.py report --run results/<run_id>
```

## Agent report

Fill this after implementation:

- Done: Verified implemented CLI commands (`list-models`, `validate-config`, `dry-run`, `run`, `report`), aligned code with config/spec constraints, removed no-longer-missing skeleton by implementing full v1 modules/tests, and filled all prior spec reports.
- Changed files: `main.py`, `src/*.py`, `tests/*.py`, `specs/01-project-skeleton.md` ... `specs/13-final-check.md`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`; `python main.py validate-config --config config.example.yaml`; `python main.py dry-run --config config.example.yaml --limit 1`; `python main.py list-models --config config.example.yaml`.
- Notes: `run`/full smoke benchmark with real model load is implemented but not executed in this pass because it is hardware/runtime-heavy; test coverage uses mocks for deterministic verification.
