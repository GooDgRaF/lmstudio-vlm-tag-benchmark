# SPEC-23 — Runner migration and REST request artifacts

## Goal

Wire the REST Chat transport from SPEC-22 into the benchmark runner and make all per-request artifacts accurately record the REST response contract.

After this spec, a real benchmark run should use REST Chat for normal inference, parse only final message content as tags, and save request artifacts that preserve final answer text, reasoning text, token diagnostics, and compatibility aliases.

This spec does not update collect/report rendering beyond whatever is necessary to keep the run command from failing. Full collect/report changes are handled in SPEC-24.

## Files

Related files:

- [SPEC-22 REST Chat transport and response normalization](./22-rest-chat-transport.md)
- [Specs workflow](./README.md)
- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)

Expected files to change:

- `src/runner.py`
- `src/storage.py`
- `src/diagnostics.py`
- `src/lmstudio_client.py` only for small follow-up fixes from runner integration
- `config.example.yaml`
- `config.smoke.yaml`
- `tests/test_runner.py`
- `tests/test_storage.py`
- `tests/test_diagnostics.py`

Avoid changing in this spec unless needed for a failing integration test:

- `src/collect.py`
- `src/report.py`

## Preconditions

SPEC-22 must already be implemented.

Required functions or equivalent behavior must exist:

- `LMStudioClient.chat_rest(...)`;
- `normalize_rest_chat_response(...)`;
- REST token/stat extraction;
- `ModelConfig.reasoning`.

If any of these are missing, implement the missing SPEC-22 behavior first and record it in `Agent report`.

## Main behavior change

Current runner inference path uses OpenAI-compatible chat completions:

```text
build OpenAI messages
maybe build response_format
client.chat_completion(...)
_extract_text_from_completion(...)
normalize_model_output(raw_output=...)
save artifacts
```

New runner inference path:

```text
build prompt
build REST input items: text + image
client.chat_rest(..., reasoning=model.reasoning)
normalize_rest_chat_response(...)
normalize_model_output(raw_output=rest_normalized.final_content)
save artifacts with REST metadata
```

Required invariant:

```text
Only REST final_content may be passed to normalize_model_output.
```

Forbidden behavior:

```text
Do not pass reasoning_content to normalize_model_output.
Do not fallback from empty final_content to reasoning_content.
Do not parse OpenAI message.reasoning_content as tags in normal REST runs.
```

## Runner tasks

### 1. Remove reasoning fallback from normal answer extraction

The current `_extract_text_from_completion` falls back from empty `message.content` to `message.reasoning_content`.

For REST runs this is forbidden.

Required action:

- Stop using `_extract_text_from_completion` in the normal benchmark path.
- Either delete the reasoning fallback or limit it to an explicit legacy OpenAI debug path.
- If the function remains, rename or comment it so future code does not use it for REST.

Acceptable compatibility behavior:

- OpenAI legacy helper may still extract `message.content`.
- OpenAI legacy helper must not treat `reasoning_content` as final answer unless an explicit debug-only option exists. Prefer no fallback at all.

### 2. Build REST input items in runner

Convert the existing prompt and image into REST input items.

Required shape:

```python
[
    {"type": "text", "content": prompt.prompt},
    {"type": "image", "data_url": image_data_url},
]
```

Rules:

- Reuse existing image-to-data-url logic if available.
- Do not duplicate large base64 conversion code in multiple places.
- Do not store data URLs in summary CSV.
- Raw artifacts may contain the raw REST response but should not need to store the full request body unless current artifact conventions already do so.

### 3. Call REST Chat for smoke test

The runner's model smoke test must call REST Chat.

Required behavior:

- Use the same model profile `reasoning` setting as normal benchmark requests.
- Print/log a preview of final message only.
- If reasoning exists, mention only that reasoning exists and its length/tokens; do not print full reasoning by default.
- If final answer is empty but reasoning exists, fail or warn according to current smoke behavior, but do not display reasoning as the answer.

### 4. Call REST Chat for benchmark requests

For each image/mode request:

- build prompt as today;
- build REST input items;
- call `client.chat_rest` with:
  - `model_id=loaded.instance_id`;
  - `input_items=...`;
  - `temperature=cfg.generation.temperature`;
  - `top_p=cfg.generation.top_p`;
  - `max_output_tokens=cfg.generation.max_tokens`;
  - `reasoning=model.reasoning`;
- normalize the REST response;
- pass only `final_content` to `normalize_model_output`.

### 5. Disable OpenAI response_format for REST path

Remove the current REST-incompatible logic from the normal path:

```python
if cfg.validation.use_response_format:
    response_format_payload = _response_format_payload(...)
```

