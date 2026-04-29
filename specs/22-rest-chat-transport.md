# SPEC-22 — REST Chat transport and response normalization

## Goal

Replace the benchmark inference transport layer with LM Studio REST Chat while keeping the rest of the benchmark pipeline stable.

This spec is intentionally limited to the low-level transport contract:

- configuration fields needed to call REST Chat;
- REST request construction;
- REST response normalization;
- usage/token diagnostics extraction from REST stats;
- tests that prove final answer text and reasoning text are separated.

After this spec, code should be able to call LM Studio REST Chat and produce a normalized internal response object. The runner does not need to be fully migrated in this spec except for a minimal smoke helper if needed by tests.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [Specs workflow](./README.md)

Expected files to change:

- `src/config.py`
- `src/validator.py`
- `src/lmstudio_client.py`
- `src/diagnostics.py`
- `config.example.yaml`
- `config.smoke.yaml`
- `tests/test_config.py`
- `tests/test_validator.py`
- `tests/test_lmstudio_client.py`
- `tests/test_diagnostics.py`

Do not change in this spec unless absolutely necessary:

- `src/runner.py`
- `src/storage.py`
- `src/collect.py`
- `src/report.py`

Those files are covered by later specs.

## Background

The project currently uses LM Studio through the OpenAI-compatible endpoint:

```text
POST /v1/chat/completions
```

The new primary transport must use LM Studio REST Chat:

```text
POST /api/v1/chat
```

REST Chat matters because it returns final answer blocks separately from reasoning blocks. The benchmark must parse only the final answer as tags.

The important semantic rule is:

- `output[type=message].content` is candidate final answer text;
- `output[type=reasoning].content` is diagnostic reasoning text;
- reasoning text must never be parsed as image tags.

This spec fixes the root transport-level failure mode. Later specs wire the normalized response into request artifacts, collect, and reports.

## REST API contract

Use this request path relative to `lmstudio.api_base_url`:

```text
/api/v1/chat
```

Request body shape:

```json
{
  "model": "<loaded model instance id>",
  "input": [
    { "type": "text", "content": "<prompt>" },
    { "type": "image", "data_url": "data:image/jpeg;base64,..." }
  ],
  "temperature": 0.0,
  "top_p": 1.0,
  "max_output_tokens": 2048,
  "reasoning": "off",
  "store": false
}
```

Rules:

- Use `type: "text"` for text input. This is the shape confirmed against the local LM Studio build.
- Use `type: "image"` with `data_url` for image input.
- Use `generation.max_tokens` as REST `max_output_tokens`.
- Send `temperature` and `top_p` from the existing generation config.
- Always send `store: false` for benchmark requests.
- Do not send OpenAI `messages` to REST Chat.
- Do not send OpenAI `response_format` to REST Chat.
- Do not enable `stream` in this spec.
- Do not enable tools, MCP integrations, or stateful `previous_response_id` in this spec.

Compatibility note:

- A local manual probe in this repository confirmed `type: "text"` for text input and `type: "image"` with `data_url` for image input.
- Do not implement a `type: "message"` primary path unless a later live LM Studio check proves the local API changed.
- If future LM Studio versions require a different text item discriminator, keep any compatibility shim inside `LMStudioClient` and do not leak multiple shapes into runner code.

## Config changes

Add model-level reasoning control to `ModelConfig`.

Required dataclass field:

```python
reasoning: str = "default"
```

Allowed values:

```text
default
on
off
```

Meaning:

- `default` — omit the REST `reasoning` field and let LM Studio choose model default behavior.
- `on` — send `"reasoning": "on"`.
- `off` — send `"reasoning": "off"`.

Validation rules:

- Missing `reasoning` must become `"default"`.
- Unknown values must fail config validation.
- Duplicate model `id` values are allowed when `label` values are unique.
- Duplicate model `label` values remain invalid.
- Do not add automatic text-only model detection in this spec unless the config already has an explicit stable field for it.

