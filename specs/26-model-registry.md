# SPEC-26 - Auto-generated model registry

## Goal

Add an automatically generated model registry based on the LM Studio REST model list.

The user should not manually maintain full model entries in `config.yaml`. The program should query LM Studio, derive stable project labels, and store enough metadata to expand user-selected labels into the current internal `ModelConfig` entries.

## Current state

The current full configs contain complete model objects directly in YAML:

```yaml
models:
  - id: "qwen/qwen3.5-9b@q4_k_m"
    base_model_id: "qwen/qwen3.5-9b"
    label: "qwen3_5-9b-q4_k_m-no-think"
    reasoning: "off"
```

`src/config.py` currently parses these objects into `ModelConfig`.

The runner already uses `model.reasoning` and passes it to `LMStudioClient.chat_rest(...)`, where only `"on"` and `"off"` become an explicit REST `reasoning` field. `"default"` omits the field.

## New files

Add/update generated model inventory files:

```text
models/lmstudio-models.raw.json
models/models.active.yaml
models/models.excluded.yaml
models.registry.yaml
```

`models.registry.yaml` should stay in the repository root because it is the user-facing generated label registry used by `config.yaml` expansion.

The existing `models/` directory remains the machine-readable LM Studio inventory area:

- `models/lmstudio-models.raw.json` is the latest raw LM Studio model list;
- `models/models.active.yaml` is the auto-selected benchmark candidate list;
- `models/models.excluded.yaml` is the auto-generated exclusion list with reasons.

These three files should no longer be treated as manually maintained project data. `refresh-models` should regenerate them from the current LM Studio model list.

## New module

Add:

```text
src/model_registry.py
```

Responsibilities:

- query LM Studio model list;
- normalize raw LM Studio model records;
- write raw, active, and excluded model inventory files under `models/`;
- generate project model entries;
- write `models.registry.yaml`;
- load `models.registry.yaml`;
- resolve user-selected labels into full internal model dicts;
- provide a printable list of labels.

## LM Studio source

Use the existing client method:

```python
LMStudioClient.list_models()
```

For registry refresh, do not require a user config. Use hardcoded project defaults:

```python
DEFAULT_LMSTUDIO_HOST = "http://localhost:1234"
DEFAULT_API_BASE_URL = "http://localhost:1234/api/v1"
DEFAULT_OPENAI_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_TIMEOUT_SEC = 180
```

This is important: `init-config` and `refresh-models` should work before `config.yaml` exists.

## Generated model inventory

Registry refresh should query information about all models exposed by LM Studio, then generate:

```text
models/lmstudio-models.raw.json
models/models.active.yaml
models/models.excluded.yaml
models.registry.yaml
```

Selection rule for `models/models.active.yaml`:

- include models that are explicitly `type: llm` or otherwise look like chat/LLM models;
- include only models with `vision: true`;
- include only models whose parameter count is below 10B;
- expand every available model variant into a separate active entry.

Exclusion rule for `models/models.excluded.yaml`:

- write every non-active model with a short reason, for example `not_vision`, `not_llm`, `params_over_10b`, or `missing_model_id`.

Parameter parsing is best effort. Accept common LM Studio values such as `4B`, `4.6B`, `9B`, and `35B`. If the parameter count is missing or cannot be parsed, prefer exclusion with reason `unknown_params` rather than silently adding a large model.

The root `models.registry.yaml` is generated from the active list, optionally enriched by live LM Studio metadata. It is the source used to resolve user-facing labels in `config.yaml`.

## Raw model field extraction

LM Studio payload shape may vary. Extract model id candidates defensively from each raw model object.

Try, in order:

```python
raw.get("id")
raw.get("model_id")
raw.get("selected_variant")
raw.get("selectedVariant")
raw.get("key")
raw.get("modelKey")
```

If a record has a list of variants, expanding variants is mandatory. Each variant should become a separate candidate model entry. If a record has no variants, use the best available id above and keep enough source metadata for debugging.

Store the raw object or selected raw fields under `raw` only if it does not make the file too noisy. The human-facing config must not depend on raw structure.

## Registry format

Write YAML like this:

```yaml
generated_at: "2026-04-30T09:00:00"
source: "lmstudio"
api_base_url: "http://localhost:1234/api/v1"

models:
  - id: "qwen/qwen3-vl-4b@q4_k_m"
    base_model_id: "qwen/qwen3-vl-4b"
    label: "qwen3-vl-4b-q4_k_m"
    reasoning: "default"
    display_name: "Qwen3 VL 4B"
    params: "4B"
    architecture: "qwen3vl"
    quant: "Q4_K_M"
    quant_bits: 4
    size_bytes: 3333641502
    max_context_length: 262144

  - id: "qwen/qwen3.5-9b@q4_k_m"
    base_model_id: "qwen/qwen3.5-9b"
    label: "qwen3_5-9b-q4_k_m-think"
    reasoning: "on"
    display_name: "Qwen3.5 9B"
    params: "9B"
    architecture: "qwen35"
    quant: "Q4_K_M"
    quant_bits: 4
    size_bytes: 6548927017
    max_context_length: 262144

  - id: "qwen/qwen3.5-9b@q4_k_m"
    base_model_id: "qwen/qwen3.5-9b"
    label: "qwen3_5-9b-q4_k_m-no-think"
    reasoning: "off"
    display_name: "Qwen3.5 9B"
    params: "9B"
    architecture: "qwen35"
    quant: "Q4_K_M"
    quant_bits: 4
    size_bytes: 6548927017
    max_context_length: 262144
```

The registry is generated, but it should still be readable and diff-friendly.

