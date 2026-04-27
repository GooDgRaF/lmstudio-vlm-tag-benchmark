# SPEC-01 — Project skeleton

## Goal

Create the minimal Python project structure for the local VLM image tagger benchmark.

After this stage, the project should have a package, a CLI entry point, and a minimal config-loading command. No real LM Studio calls or image processing are required yet.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [Specs workflow](./README.md)

Expected files:

- `main.py`
- `src/config.py`
- `tests/test_cli.py`
- `requirements.txt`

## Tasks

- Create the minimal source and test layout.
- Keep the architecture's flat `src/*.py` module layout for v1.
- Add a CLI entry through `main.py`.
- Add a command that accepts `--config config.example.yaml`.
- Load the YAML config file.
- Return a clear error if the config file does not exist.
- Print a short success message when the config is loaded.
- Add minimal CLI tests.
- Do not connect to LM Studio in this stage.
- Do not process images in this stage.

## Check

Manual check:

```bash
python main.py validate-config --config config.example.yaml
```

Expected result:

```text
Config loaded: config.example.yaml
```

Automated check:

```bash
pytest
```

Tests should check:

- CLI succeeds with an existing config file.
- CLI fails with a clear error for a missing config file.

## Agent report

Fill this after implementation:

- Done: Created project skeleton with `main.py`, package layout, config loading, and `validate-config` CLI command.
- Changed files: `main.py`, `src/__init__.py`, `src/config.py`, `tests/test_cli.py`, `tests/helpers.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`; `python main.py validate-config --config config.example.yaml`.
- Notes: Config loading fails early with clear `ConfigError` for missing file or invalid section shape.
