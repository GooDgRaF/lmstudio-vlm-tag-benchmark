# AGENTS.md

Instructions for coding agents working in this repository.

## Fast Onboarding

Read in this order:

1. `README.md`: project overview and quick start.
2. `PROJECT_GUIDE.md`: repository map, commands, outputs, and release checks.
3. `ARCHITECTURE.md`: technical contracts and v1 boundaries.
4. `prompts/pools/README.md`: when the task touches tag pools or pool validation.

Then run:

```bash
git status --short --branch
python main.py dry-run --config configs/config.smoke.yaml
python -m pytest -q
```

`configs/config.smoke.yaml` is the default quick runtime profile for agent work.

## Main Vertical Slice

Start with `src/runner.py` for end-to-end behavior:

```text
load config
expand simple config when needed
load tag pools
discover images
create results/<run_id>/
check LM Studio
unload existing loaded instances
load model
run image smoke-test
run model requests for image x mode
save raw JSON
normalize response
append summary.csv row
unload model
build report.html and diagnostics.html
```

If the task is to check whether the project works, use:

```bash
python main.py run --config configs/config.smoke.yaml
```

After a run, inspect:

```text
results/<run_id>/report.html
results/<run_id>/diagnostics.html
results/<run_id>/summary.csv
results/<run_id>/errors.log
```

## Module Map

```text
main.py                 CLI commands
src/config.py           config loading and dataclasses
src/user_config.py      simple config expansion
src/model_registry.py   LM Studio inventory and registry
src/lmstudio_client.py  LM Studio API wrapper
src/runner.py           sequential benchmark runner
src/storage.py          run folders, request ids, summary CSV
src/prompts.py          prompt construction
src/validator.py        response parsing and normalization
src/report.py           static HTML reports
src/collect.py          recomposition from request artifacts
src/tag_pools.py        pool loading and ID mapping
src/image_loader.py     image discovery and image IDs
src/diagnostics.py      GPU/context/token diagnostics
```

## Configs

- `config.yaml`: generated user-facing config; ignored by git.
- `configs/config.smoke.yaml`: quick verification profile.
- `configs/config.example.yaml`: full benchmark example with active model variants.
- `configs/config.rest-reasoning-smoke.yaml`: small reasoning profile check.

Prefer smoke config for agent work. Use the full example only when the user asks for a real benchmark or model comparison.

Before a full benchmark, run:

```bash
python main.py dry-run --config configs/config.example.yaml --limit 1
```

## LM Studio Notes

Default endpoints:

```yaml
lmstudio:
  api_base_url: "http://localhost:1234/api/v1"
  openai_base_url: "http://localhost:1234/v1"
```

The runner loads models through `/api/v1/models/load` and sends inference through REST Chat (`/api/v1/chat`).

The runner also performs best-effort unload cleanup:

- before each model load;
- after each model run when `runtime.unload_model_after_run: true`.

If multiple LM Studio instances appear loaded, inspect:

- `src/runner.py`;
- `src/lmstudio_client.py`;
- `results/<run_id>/models/<model_label>/load.json`;
- `results/<run_id>/errors.log`;
- `client.list_models()` output.

## Result Files

For debugging a run, inspect in this order:

1. `results/<run_id>/report.html`
2. `results/<run_id>/diagnostics.html`
3. `results/<run_id>/diagnostics.json`
4. `results/<run_id>/summary.csv`
5. `results/<run_id>/errors.log`
6. `results/<run_id>/models/<model_label>/load.json`
7. `results/<run_id>/models/<model_label>/smoke_test.json`
8. `results/<run_id>/requests/<request_id>/...`
9. `results/<run_id>/normalized/<request_id>.json`
10. `results/<run_id>/raw/<request_id>.json`

`pool_validation_failed` is benchmark signal unless the user explicitly asks to change pool behavior.

## Test Strategy

Default:

```bash
python -m pytest -q
```

Focused checks:

```bash
python -m pytest -q tests/test_runner.py
python -m pytest -q tests/test_lmstudio_client.py
python -m pytest -q tests/test_response_parsing.py
python -m pytest -q tests/test_report.py
python -m pytest -q tests/test_collect.py
```

Use `dry-run` after config or path changes:

```bash
python main.py dry-run --config configs/config.smoke.yaml
```

Use real `run` only when runtime behavior needs LM Studio verification.

## Editing Rules

- Keep v1 as a simple CLI benchmark.
- Prefer small local changes that match existing modules.
- Do not add GUI, web server, SQLite, async runner, plugin system, judge model, or non-LM-Studio backend unless the user asks.
- Do not delete or rename files in `ImgToTag/`; they are user data.
- Do not commit generated `results/*`; only `results/.gitkeep` is tracked.
- Do not commit generated model inventory; only `models/.gitkeep` is tracked.
- Do not change pool semantics casually.
- Update docs when behavior, CLI commands, config keys, output shape, or project structure changes.

## Common Tasks

### Change Smoke Image Count

Edit:

```yaml
limits:
  limit_images: 1
```

in `configs/config.smoke.yaml`.

### Add or Remove a Mode

Touchpoints:

- config `modes`;
- `src/prompts.py`;
- `src/validator.py`;
- tests for prompts and parsing;
- docs if user-facing.

### Add a Summary Column

Touchpoints:

- `src/storage.py`;
- `src/runner.py`;
- `src/collect.py`;
- `src/report.py` if visible in HTML;
- `tests/test_summary_csv.py`;
- `tests/test_report.py` if relevant.

### Change Report Layout

Touchpoints:

- `src/report.py`;
- `tests/test_report.py`;
- smoke run for visual sanity when behavior changes.

### Change LM Studio Payloads

Touchpoints:

- `src/lmstudio_client.py`;
- `tests/test_lmstudio_client.py`;
- `python main.py list-models` or `python main.py refresh-models` when LM Studio is running;
- smoke run if load/chat/unload behavior changed.

## Workflow Constraints

- Do not remove support for full configs under `configs/`.
- Selectable labels must remain directly under `models:` and modes under `modes:` in simple config.
- Do not put LM Studio URLs into generated `config.yaml`.
- Keep defaults `context_length = 8192` and `max_output_tokens = 4096`.
- Keep reasoning source of truth in registry field `reasoning`, not label suffix parsing.

## Useful Commands

```bash
rg --files
rg -n "run_benchmark|load_model|chat_completion|summary.csv|report.html" src tests
python main.py validate-config --config configs/config.smoke.yaml
python main.py dry-run --config configs/config.smoke.yaml
python -m pytest -q
```

## Encoding Hygiene

- Keep text files in UTF-8.
- In PowerShell, use explicit encoding when reading or writing text:
  - `Get-Content -Encoding UTF8 ...`
  - `Set-Content -Encoding utf8 ...`
- In Python, use explicit encoding such as `encoding="utf-8"`.
- Never use lossy conversion modes such as `errors="ignore"`.
- If a file shows mojibake markers, restore from a known-good revision or rewrite the damaged text directly in UTF-8.