## Label generation

The label is the stable user-facing key.

Base rule:

```text
<base-name>-<quant>
```

Then append reasoning suffix only for models that support the project-level reasoning toggle:

```text
<base-name>-<quant>-think
<base-name>-<quant>-no-think
```

Rules:

- remove organization prefix: `qwen/qwen3.5-9b` -> `qwen3.5-9b`;
- replace dots with underscores in labels: `qwen3.5-9b` -> `qwen3_5-9b`;
- keep hyphens;
- lowercase quant in labels if the current project convention uses lowercase: `Q4_K_M` -> `q4_k_m`;
- keep the full model `id` unchanged internally.

Examples:

```text
qwen/qwen3-vl-4b@q4_k_m       -> qwen3-vl-4b-q4_k_m
qwen/qwen3.5-9b@q4_k_m        -> qwen3_5-9b-q4_k_m-think / qwen3_5-9b-q4_k_m-no-think
google/gemma-4-e4b@q6_k       -> gemma-4-e4b-q6_k-think / gemma-4-e4b-q6_k-no-think
```

## Reasoning profile rules

Do not rely on the label suffix as the source of truth. The source of truth is the registry entry field:

```yaml
reasoning: "on"
```

The suffix is only the naming convention used to make labels readable.

Preferred source:

1. If LM Studio exposes `capabilities.reasoning.allowed_options`, use it.
2. If `allowed_options` contains both `"on"` and `"off"`, generate two registry entries:

```yaml
reasoning: "on"   # label suffix -think
reasoning: "off"  # label suffix -no-think
```

3. If the capability metadata is absent, use a conservative fallback family table:

```python
REASONING_TOGGLE_FAMILIES = [
    "qwen3.5",
    "qwen3_5",
    "gemma-4",
    "gemma4",
]
```

If a raw/base model matches this fallback table, generate the same two entries:

```yaml
reasoning: "on"   # label suffix -think
reasoning: "off"  # label suffix -no-think
```

Otherwise generate one entry:

```yaml
reasoning: "default"
```

This matches the current real config pattern:

```yaml
- id: "qwen/qwen3.5-9b@q4_k_m"
  base_model_id: "qwen/qwen3.5-9b"
  label: "qwen3_5-9b-q4_k_m-no-think"
  reasoning: "off"
```

## Metadata extraction

Best effort only. Missing metadata must not block registry generation.

Extract when available:

- `display_name`
- `params`
- `architecture`
- `quant`
- `quant_bits`
- `size_bytes`
- `max_context_length`

If unavailable, set `null` or omit optional fields consistently. The config expander must tolerate missing optional metadata.

## Filtering

The registry refresh must build the active registry from vision-capable LLMs below 10B.

Initial practical rule:

- include entries where the record appears to be an LLM/chat model;
- require `vision: true`;
- if `type` is explicitly present and is not `llm`, exclude it;
- require a parseable parameter count below 10B;
- write excluded records to `models/models.excluded.yaml` with reason codes.

This intentionally keeps `init-config` focused on realistic local benchmark candidates instead of presenting every downloaded LM Studio model.

## Collision handling

Labels must be unique.

If generated labels collide:

1. keep the first label unchanged;
2. append a short deterministic suffix to later labels, based on a hash of the full model id:

```text
gemma-4-e4b-q6_k-a17f2c
```

Do not silently overwrite registry entries.

## API functions

Implement at least:

```python
def refresh_registry(output_path: Path = Path("models.registry.yaml")) -> ModelRegistry: ...
def load_registry(path: Path = Path("models.registry.yaml")) -> ModelRegistry: ...
def resolve_model_labels(labels: list[str], registry: ModelRegistry) -> list[dict[str, Any]]: ...
def list_registry_labels(registry: ModelRegistry) -> list[str]: ...
```

`resolve_model_labels` must raise a clear error for unknown labels and suggest the closest available labels if possible.

Example error:

```text
Unknown model label: qwen3-vl-4b-q4
Run `python main.py init-config --force` to refresh config, or use one of:
- qwen3-vl-4b-q4_k_m
- qwen3-vl-4b-q8_0
```

## Acceptance criteria

- Running the registry refresh without an existing user config works.
- `models/lmstudio-models.raw.json`, `models/models.active.yaml`, and `models/models.excluded.yaml` are regenerated from LM Studio list data.
- `models.registry.yaml` is generated from the active model inventory.
- Reasoning-capable models produce both `-think` and `-no-think` entries based on LM Studio capabilities when available.
- Every LM Studio variant in an active model record becomes a separate registry label.
- Each registry entry has a unique `label`.
- Registry labels can be resolved into the same model dict shape currently used by `src/config.py`.
- Existing full configs still work unchanged.

## Tests

Add unit tests for:

- label generation from representative ids;
- dot-to-underscore conversion;
- quant parsing;
- parameter filtering below 10B;
- mandatory variant expansion;
- active/excluded file generation;
- reasoning profile expansion;
- collision handling;
- unknown-label error;
- registry write/load roundtrip.

Use fake LM Studio model payloads. Do not require a real LM Studio server in tests.

## Agent report

- Done: Added model registry module with LM Studio inventory refresh, active/excluded filtering, variant expansion, reasoning-profile expansion, unique label handling, registry load/list/resolve helpers, and unknown-label suggestions.
- Changed files:
  - src/model_registry.py
  - tests/test_model_registry.py
  - specs/26-model-registry.md
- Checks run:
  - python -m pytest -q tests/test_model_registry.py
- Notes:
  - Parameter parsing is best-effort from both model fields and model id suffixes like `8b`.