Important non-goal:

- Do not implement `low`, `medium`, or `high` reasoning effort values in this spec. They may exist in LM Studio, but the current benchmark needs only stable on/off/default profiles.

Example model rows:

```yaml
models:
  - id: "qwen/qwen3-vl-8b@q4_k_m"
    base_model_id: "qwen/qwen3-vl-8b"
    label: "qwen3-vl-8b-q4_k_m"
    reasoning: "default"

  - id: "qwen/qwen3.5-9b@q4_k_m"
    base_model_id: "qwen/qwen3.5-9b"
    label: "qwen3_5-9b-q4_k_m-think"
    reasoning: "on"

  - id: "qwen/qwen3.5-9b@q4_k_m"
    base_model_id: "qwen/qwen3.5-9b"
    label: "qwen3_5-9b-q4_k_m-no-think"
    reasoning: "off"
```

## Response format config rule

The existing config has:

```yaml
validation:
  use_response_format: true
```

For REST Chat this must not mean sending an API `response_format` payload.

Required rule:

- For REST transport, `validation.use_response_format` may continue to influence parser expectations only.
- REST requests must not include `response_format`.
- If code keeps OpenAI-compatible chat helpers, `response_format` may remain there for legacy tests only.

Add a comment to `config.example.yaml` near `validation.use_response_format` explaining that REST Chat ignores OpenAI `response_format` payloads.

## REST client task

Add a method to `LMStudioClient`:

```python
def chat_rest(
    self,
    *,
    model_id: str,
    input_items: list[dict[str, Any]],
    temperature: float,
    top_p: float,
    max_output_tokens: int,
    reasoning: str = "default",
) -> dict[str, Any]:
    ...
```

Behavior:

- POST to `/api/v1/chat`.
- Use `self.api_base_url`, not the OpenAI-compatible base URL.
- Pass `model_id` as the loaded instance id returned by existing model-load logic.
- Copy `input_items` without mutating caller data.
- Add `reasoning` only for `"on"` and `"off"`.
- Omit `reasoning` for `"default"`.
- Raise `LMStudioClientError` consistently with existing client methods.
- Include response body or useful server text in the exception message when available.

Do not remove `chat_completion` in this spec. Keep it for legacy tests and for a possible explicit debug path.

## Input item builder

Add a small helper, either in `lmstudio_client.py` or a lightweight utility module:

```python
def build_rest_input_items(prompt: str, image_data_url: str) -> list[dict[str, Any]]:
    return [
        {"type": "text", "content": prompt},
        {"type": "image", "data_url": image_data_url},
    ]
```

Rules:

- This helper receives an already encoded image data URL.
- This helper must not read files from disk.
- Image reading and data URL creation should remain in existing runner/client utilities or a dedicated helper.
- Unit tests should be able to verify the exact item shape without loading images.

## Normalized REST response shape

Add a dedicated normalizer function.

Preferred location:

```text
src/lmstudio_client.py
```

Alternative acceptable location:

```text
src/diagnostics.py
```

Function signature:

```python
def normalize_rest_chat_response(
    payload: dict[str, Any],
    *,
    reasoning_requested: str,
    max_output_tokens: int | None,
) -> dict[str, Any]:
    ...
```

Required output keys:

```python
{
    "transport": "rest",
    "reasoning_requested": "on",              # "default" | "on" | "off"
    "final_content": "tag1\ntag2",
    "reasoning_content": "...",
    "output_source": "message",              # "message" | "empty" | "bad_rest_response"
    "final_content_empty": False,
    "reasoning_content_present": True,
    "final_content_length": 9,
    "reasoning_content_length": 1234,
    "no_final_answer": False,
    "bad_rest_response": False,
    "finish_reason": None,
    "prompt_tokens": 556,
    "completion_tokens": 460,
    "total_tokens": 1016,
    "reasoning_tokens": 441,
    "tokens_per_second": 22.5,
    "time_to_first_token_seconds": 0.8,
    "output_truncated": False,
    "raw_response": payload,
}
```

