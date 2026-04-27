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

If LM Studio is available and at least one image exists, run a smoke benchmark:

```bash
python main.py run --config config.example.yaml --limit 1
python main.py report --run results/<run_id>
```

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
