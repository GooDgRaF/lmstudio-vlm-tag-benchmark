# Project Guide

Operational guide for running and maintaining the local VLM image tagging benchmark.

For technical contracts, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Daily Workflow

```bash
python main.py init-config
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
```

What happens:

1. `init-config` refreshes LM Studio model inventory and writes `config.yaml`.
2. `dry-run` validates config and input discovery without inference.
3. `run` sends real requests to LM Studio and writes artifacts under `results/<run_id>/`.

## Configs

Primary user config:

```text
config.yaml
```

Generated local model files:

```text
models.registry.yaml
models/lmstudio-models.raw.json
models/models.active.yaml
models/models.excluded.yaml
```

Advanced full-shape configs:

```text
configs/config.smoke.yaml
configs/config.example.yaml
configs/config.rest-reasoning-smoke.yaml
```

Use `config.yaml` for normal runs. Use `configs/config.smoke.yaml` for quick development checks.

## CLI Commands

Model inventory and setup:

```bash
python main.py init-config
python main.py refresh-models
python main.py list-models
python main.py list-models --verbose
```

Validation and execution:

```bash
python main.py validate-config --config config.yaml
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
python main.py run --config config.yaml --run-id my-run-001
python main.py run --config config.yaml --run-id my-run-001 --force-lock
```

Rebuild derived outputs:

```bash
python main.py collect --run results/<run_id> --write-reports
python main.py report --run results/<run_id>
```

## Repository Map

```text
README.md             project overview
PROJECT_GUIDE.md      operational guide
ARCHITECTURE.md       technical architecture contract
AGENTS.md             coding-agent rules
main.py               CLI entrypoint
src/                  application code
tests/                pytest suite
configs/              advanced full-shape configs
prompts/              prompt headers and tag pools
models/               generated model inventory snapshots
results/              generated benchmark artifacts
user_manual.md        short user manual
```

`models/` and `results/` are runtime folders. Only their `.gitkeep` files are tracked.

## Input Images

The input folder is configured by `images_folder` in `config.yaml`.

Supported extensions:

```text
.jpg, .jpeg, .png, .webp, .bmp
```

`recursive` controls nested scanning. CLI `--limit` overrides the config image limit for one run.

Image discovery is implemented in `src/image_loader.py`.

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

Default prompt and pool files live under `prompts/`:

```text
prompts/ru_free.txt
prompts/ru_pool.txt
prompts/ru_pool_explained.txt
prompts/en_free.txt
prompts/en_pool.txt
prompts/en_pool_explained.txt
prompts/pools/ru_plain.txt
prompts/pools/en_plain.txt
prompts/pools/ru_explained_ids.tsv
prompts/pools/en_explained_ids.tsv
```

Pool violations are recorded as benchmark signal. They are not automatically code bugs.

## Results

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

1. `report.html`: answer matrix.
2. `diagnostics.html`: technical metrics and request diagnostics.
3. `summary.csv`: spreadsheet-friendly table.
4. `errors.log`: runner events and failures.
5. `requests/<request_id>/...`: canonical per-request artifacts.

`summary.csv`, `diagnostics.json`, `report.html`, and `diagnostics.html` are derived files and can be rebuilt with `collect`.

## Code Map

```text
src/config.py           config loading and style detection
src/user_config.py      simple profile expansion
src/model_registry.py   model inventory and registry generation
src/lmstudio_client.py  LM Studio API wrapper
src/runner.py           sequential benchmark execution
src/storage.py          run artifact layout and summary CSV
src/prompts.py          prompt construction
src/validator.py        response parsing and normalization
src/report.py           static HTML reports
src/collect.py          recomposition from request artifacts
src/diagnostics.py      runtime diagnostics helpers
src/tag_pools.py        pool loading and ID mapping
src/image_loader.py     image discovery and IDs
```

## Tests

Run all tests:

```bash
python -m pytest -q
```

Useful focused checks:

```bash
python -m pytest -q tests/test_model_registry.py
python -m pytest -q tests/test_user_config.py
python -m pytest -q tests/test_runner.py
python -m pytest -q tests/test_report.py
python -m pytest -q tests/test_collect.py
```

## Release Check

Before publishing:

```bash
git status --short --branch
python main.py validate-config --config configs/config.smoke.yaml
python main.py dry-run --config configs/config.smoke.yaml
python main.py validate-config --config configs/config.example.yaml
python main.py dry-run --config configs/config.example.yaml --limit 1
python -m pytest -q
```

Run a real LM Studio smoke benchmark only when runtime behavior needs verification.

## Maintenance Rules

- Keep `config.yaml` as the primary user workflow.
- Keep LM Studio REST Chat as the primary inference transport.
- Keep runtime artifacts deterministic and rebuildable.
- Avoid heavyweight runtime dependencies unless the project scope changes.