Compatibility aliases for later pipeline stages:

```python
{
    "raw_output": final_content,
    "content_empty": final_content_empty,
    "content_length": final_content_length,
    "reasoning_content_used": False,
}
```

Rules for output extraction:

- If `payload["output"]` is not a list, set:
  - `final_content = ""`;
  - `reasoning_content = ""`;
  - `output_source = "bad_rest_response"`;
  - `bad_rest_response = True`;
  - `no_final_answer = True`.
- Gather every item where `type == "reasoning"` and `content` is not null.
- Join multiple reasoning blocks with `"\n"`.
- Use the first non-empty `type == "message"` `content` as `final_content`.
- If all message contents are empty but at least one message item exists, keep `output_source = "message"` and set `no_final_answer = True`.
- If no message item exists, set `output_source = "empty"` and `no_final_answer = True`.
- Ignore `tool_call` and `invalid_tool_call` items for tag parsing.
- Preserve unknown output item types only inside `raw_response`.
- Never copy reasoning text into `final_content` or `raw_output`.
- Always set `reasoning_content_used = False`.

## Token and performance diagnostics

REST stats come from `payload["stats"]` when present.

Mapping:

- `stats.input_tokens` -> `prompt_tokens`;
- `stats.total_output_tokens` -> `completion_tokens`;
- `stats.reasoning_output_tokens` -> `reasoning_tokens`;
- `stats.tokens_per_second` -> `tokens_per_second`;
- `stats.time_to_first_token_seconds` -> `time_to_first_token_seconds`.

Rules:

- Missing `stats` must not fail a request.
- Missing individual fields must become `None`, not `0`, unless the server explicitly returns `0`.
- Compute `total_tokens = prompt_tokens + completion_tokens` only when both are known.
- `completion_tokens` means all output tokens reported by LM Studio, including reasoning tokens when LM Studio counts them that way.
- Keep `reasoning_tokens` separate so reports can show how much of the output budget was spent on reasoning.

Output truncation:

- If REST exposes a length/stop reason in a future version, preserve it and use it.
- If no finish reason exists, infer `output_truncated = True` only when `completion_tokens` and `max_output_tokens` are both known and `completion_tokens >= max_output_tokens`.
- If unsure, prefer `False` or `None` over inventing a truncation warning.

## Error classification from normalizer

The normalizer does not handle HTTP errors. HTTP errors are still raised by `chat_rest`.

The normalizer should classify only malformed or empty successful payloads:

- `bad_rest_response` when `output` is missing or not a list.
- `empty_rest_output` when `output` is an empty list.
- `no_final_answer` when reasoning or other output exists but there is no non-empty final message.

Suggested fields:

```python
"normalization_error_type": None | "bad_rest_response" | "empty_rest_output" | "no_final_answer"
```

Later runner code will map this to request-level `error_type`.

## Config file updates

Config file updates in this spec should be minimal:

- Update `config.example.yaml` and `config.smoke.yaml` only enough to keep validation examples accurate for `ModelConfig.reasoning`.
- Add `reasoning: "default"` to existing model rows if explicit examples are useful.
- Do not split the full benchmark into think/no-think profile rows in this spec; that belongs to SPEC-24 after the runner and artifact schema are migrated.
- Keep smoke fast and do not make normal smoke depend on a slow reasoning model.

## Tests

Add or update tests for config parsing:

- Missing `reasoning` becomes `"default"`.
- `reasoning: "default"` is accepted.
- `reasoning: "on"` is accepted.
- `reasoning: "off"` is accepted.
- `reasoning: "low"` is rejected in this project spec.
- Any arbitrary string is rejected.
- Duplicate model ids are accepted if labels are unique.
- Duplicate labels are rejected.

Add or update tests for REST request construction:

