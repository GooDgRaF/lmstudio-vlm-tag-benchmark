# SPEC-03 — LM Studio API probe and client

## Goal

Add a small LM Studio client for model listing, model loading, model unloading, and chat completion requests.

This stage should first verify the current LM Studio API shape, then provide the API wrapper. The full benchmark loop comes later.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-02](./02-config-validation.md)

Expected files:

- `src/lmstudio_client.py`
- `tests/test_lmstudio_client.py`
- `README.md`

## Tasks

- Implement a small HTTP client using the configured URLs:
  - `lmstudio.api_base_url` for native LM Studio model management;
  - `lmstudio.openai_base_url` for OpenAI-compatible chat completions.
- Add a lightweight API probe through a CLI command such as `list-models` or `probe-lmstudio`.
- The probe should verify the currently installed LM Studio endpoint behavior before the full runner is implemented.
- If the observed LM Studio endpoint shape differs from the architecture, document the observed behavior in the README or Agent report before continuing.
- Add methods for:
  - `list_models()` using `GET /api/v1/models`;
  - `load_model(model_id, load_config)` using `POST /api/v1/models/load`;
  - `unload_model(instance_id)` using `POST /api/v1/models/unload`;
  - `chat_completion(...)` using `POST /v1/chat/completions`.
- Unload loaded models with `POST /api/v1/models/unload` and the exact JSON body `{"instance_id": "<loaded instance id>"}`.
- Do not include an `id` key in the unload body; current LM Studio rejects extra keys with `unrecognized_keys`.
- Use the returned load `instance_id`, or values from `loaded_instances`, rather than the configured variant `model_id`.
- Preserve raw response objects enough for diagnostics.
- Add a `LoadedModel` data structure with fields from the architecture.
- Add timeouts from config.
- Add clear error messages for connection failures and HTTP errors.
- If `response_format` is rejected or unsupported by the OpenAI-compatible endpoint, return a clear diagnostic and allow the caller to retry without `response_format` later.
- Add `list-models` CLI command.
- Do not implement image processing or the full runner yet.

## Check

Manual check with LM Studio running:

```bash
python main.py list-models --config config.example.yaml
```

Automated check:

```bash
pytest
```

Tests should mock HTTP calls and cover:

- model listing;
- load request body includes configured context length;
- unload request is sent with `instance_id` and no extra `id` key;
- chat completion sends to the OpenAI-compatible endpoint;
- unsupported `response_format` errors are surfaced clearly;
- connection errors become readable application errors.

## Agent report

Fill this after implementation:

- Done: Added LM Studio client (`list_models`, `load_model`, `unload_model`, `chat_completion`), `LoadedModel`, connection/HTTP error handling, response-format unsupported diagnostic, and `list-models` CLI probe.
- Changed files: `src/lmstudio_client.py`, `main.py`, `tests/test_lmstudio_client.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`; `python main.py list-models --config config.example.yaml`.
- Notes: Observed LM Studio `/api/v1/models` payload shape is `{ "models": [...] }` in this environment (not only `{ "data": [...] }`), parser updated to support both.
- Notes: Observed LM Studio `/api/v1/models/unload` requires exactly `{"instance_id": ...}`. Sending both `id` and `instance_id` is rejected as `unrecognized_keys`; falling back to `model`/`identifier` then produces the misleading `Missing required field 'instance_id'` error.