Required behavior:

- `response_format_payload` must not be constructed for REST calls.
- `retried_without_response_format` should be `False` for REST calls.
- `retry_count` should not become `1` merely because REST ignores OpenAI structured output.
- `response_format_requested` should remain the prompt/parser expectation.
- `response_format_used` should be the parser format actually used for local parsing.

Recommended mapping:

- free modes: usually `line_tags` unless prompt config explicitly expects JSON parsing;
- plain pool modes: usually `line_tags`;
- explained pool modes: usually `line_ids`.

If current `build_prompt` already returns `prompt.response_format_requested`, keep using that as the parser expectation, but do not send it as an API payload.

## Request id changes

Update `build_request_id` in `src/storage.py`.

Add source parts:

- `transport`;
- `reasoning_requested`.

Suggested signature:

```python
def build_request_id(
    *,
    model_id: str,
    model_label: str,
    image_id: str,
    mode: str,
    prompt_version: str,
    response_format_requested: str,
    transport: str = "rest",
    reasoning_requested: str = "default",
    pool_hash: str | None = None,
) -> str:
    ...
```

Rules:

- Include `transport` and `reasoning_requested` in the hash source.
- Include them in the filename base if the name remains readable and not too long.
- Keep defaults so old tests and helper calls are easy to update.
- Old artifacts with request ids created before this spec do not need to be renamed.

Why this matters:

- A REST request and an old OpenAI request must not collide.
- A user changing `reasoning` on the same label should not accidentally reuse stale artifacts.
- Labels are still expected to be unique, but request ids should not rely on label uniqueness alone for reasoning-mode separation.

## Manifest and request queue metadata

Update run manifest and request queue entries to include:

- `transport: "rest"`;
- `reasoning_requested: model.reasoning`.

For each request item created before inference, include at least:

```json
{
  "request_id": "...",
  "transport": "rest",
  "reasoning_requested": "off",
  "model_id": "...",
  "model_label": "...",
  "image_id": "...",
  "mode": "...",
  "prompt_version": "...",
  "response_format_requested": "line_tags"
}
```

Rules:

- Do not infer `reasoning_requested` later from the label.
- Store the actual config value.
- Keep old request queues readable if resume encounters a queue without these fields; default missing transport to `"openai"` or `"legacy"` only for display, not for new requests.

## Normalized artifact schema

Every successful REST request normalized artifact must include current normalized tag fields plus REST fields.

Required fields:

```json
{
  "request_id": "...",
  "run_id": "...",
  "transport": "rest",
  "reasoning_requested": "off",
  "model_id": "...",
  "base_model_id": "...",
  "model_label": "...",
  "image_id": "...",
  "image_path": "...",
  "image_rel_path": "...",
  "mode": "ru_free",
  "prompt_version": "...",
  "response_format_requested": "line_tags",
  "response_format_used": "line_tags",

  "raw_output": "tag1\ntag2",
  "final_content": "tag1\ntag2",
  "reasoning_content": "...",
  "output_source": "message",

  "content_empty": false,
  "content_length": 9,
  "final_content_empty": false,
  "final_content_length": 9,
  "reasoning_content_present": true,
  "reasoning_content_length": 1234,
  "reasoning_content_used": false,
  "no_final_answer": false,

  "raw_tags": [],
  "raw_ids": [],
  "accepted_tags": [],
  "accepted_ids": [],
  "rejected_tags": [],
  "rejected_ids": [],
  "tag_count": 0,
  "pool_violations": 0,
  "parse_ok": true,
  "schema_ok": true,
  "json_extracted": false,
  "line_fallback_used": false,
  "pool_ok": true,

  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0,
  "reasoning_tokens": 0,
  "tokens_per_second": 0.0,
  "time_to_first_token_seconds": 0.0,
  "output_truncated": false,

  "error_type": null,
  "error": null,
  "latency_sec": 0.0
}
```

Compatibility aliases:

- `raw_output` must equal `final_content`.
- `content_empty` must equal `final_content_empty`.
- `content_length` must equal `final_content_length`.
- `reasoning_content_used` must always be `false` for REST.

Reasoning storage rule:

- It is acceptable for normalized artifacts to contain full `reasoning_content` because they are local debug artifacts.
- Summary CSV should not include full reasoning text.
- Reports should not render full reasoning in the main matrix.

## Raw artifact schema

Raw request artifact should include:

```json
{
  "request_id": "...",
  "transport": "rest",
  "reasoning_requested": "off",
  "model_id": "...",
  "model_label": "...",
  "image_id": "...",
  "mode": "...",
  "prompt_version": "...",
  "response_format_requested": "line_tags",
  "response_format_used": "line_tags",
  "final_content": "tag1\ntag2",
  "reasoning_content": "...",
  "response": { "...": "raw LM Studio REST response" }
}
```

