# SPEC-27 - `init-config`: generate human-friendly `config.yaml`

## Goal

Add one command that creates a user-friendly `config.yaml` from the current LM Studio models.

The user workflow should be:

```bash
python main.py init-config
```

Then open `config.yaml`, comment/uncomment models and modes, and run:

```bash
python main.py run --config config.yaml
```

## Command behavior

Add CLI command:

```bash
python main.py init-config
```

Responsibilities:

1. Query LM Studio.
2. Generate/update `models/lmstudio-models.raw.json`, `models/models.active.yaml`, `models/models.excluded.yaml`, and `models.registry.yaml`.
3. Generate `config.yaml`.
4. Put all selectable model labels directly under the `models:` key.
5. Put all selectable modes directly under the `modes:` key.
6. Leave only a safe minimal subset uncommented.

## No copy-paste UX rule

This is the core UX requirement:

> All selectable model labels must be placed directly under `models:`. All selectable modes must be placed directly under `modes:`. The user should only comment or uncomment YAML list items. The user should not copy values from a reference section into the active section.

Correct:

```yaml
models:
  - "qwen3-vl-4b-q4_k_m"
  # - "qwen3-vl-8b-q4_k_m"
  # - "qwen3_5-9b-q4_k_m-think"
  # - "qwen3_5-9b-q4_k_m-no-think"

modes:
  - "ru_free"
  # - "ru_pool"
  # - "ru_pool_explained"
  # - "en_free"
  # - "en_pool"
  # - "en_pool_explained"
```

Incorrect:

```yaml
models:
  - "qwen3-vl-4b-q4_k_m"

# Available models:
# - "qwen3-vl-8b-q4_k_m"
```

The second version forces copy-paste and is not acceptable for this feature.

## Generated `config.yaml` format

Generate this style:

```yaml
# Human-friendly config for Local VLM Image Tagger Benchmark.
# Edit this file, then run:
#   python main.py dry-run --config config.yaml
#   python main.py run --config config.yaml

images_folder: "ImgToTag"

# 1 = quick smoke test
# null = all images
limit_images: 1

models:
  - "qwen3-vl-4b-q4_k_m"
  # - "qwen3-vl-8b-q4_k_m"
  # - "qwen3-vl-4b-q8_0"
  # - "qwen3_5-9b-q4_k_m-think"
  # - "qwen3_5-9b-q4_k_m-no-think"

modes:
  - "ru_free"
  # - "ru_pool"
  # - "ru_pool_explained"
  # - "en_free"
  # - "en_pool"
  # - "en_pool_explained"

output_folder: "results"

# Optional settings. Defaults are usually fine.
# context_length: 8192
# max_output_tokens: 4096
# temperature: 0.0
# recursive: false
```

The active lines form a valid simple config.

## User-editable fields

Required active fields:

```yaml
images_folder: "..."
models:
  - "..."
modes:
  - "..."
```

Optional active fields:

```yaml
limit_images: 1
output_folder: "results"
context_length: 8192
max_output_tokens: 4096
temperature: 0.0
recursive: false
```

The optional generation/load fields should remain commented in the generated file unless there is a strong reason to show them active.

## Defaults

The program must use these defaults when user config omits optional fields:

```text
limit_images = 1 for generated config, but internal default may be null if key is absent
output_folder = "results"
context_length = 8192
max_output_tokens = 4096
temperature = 0.0
top_p = 1.0
recursive = false
extensions = [.jpg, .jpeg, .png, .webp, .bmp]
```

Important: `max_output_tokens` should map to internal `generation.max_tokens`. Keep current 4096 default. Do not use 256.

## Choosing the default active model

Use this order:

1. Prefer a label containing `qwen3-vl-4b` and `q4_k_m`.
2. Else prefer the first label that looks vision-capable and under 10B, if metadata is available.
3. Else prefer the first registry label.
4. If no models are found, generate a config with commented instructions and an empty `models:` list.

Example no-model fallback:

```yaml
models:
  # No LM Studio models were found.
  # Start the LM Studio server and run:
  #   python main.py init-config --force
```

## Choosing the default active mode

Always enable only:

```yaml
modes:
  - "ru_free"
```

Comment all other modes.

Reason: this is the smallest useful smoke test and avoids accidentally running all six modes.

## Existing file behavior

If `config.yaml` already exists, do not overwrite it silently.

Default behavior:

```text
Error: config.yaml already exists. Use --force to overwrite or --output <path> to write another file.
```

Support:

```bash
python main.py init-config --force
python main.py init-config --output config.generated.yaml
```

`--force` should overwrite both generated config and registry only if needed. It is acceptable for registry refresh to always update `models.registry.yaml`, but the command must not destroy a hand-edited `config.yaml` without explicit user intent.

## Paths

Default `images_folder` should be relative:

```text
ImgToTag
```

Resolve relative paths against the project root/current working directory used to run the CLI. Avoid writing absolute paths into generated `config.yaml`, especially paths with non-ASCII characters that are easy to corrupt in terminals or editors.

Allow an override flag:

```bash
python main.py init-config --images-folder ImgToTag
```

But do not require this flag for the first implementation.

## Formatting requirements

- Preserve quotes around model labels and mode names.
- Use CRLF or LF consistently; LF is fine.
- Use UTF-8.
- Do not rely on YAML dumper for the whole file, because comments and commented list items are important.
- Generate the file from a small template string or explicit line writer.

## Acceptance criteria

- `python main.py init-config` creates the generated model inventory files, `models.registry.yaml`, and `config.yaml`.
- `config.yaml` is valid YAML after generation.
- All available model labels are under `models:` with one active and the rest commented.
- All available modes are under `modes:` with `ru_free` active and the rest commented.
- `config.yaml` can be passed to `dry-run` after implementing SPEC-28.
- Existing config is not overwritten without `--force`.

## Tests

Add tests for:

- generated config is valid YAML;
- model labels appear under `models:` and not in a separate reference section;
- modes appear under `modes:` and not in a separate reference section;
- only one default model is active;
- only `ru_free` is active by default;
- `--force` overwrite behavior;
- no-model fallback.

Use fake registry data; do not require real LM Studio.

## Agent report

- Done: Added `init-config` command that refreshes model registry and generates human-friendly `config.yaml` with inline selectable model/mode lists and overwrite protection.
- Changed files:
  - main.py
  - src/init_config.py
  - tests/test_init_config.py
  - specs/27-init-config.md
- Checks run:
  - python -m pytest -q tests/test_init_config.py tests/test_model_registry.py
- Notes:
  - Generated config keeps one active model and only `ru_free` active by default.
