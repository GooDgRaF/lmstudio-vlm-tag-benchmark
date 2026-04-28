# SPEC-18 — Resumable request artifacts

## Goal

Make benchmark execution resilient to interruptions by saving every model/image/mode response as an independent request artifact immediately after it is produced.

The runner should no longer depend on finishing the whole benchmark before useful data exists. After a crash, timeout, manual stop, or machine reboot, the next run should skip already completed deterministic requests and continue from the remaining work.

This spec changes the runtime storage model. It does not redesign HTML reports.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-15 Diagnostics data contract](./15-diagnostics-data-contract.md)
- [SPEC-16 Diagnostics HTML report](./16-diagnostics-html-report.md)

Expected files:

- `src/config.py`
- `src/runner.py`
- `src/storage.py`
- `src/diagnostics.py`
- `tests/test_config.py`
- `tests/test_runner.py`
- `tests/test_storage.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Scope

Implement in this spec:

- create a stable run manifest before requests start;
- create one directory per logical request;
- save `request.json`, `status.json`, `raw.json`, `normalized.json`, and `diagnostics.json` per request;
- write request files atomically;
- support deterministic resume that skips successful requests;
- support overwrite mode that recomputes requests;
- add an explicit `--run-id <id>` CLI option for creating or continuing a run;
- create failed request statuses for model load failures;
- keep existing `summary.csv`, `diagnostics.json`, `report.html`, and `diagnostics.html` behavior working as best-effort final artifacts.

Do not implement in this spec:

- a separate `collect` CLI command;
- final rebuild of `summary.csv` from request artifacts;
- accumulation mode with multiple attempts;
- report timing summary blocks;
- PDF/print CSS;
- async runner;
- parallel inference;
- SQLite or external database.

## New Config

Add runtime settings:

```yaml
runtime:
  result_mode: deterministic
  resume: true
  retry_failed: true
```

Allowed `result_mode` values:

- `deterministic`;
- `overwrite`.

Semantics:

- `deterministic`: one canonical result per logical request. If `status.json` says `success`, skip it on resume.
- `overwrite`: recompute requests even if a success already exists.

Remove the old runtime flags:

```yaml
skip_existing_success
retry_existing_errors
```

This is a local project without an external API compatibility contract. Keep the config simple and use only:

```yaml
runtime:
  result_mode: deterministic
  resume: true
  retry_failed: true
```

Decision rules:

- if `resume: false`, run requests according to `result_mode` but do not skip existing successes;
- if `result_mode: deterministic` and `resume: true`, skip requests with canonical `status.json` equal to `success`;
- if `result_mode: deterministic`, `resume: true`, and `retry_failed: true`, retry requests with `failed`, `running`, missing, or invalid status;
- if `result_mode: deterministic`, `resume: true`, and `retry_failed: false`, skip `failed` requests and retry only `running`, missing, or invalid status;
- if `result_mode: overwrite`, recompute all requests and replace canonical artifacts.

## CLI

Add an optional run id to `run`:

```bash
python main.py run --config config.smoke.yaml --run-id <id>
```

Semantics:

- if `results/<id>/` does not exist, create a new run with that id;
- if `results/<id>/` exists and contains `run_manifest.json`, load the manifest and continue that run;
- if `results/<id>/` exists but has no manifest, fail with a clear message unless an explicit force option is supplied;
- if `--run-id` is omitted, keep the current timestamp-generated run id behavior.

Add a lock override for stale locks:

```bash
python main.py run --config config.smoke.yaml --run-id <id> --force-lock
```

`--force-lock` may remove or ignore an existing `run.lock`. Document that it is intended for stale locks after a crash, not for concurrent runs.

## Run Manifest

Create before model execution:

```text
results/<run_id>/run_manifest.json
```

Required shape:

```json
{
  "schema_version": 1,
  "run_id": "...",
  "created_at": "...",
  "config_path": "...",
  "result_mode": "deterministic",
  "request_count": 2016,
  "pool_hashes": {
    "ru_plain": "...",
    "en_plain": "...",
    "ru_explained": "...",
    "en_explained": "..."
  },
  "requests": [
    {
      "request_id": "...",
      "model_label": "...",
      "model_id": "...",
      "image_id": "...",
      "image_rel_path": "...",
      "mode": "en_free",
      "prompt_version": "v1",
      "response_format_requested": "strict_json"
    }
  ]
}
```

The manifest is the source of truth for the expected task list.

## Stable Request ID

For deterministic mode, `request_id` must be stable for the same logical request and must include:

```text
model_id
model_label
image_id
mode
prompt_version
response_format_requested
relevant pool hash for pool modes
```

Pool hashes matter because a result against an old pool should not silently count as completed against a changed pool.

For free modes, pool hash may be omitted.

Keep filenames safe through the existing filename sanitizer.

## Request Artifact Layout

In deterministic mode:

```text
results/<run_id>/requests/<request_id>/
  request.json
  status.json
  raw.json
  normalized.json
  diagnostics.json
