# Project Guide

This document is the operational map of the repository:
- where things are;
- which command to run for each task;
- where to inspect outputs and diagnostics.

`ARCHITECTURE.md` is the technical contract.
This guide is workflow-first.

## Quick Path (Daily Workflow)

```bash
python main.py init-config
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
```

What this does:
1. `init-config` refreshes model registry from LM Studio and generates user-editable `config.yaml`.
2. `dry-run` validates and prints planned request counts (no model inference).
3. `run` performs real LM Studio requests and writes artifacts to `results/<run_id>/`.

## Config Model

The project uses two config layers:

1. `config.yaml` (simple user profile):
- edited directly by user;
- model labels and modes are selected by comment/uncomment list items.

2. Resolved internal full config:
- produced automatically from user profile;
- consumed by `BenchmarkConfig` and the runner.

### Key files

```text
config.yaml                      user-edited simple config
models.registry.yaml             generated model label registry
models/lmstudio-models.raw.json  raw LM Studio model inventory
models/models.active.yaml        generated active VLM candidates
models/models.excluded.yaml      generated excluded candidates with reasons
configs/config.example.yaml      advanced full-shape example
configs/config.smoke.yaml        advanced smoke full-shape profile
```

## CLI Commands

### Initialization and model inventory

```bash
python main.py init-config
python main.py refresh-models
python main.py list-models
```

When to use:
- `init-config`: first setup or regenerate `config.yaml` + registry.
- `refresh-models`: refresh only model inventory/registry.
- `list-models`: print registry labels available for `config.yaml`.

### Validation and execution

```bash
python main.py validate-config --config config.yaml
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
python main.py run --config config.yaml --run-id my-run-001
python main.py run --config config.yaml --run-id my-run-001 --force-lock
```

### Rebuild from artifacts

```bash
python main.py collect --run results/<run_id> --write-reports
python main.py report --run results/<run_id>
```

## Repository Map

```text
README.md             entry overview
PROJECT_GUIDE.md      operational workflow guide (this file)
ARCHITECTURE.md       technical architecture contract
AGENTS.md             coding-agent rules
main.py               CLI entrypoint
configs/              advanced full-shape configs
models/               generated model inventory snapshots
pools/                tag pools
results/              runtime artifacts
specs/                implementation specs history
src/                  application code
tests/                pytest test suite
user_manual.md        short user manual
```

## Input Images

Default user path is set in `config.yaml` via `images_folder`.

Notes:
- supported extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`;
- `recursive` controls nested scanning;
- `--limit` in CLI overrides config image limit for that run.

Image discovery logic lives in `src/image_loader.py`.

## Modes and Pools

Supported modes:

```text
ru_free
ru_pool
ru_pool_explained
en_free
en_pool
en_pool_explained
```

Pool files:

```text
pools/ru_plain.txt
pools/en_plain.txt
pools/ru_explained_ids.tsv
pools/en_explained_ids.tsv
```

Rules:
- free/plain pool modes use line tags by default;
- explained modes use line IDs;
- pool violations are quality signal and are recorded in outputs.

## Results and Where to Look

Each run creates:

```text
results/<run_id>/
  run_config.yaml
  models.json
  run_manifest.json
  run_state.json
  run_complete.json
  summary.csv
  report.html
  diagnostics.html
  diagnostics.json
  errors.log
  requests/
  raw/
  normalized/
  assets/thumbs/
```

Recommended inspection order:
1. `report.html` (answer matrix)
2. `diagnostics.html` (technical metrics)
3. `summary.csv`
4. `errors.log`
5. `requests/<request_id>/...` for per-request truth

`requests/<request_id>/...` is the canonical source.
Other summaries/reports can be rebuilt.

## Advanced Profiles (Optional)

These are for internal/extended workflows, not default user entry:
- `configs/config.smoke.yaml`
- `configs/config.example.yaml`
- `configs/config.rest-reasoning-smoke.yaml`

Useful commands:

```bash
python main.py validate-config --config configs/config.smoke.yaml
python main.py dry-run --config configs/config.smoke.yaml
python main.py run --config configs/config.smoke.yaml
```

## Code Map

```text
src/config.py           config loading + style detection
src/user_config.py      simple profile expansion to full runtime config
src/model_registry.py   model inventory refresh + registry generation/resolution
src/lmstudio_client.py  LM Studio API wrapper
src/runner.py           sequential benchmark execution
src/storage.py          run artifact layout + CSV writing
src/prompts.py          prompt construction and format selection
src/validator.py        response parsing + normalization + semantic checks
src/report.py           static HTML reports
src/collect.py          recomposition from request artifacts
src/diagnostics.py      runtime diagnostics helpers
src/tag_pools.py        pool loading and ID mapping
src/image_loader.py     image discovery and IDs
```

## Test Strategy

Run all:

```bash
python -m pytest -q
```

Focused suites:

```bash
python -m pytest -q tests/test_model_registry.py
python -m pytest -q tests/test_user_config.py
python -m pytest -q tests/test_runner.py
python -m pytest -q tests/test_report.py
python -m pytest -q tests/test_collect.py
```

## Change Playbooks

### Change model inventory behavior
Touch:
- `src/model_registry.py`
- `src/init_config.py`
- `tests/test_model_registry.py`
- `tests/test_init_config.py`
- `tests/test_cli_config_workflow.py`

### Change response parsing behavior
Touch:
- `src/validator.py`
- `src/report.py` (if rendering changes)
- `tests/test_response_parsing.py`
- `tests/test_report.py`

### Change report layout/metrics
Touch:
- `src/report.py`
- `tests/test_report.py`

### Change run artifact schema
Touch:
- `src/storage.py`
- `src/runner.py`
- `src/collect.py`
- `tests/test_storage.py`
- `tests/test_collect.py`

## Keep It Simple

For release stability:
- keep CLI-first architecture;
- keep `config.yaml` workflow primary;
- avoid introducing heavyweight runtime dependencies;
- preserve deterministic artifact contracts.