Rules:

- Preserve the raw REST response under `response`.
- Preserve extracted `final_content` and `reasoning_content` for quick inspection.
- Do not call reasoning content `raw_output`.
- If a request fails before response, keep current error artifact behavior but add `transport` and `reasoning_requested`.

## Request diagnostics schema

Each request diagnostics artifact should include:

```json
{
  "request_id": "...",
  "status": "completed",
  "transport": "rest",
  "reasoning_requested": "off",
  "output_source": "message",
  "final_content_empty": false,
  "reasoning_content_present": true,
  "no_final_answer": false,
  "bad_rest_response": false,
  "normalization_error_type": null,
  "final_content_length": 9,
  "reasoning_content_length": 1234,
  "reasoning_tokens": 441,
  "tokens_per_second": 22.5,
  "time_to_first_token_seconds": 0.8,
  "output_truncated": false,
  "raw_path": "...",
  "normalized_path": "..."
}
```

Rules:

- Keep existing diagnostics fields.
- Add these REST fields; do not replace old fields abruptly.
- `reasoning_content_used` may remain as a compatibility field but must be `false`.

## Error handling

### HTTP/client errors

If `chat_rest` raises `LMStudioClientError`:

- keep current failed-request flow;
- set `error_type: "request_error"`;
- set `transport: "rest"`;
- set `reasoning_requested` from the model config;
- save raw/normalized/diagnostics artifacts as current code does for failures.

### Successful response but no final answer

If `normalize_rest_chat_response` returns `no_final_answer: true`:

- do not parse reasoning text;
- call `normalize_model_output` with empty string or skip tag parsing;
- set:
  - `accepted_tags: []`;
  - `accepted_ids: []`;
  - `rejected_tags: []`;
  - `rejected_ids: []`;
  - `tag_count: 0`;
  - `parse_ok: false`;
  - `schema_ok: false`;
  - `pool_ok: false` for pool modes if current semantics require a valid parse, otherwise keep current no-output behavior;
  - `error_type: "no_final_answer"` unless a stronger normalization error exists;
  - `error` to a short stable message such as `"REST response did not contain a non-empty final message"`.
- preserve reasoning diagnostics.

### Malformed REST response

If normalizer reports `bad_rest_response`:

- set `error_type: "bad_rest_response"`;
- do not parse tags;
- save raw payload for inspection.

If normalizer reports `empty_rest_output`:

- set `error_type: "empty_rest_output"`;
- do not parse tags.

## Result modes

The project supports:

```yaml
runtime:
  result_mode: "deterministic"   # or "overwrite" or "accumulate"
```

This spec must update all save paths.

Required behavior for deterministic/overwrite:

- request raw artifact includes REST metadata;
- request normalized artifact includes REST metadata;
- request diagnostics artifact includes REST metadata;
- legacy raw/normalized mirrors, if still written, include equivalent REST metadata or are clearly deprecated.

Required behavior for accumulate:

- attempt raw artifact includes REST metadata;
- attempt normalized artifact includes REST metadata;
- attempt diagnostics artifact includes REST metadata;
- attempt status includes REST metadata where useful;
- `attempt` number remains correct.

Do not update only the deterministic path. That is a common failure mode.

## Summary row updates

Update `SUMMARY_FIELDS` in `src/storage.py`.

Add fields near other response diagnostics:

```text
transport
reasoning_requested
final_content_empty
final_content_length
reasoning_content_present
reasoning_content_length
reasoning_tokens
no_final_answer
normalization_error_type
tokens_per_second
time_to_first_token_seconds
```

Keep old fields for compatibility:

```text
content_empty
reasoning_content_used
content_length
```

Summary row rules:

- Do not include full `reasoning_content` in summary CSV.
- Do not include full `final_content` in summary CSV unless current summary already includes raw output; prefer parsed tags only.
- Include booleans and lengths so diagnostics can be rebuilt without opening every raw response.

## Resume behavior

For deterministic mode:

- A completed REST request should be skipped on resume as current completed requests are skipped.
- Old OpenAI artifacts should not be mistaken for equivalent REST artifacts because request id now includes transport.

For overwrite mode:

- Existing request artifacts may be overwritten according to current behavior.
- New artifacts must use REST schema.

For accumulate mode:

- New attempts should be appended as current behavior.
- REST fields must be present in each attempt.

Missing-field compatibility:

- If resume reads a status/manifest created before this spec, missing `transport` and `reasoning_requested` must not crash.
- New requests generated after this spec must always include both fields.

