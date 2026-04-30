# SPEC-29 - CLI workflow updates

## Goal

Make the command-line workflow match the new user-facing config flow.

The main user path should be:

```bash
python main.py init-config
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
```

Secondary commands should support model registry refresh and inspection without requiring an existing config.

## Current CLI issues

Current `main.py list-models` requires:

```bash
python main.py list-models --config config.smoke.yaml
```

This is inconvenient because the new workflow needs model discovery before the user config exists.

## New commands

Add:

```bash
python main.py init-config
python main.py refresh-models
python main.py list-models
```

Keep existing commands:

```bash
python main.py validate-config --config ...
python main.py dry-run --config ...
python main.py run --config ...
python main.py collect --run ...
python main.py report --run ...
```

## `init-config`

Syntax:

```bash
python main.py init-config [--output config.yaml] [--force]
```

Behavior:

- refreshes `models.registry.yaml` from LM Studio;
- writes human-friendly `config.yaml`;
- refuses to overwrite existing config unless `--force` is passed.

Success output example:

```text
Model registry written: models.registry.yaml
Config written: config.yaml
Edit models/modes by commenting or uncommenting list items, then run:
  python main.py dry-run --config config.yaml
  python main.py run --config config.yaml
```

If LM Studio is not reachable:

```text
Failed to connect to LM Studio at http://localhost:1234/api/v1.
Start LM Studio server and run `python main.py init-config` again.
```

Do not create a misleading config with stale or empty models unless explicitly supported by a flag.

## `refresh-models`

Syntax:

```bash
python main.py refresh-models
```

Behavior:

- queries LM Studio;
- writes `models.registry.yaml`;
- prints count and a short summary.

Example:

```text
Model registry written: models.registry.yaml
Registry entries: 13
```

This command should not touch `config.yaml`.

## `list-models`

Change behavior so it no longer requires `--config`.

Syntax:

```bash
python main.py list-models
```

Remove the old `list-models --config ...` workflow from the project:

- CLI help should not advertise `--config` for `list-models`;
- docs and AGENTS instructions should stop using `python main.py list-models --config ...`;
- tests should be updated to the registry-based `list-models` behavior.

If an old `--config` argument is still accepted temporarily for parser simplicity, it must be ignored with a deprecation warning and must not be required. Prefer removing it fully in this spec if the change stays local and simple.

Default behavior:

- if `models.registry.yaml` exists, list registry labels;
- if it does not exist, print a helpful message:

```text
models.registry.yaml not found. Run `python main.py init-config` or `python main.py refresh-models` first.
```

Optional flag:

```bash
python main.py list-models --live
```

`--live` may query LM Studio directly, but it is not required for the first implementation.

Output should show user-facing labels, not only raw LM Studio ids:

```text
Available model labels:
- qwen3-vl-4b-q4_k_m
- qwen3-vl-8b-q4_k_m
- qwen3_5-9b-q4_k_m-think
- qwen3_5-9b-q4_k_m-no-think
```

Optional detailed output:

```bash
python main.py list-models --verbose
```

Can print id, reasoning, params, quant, and max context.

## `dry-run`

Keep syntax:

```bash
python main.py dry-run --config config.yaml
```

It must work with both simple and full configs.

Improve output if possible:

```text
Config: config.yaml
Images discovered: 1
Models selected: 2
Modes selected: 3
Total requests: 6

Models:
- qwen3-vl-4b-q4_k_m
- qwen3_5-9b-q4_k_m-no-think

Modes:
- ru_free
- ru_pool
- ru_pool_explained
```

The key value is `Total requests = images * models * modes`.

## `validate-config`

Keep syntax:

```bash
python main.py validate-config --config config.yaml
```

It must validate both simple and full configs.

For simple config, validation includes:

- required fields exist;
- image folder exists;
- model labels exist in registry;
- modes are known;
- pool files exist through expanded config;
- numeric values are valid.

## Error messages

Prefer actionable messages:

Bad:

```text
KeyError: qwen3-vl-4b
```

Good:

```text
Unknown model label: qwen3-vl-4b
Run `python main.py list-models` to see available labels.
```

Bad:

```text
Config section 'lmstudio' is missing
```

Good for simple config:

```text
This looks like a simple user config. Failed to expand it because models.registry.yaml is missing.
Run `python main.py init-config` first.
```

## Acceptance criteria

- `init-config` works without an existing config.
- `refresh-models` works without an existing config.
- `list-models` works from registry without `--config`.
- project docs no longer recommend or require `list-models --config`.
- `dry-run --config config.yaml` works with generated simple config.
- Old commands with `config.smoke.yaml` and `config.example.yaml` still work.
- CLI help text clearly shows the new workflow.

## Tests

Add CLI-level tests where practical:

- parser includes new commands;
- `init-config --output tmp/config.yaml` writes config;
- `init-config` refuses overwrite without `--force`;
- `list-models` reads registry;
- `dry-run` accepts simple config.

Use monkeypatching/fakes for LM Studio calls.

## Agent report

- Done: Added CLI workflow commands `refresh-models` and `list-models` (registry-based), removed `--config` requirement for listing labels, and improved dry-run output with total request count and selected models/modes.
- Changed files:
  - main.py
  - tests/test_cli_config_workflow.py
  - specs/29-cli-and-workflow.md
- Checks run:
  - python -m pytest -q tests/test_cli.py tests/test_cli_config_workflow.py tests/test_init_config.py tests/test_user_config.py tests/test_model_registry.py
- Notes:
  - `list-models` now reads `models.registry.yaml` and prints a helpful hint when it is missing.