- `chat_rest` posts to `/api/v1/chat`.
- Request uses REST `input`, not OpenAI `messages`.
- Text input item is `{"type": "text", "content": prompt}`.
- Image input item is `{"type": "image", "data_url": data_url}`.
- `max_output_tokens` is sent.
- `store: false` is sent.
- `reasoning: "on"` is sent when requested.
- `reasoning: "off"` is sent when requested.
- `reasoning` is omitted for `"default"`.
- `response_format` is never sent by `chat_rest`.

Add or update tests for normalization:

- A response with one message returns that message as `final_content`.
- A response with reasoning and message separates both fields.
- A response with reasoning only sets `no_final_answer` and leaves `final_content` empty.
- A response with empty message and reasoning sets `no_final_answer`.
- A response with multiple reasoning blocks joins them.
- A response with multiple messages uses the first non-empty message.
- A response with missing `output` sets `bad_rest_response`.
- A response with empty `output` sets `empty_rest_output`.
- Reasoning content is never copied into `raw_output`.
- `reasoning_content_used` is always `False`.
- REST stats map to token fields.
- Missing stats do not crash.
- Truncation inference works when `completion_tokens >= max_output_tokens`.

## Manual check

Run unit checks:

```bash
python -m pytest -q tests/test_config.py tests/test_validator.py tests/test_lmstudio_client.py tests/test_diagnostics.py
```

Run config checks:

```bash
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

Optional live REST probe, if LM Studio is running:

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<loaded-instance-id>",
    "input": [
      {"type": "text", "content": "Return one tag for the image."},
      {"type": "image", "data_url": "data:image/jpeg;base64,<...>"}
    ],
    "temperature": 0,
    "max_output_tokens": 64,
    "reasoning": "off",
    "store": false
  }'
```

## Acceptance criteria

- `ModelConfig` contains `reasoning` with default `"default"`.
- Config validation rejects unsupported reasoning values.
- `LMStudioClient.chat_rest` can build and send REST Chat requests.
- REST requests do not include OpenAI `messages` or `response_format`.
- REST responses normalize final message content and reasoning content separately.
- Reasoning text cannot become `raw_output`, `final_content`, or accepted tags through this layer.
- Token stats are extracted from REST `stats` when present.
- Missing stats and malformed output are handled without crashing.

## Out of scope

Do not implement in this spec:

- full runner migration;
- request id changes;
- storage/artifact schema changes;
- collect changes;
- report changes;
- HTML redesign;
- OpenAI-to-REST automatic fallback;
- model auto-selection;
- async requests;
- parallel processing.

## Agent report

- Done:
  - Added `ModelConfig.reasoning` with default `default` and validation for `default|on|off`.
  - Added REST transport helpers: `build_rest_input_items`, `LMStudioClient.chat_rest`, `normalize_rest_chat_response`.
  - Added REST stats handling in diagnostics usage extraction.
  - Updated smoke/example configs with explicit `reasoning` and comment for `validation.use_response_format`.
  - Added/updated unit tests for reasoning validation, REST request shape, REST response normalization, and REST stats mapping.
- Changed files:
  - `src/config.py`
  - `src/validator.py`
  - `src/lmstudio_client.py`
  - `src/diagnostics.py`
  - `config.smoke.yaml`
  - `config.example.yaml`
  - `tests/test_config.py`
  - `tests/test_validator.py`
  - `tests/test_lmstudio_client.py`
  - `tests/test_diagnostics.py`
  - `specs/22-rest-chat-transport.md`
- Checks run:
  - `python -m pytest -q tests/test_config.py tests/test_validator.py tests/test_lmstudio_client.py tests/test_diagnostics.py`
  - `python main.py validate-config --config config.smoke.yaml`
  - `python main.py dry-run --config config.smoke.yaml`
- Notes:
  - `chat_completion` was kept intact for compatibility; REST additions are additive in this spec.