```

In overwrite mode, use the same canonical layout and replace canonical files atomically.

Do not create `attempts/` directories in this spec. Accumulation mode is handled by SPEC-21.

## Request Status

Required `status.json` fields:

```json
{
  "schema_version": 1,
  "request_id": "...",
  "status": "success",
  "attempt": 1,
  "started_at": "...",
  "finished_at": "...",
  "duration_sec": 1.23,
  "model_label": "...",
  "image_id": "...",
  "mode": "en_free",
  "error_type": null,
  "error": null
}
```

Allowed statuses:

- `running`;
- `success`;
- `failed`;
- `skipped`.

Before sending a request, write `running`. After the request completes, replace it with `success` or `failed`.

If the process dies while a request is `running`, the next deterministic resume may treat it as incomplete and retry it.

## Atomic Writes

Write JSON artifacts atomically:

1. Write to `<name>.tmp`.
2. Flush and close.
3. Rename/replace to `<name>.json`.

Never leave partially written `raw.json`, `normalized.json`, `diagnostics.json`, or `status.json` as the canonical file.

## Runner Behavior

Execution flow:

1. Load config.
2. Load tag pools and compute hashes.
3. Discover images.
4. Build or load run manifest.
5. Iterate manifest requests in stable order.
6. Load/unload models as today.
7. Before each request, decide whether it should run, skip, or retry.
8. Write per-request artifacts immediately.
9. Continue after failed requests.
10. At the end, keep writing existing final artifacts if possible.

Failures in one request must not stop the whole benchmark.

Model load failure must create failed request statuses for every manifest request belonging to that model. Use `error_type: "load_failed"` or `error_type: "load_failed_oom"` and keep answer artifacts empty enough for reports to render empty cells while diagnostics explain the failure.

## Run State

Maintain:

```text
results/<run_id>/run_state.json
```

Required fields:

```json
{
  "schema_version": 1,
  "run_id": "...",
  "status": "running",
  "expected": 2016,
  "completed": 1223,
  "failed": 0,
  "skipped": 0,
  "remaining": 793,
  "current_model": "...",
  "current_image": "...",
  "current_mode": "...",
  "updated_at": "..."
}
```

Update it after each request.

At normal completion, set `status: "complete"` and write:

```text
results/<run_id>/run_complete.json
```

If `run_complete.json` is missing, reports and diagnostics should treat the run as partial.

## Run Lock

Create a lightweight lock file:

```text
results/<run_id>/run.lock
```

The lock should reduce accidental concurrent writes into the same run directory.

Minimum acceptable behavior:

- if `run.lock` exists and there is no explicit force/override option, fail with a clear message;
- remove `run.lock` on normal completion;
- if the process crashes, the user may manually remove stale lock or use `--force-lock`.

Do not implement complex cross-platform process ownership checks in this spec.

## Tests

Add or update tests for:

- `run_manifest.json` is created before requests are sent;
- manifest request count matches models x images x modes;
- request directories are created;
- `request.json`, `status.json`, `raw.json`, `normalized.json`, and per-request `diagnostics.json` are saved;
- writes are atomic enough that canonical files are valid JSON;
- deterministic resume skips successful requests;
- deterministic resume retries `running` or failed requests when configured;
- `overwrite` recomputes successful requests;
- `run --run-id <id>` creates or continues the selected run id;
- stale `run.lock` fails clearly without `--force-lock`;
- `--force-lock` allows continuing a run with a stale lock;
- model load failure creates failed request statuses for all requests of that model;
- `run_state.json` updates after each request;
- `run_complete.json` exists after normal completion;
- request failure does not stop later requests.

## Check

Automated:

```bash
python -m pytest -q
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

Manual smoke check with LM Studio:

```bash
python main.py run --config config.smoke.yaml
```

Then inspect:

```text
results/<run_id>/run_manifest.json
results/<run_id>/run_state.json
results/<run_id>/requests/
results/<run_id>/run_complete.json
```

Manual interruption check:

1. Start a run with more than one image/model/mode.
2. Stop it manually.
3. Restart with `python main.py run --config <same-config> --run-id <same-id>`.
4. Confirm successful requests are skipped and remaining requests continue.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
