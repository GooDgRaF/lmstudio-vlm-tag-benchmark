# SPEC-10 — Resume behavior

## Goal

Implement simple file-based resume behavior without adding a database.

The runner should skip successful existing normalized results and optionally retry existing errors according to config.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-07](./07-storage.md)
- [SPEC-09](./09-runner-loop.md)

Expected files:

- `src/runner.py`
- `src/storage.py`
- `tests/test_resume.py`
- `README.md`

## Tasks

- Read resume settings from config:
  - `runtime.resume`;
  - `runtime.skip_existing_success`;
  - `runtime.retry_existing_errors`.
- Before each request, check whether `normalized/<request_id>.json` already exists.
- Define a successful normalized result as:
  - `error_type` is `null`;
  - `parse_ok` is `true`;
  - mode-specific validation passed;
  - for pool modes, `pool_ok` is `true`.
- If resume is enabled and the existing result is successful, skip it when `skip_existing_success` is true.
- If the existing result contains an error, retry it when `retry_existing_errors` is true.
- Treat a result with an old `prompt_version` or different `response_format_requested` as a different request through the deterministic `request_id` from [SPEC-07](./07-storage.md).
- Record skipped requests in logs or run metadata.
- Keep the logic file-based. Do not add SQLite.

## Check

Automated check:

```bash
pytest
```

Tests should cover:

- successful existing result is skipped;
- existing error result is retried when configured;
- existing error result is skipped when retry is disabled;
- pool-mode result with `pool_ok: false` is not treated as successful;
- changed `prompt_version` produces a different request path and is not skipped as old work;
- resume disabled forces a new request.

## Agent report

Fill this after implementation:

- Done: Added file-based resume decision logic for skipping successful existing normalized results and retrying or skipping existing error results based on config flags.
- Changed files: `src/runner.py`, `tests/test_resume.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`.
- Notes: Success criteria account for pool modes requiring `pool_ok == true`.