## Tests

Add or update tests for runner behavior:

- Runner uses `chat_rest` for normal inference.
- Runner does not call `chat_completion` in the normal path.
- Runner passes `model.reasoning` to `chat_rest`.
- Runner builds REST input items with prompt and image data URL.
- Runner does not construct or send OpenAI `response_format` for REST.
- Runner passes only `final_content` to `normalize_model_output`.
- Runner does not parse `reasoning_content` when `final_content` is empty.
- No-final-answer response produces `parse_ok: false` and `error_type: "no_final_answer"`.
- Bad REST response produces `error_type: "bad_rest_response"`.
- Empty REST output produces `error_type: "empty_rest_output"`.
- Request error produces `error_type: "request_error"` and includes REST metadata.

Add or update tests for request ids:

- `build_request_id` changes when `transport` changes.
- `build_request_id` changes when `reasoning_requested` changes.
- `build_request_id` remains stable for identical inputs.
- `pool_hash` still affects request id.

Add or update tests for artifacts:

- Deterministic save path writes REST metadata to raw, normalized, and diagnostics artifacts.
- Accumulate save path writes REST metadata to attempt raw, normalized, and diagnostics artifacts.
- `raw_output == final_content`.
- `content_empty == final_content_empty`.
- `reasoning_content_used is False` for REST.
- Summary row includes REST fields.
- Summary row does not include full reasoning content.

Add or update tests for smoke:

- Smoke test uses REST Chat.
- Smoke preview uses final content, not reasoning content.

## Manual check

Run targeted tests:

```bash
python -m pytest -q tests/test_runner.py tests/test_storage.py tests/test_diagnostics.py
```

Run all tests if practical:

```bash
python -m pytest -q
```

Validate config:

```bash
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

Run one real smoke benchmark:

```bash
python main.py run --config config.smoke.yaml --run-id rest-runner-smoke
```

Inspect artifacts:

```text
results/rest-runner-smoke/run_manifest.json
results/rest-runner-smoke/summary.csv
results/rest-runner-smoke/requests/*/raw.json
results/rest-runner-smoke/requests/*/normalized.json
results/rest-runner-smoke/requests/*/diagnostics.json
```

Expected manual observations:

- Raw artifact contains REST response under `response`.
- Normalized artifact contains `transport: "rest"`.
- Normalized artifact contains `final_content` and `reasoning_content` separately.
- `raw_output` equals `final_content`.
- Reasoning text is not in `accepted_tags`.
- Summary CSV has REST/reasoning columns.
- Request id contains or hashes transport/reasoning so old OpenAI artifacts are not reused.

## Acceptance criteria

- Normal benchmark run uses REST Chat.
- OpenAI-compatible chat is not used unless an explicit future legacy/debug flag is added.
- No REST request includes OpenAI `response_format`.
- Empty final answer never falls back to reasoning.
- Deterministic, overwrite, and accumulate save paths all preserve REST metadata.
- Summary rows include transport, reasoning mode, final-content status, and reasoning-token diagnostics.
- Existing old artifacts do not need migration and do not crash resume/status helpers merely because fields are missing.

## Out of scope

Do not implement in this spec:

- collect rebuild logic for old/new artifacts;
- report HTML changes;
- diagnostics HTML redesign;
- separate reasoning smoke config;
- quality scoring;
- UI filters;
- parallel execution;
- support for non-LM-Studio backends.

## Agent report

- Done:
  - Migrated runner inference/smoke paths to LM Studio REST Chat (`chat_rest`) with REST input items.
  - Removed normal-path dependence on OpenAI `messages/response_format` and disabled reasoning fallback-to-tags behavior.
  - Wired `normalize_rest_chat_response` into runner and parse pipeline (`normalize_model_output(raw_output=final_content)` only).
  - Added REST metadata to manifest/request artifacts and summary rows (`transport`, `reasoning_requested`, final/reasoning diagnostics).
  - Extended request-id entropy with `transport` and `reasoning_requested`.
  - Updated runner/storage tests for REST path and artifact semantics.
- Changed files:
  - `src/runner.py`
  - `src/storage.py`
  - `tests/test_runner.py`
  - `tests/test_storage.py`
  - `specs/23-rest-runner-artifacts.md`
- Checks run:
  - `python -m pytest -q tests/test_runner.py tests/test_storage.py tests/test_diagnostics.py`
  - `python main.py validate-config --config config.smoke.yaml`
  - `python main.py dry-run --config config.smoke.yaml`
- Notes:
  - `chat_completion` remains in client only for legacy compatibility, but normal runner path now uses REST only.
