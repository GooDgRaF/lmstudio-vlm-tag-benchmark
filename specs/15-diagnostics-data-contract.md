# SPEC-15 — Diagnostics data contract

## Goal

Add a structured diagnostics data layer for benchmark runs.

This spec creates machine-readable diagnostics only:

```text
results/<run_id>/diagnostics.json
```

The file should support later human-readable diagnostics rendering in SPEC-16.

This spec is about data collection and storage, not visual design.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-14 HTML answer matrix](./14-html-answer-matrix.md)
- [SPEC-16 Diagnostics HTML report](./16-diagnostics-html-report.md)

Expected files:

- `src/diagnostics.py`
- `src/runner.py`
- `src/storage.py`
- `src/tag_pools.py`
- `src/lmstudio_client.py`
- `tests/test_diagnostics.py`
- `tests/test_runner.py`
- `tests/test_storage.py`

## Scope

Implement in this spec:

- collect run-level diagnostics;
- collect pool file diagnostics with counts and hashes;
- collect model-level load, smoke-test, request, unload, and GPU snapshot diagnostics;
- collect request-level parser, pool, token, context, latency, and file path diagnostics;
- write `diagnostics.json` at the end of a run;
- still write `diagnostics.json` when a model fails to load or a request fails;
- add `gpu_after_unload.json` when GPU diagnostics are available or attempted.

Do not implement in this spec:

- `diagnostics.html`;
- changes to the primary answer matrix beyond what SPEC-14 already did;
- continuous GPU polling;
- heavy CPU/RAM/temperature monitoring;
- browser screenshots;
- model quality scoring;
- fuzzy pool matching;
- large raw prompts or raw model output embedded in `diagnostics.json`.

## Output Files

Create:

```text
results/<run_id>/diagnostics.json
```

Keep existing files:

```text
results/<run_id>/summary.csv
results/<run_id>/errors.log
results/<run_id>/models/<model_label>/load.json
results/<run_id>/models/<model_label>/smoke_test.json
results/<run_id>/models/<model_label>/gpu_before_load.json
results/<run_id>/models/<model_label>/gpu_after_load.json
```

Add:

```text
results/<run_id>/models/<model_label>/gpu_after_unload.json
```

`summary.csv` remains one row per model request. `diagnostics.json` is the richer structured diagnostics file.

## Data Ownership

Use this ownership model to avoid duplication:

- `summary.csv`: compact tabular request summary for spreadsheet use.
- `raw/<request_id>.json`: backend payloads and raw response details.
- `normalized/<request_id>.json`: normalized parsing result for one request.
- `models/<model_label>/*.json`: per-model raw load/smoke/GPU artifacts.
- `diagnostics.json`: aggregated counts, flags, short error text, hashes, and paths to detailed files.

Do not copy large raw output text or full backend payloads into `diagnostics.json` when those details already exist in raw or normalized files.

## Required JSON Shape

`diagnostics.json` must be a JSON object with these top-level keys:

```json
{
  "schema_version": 1,
  "run": {},
  "pools": {},
  "models": [],
  "requests": [],
  "warnings": []
}
```

All required keys must exist even when a section is empty.

## Run Diagnostics

Required `run` fields:

```json
{
  "run_id": "...",
  "started_at": "...",
  "finished_at": "...",
  "duration_sec": 0.0,
  "config_path": "...",
  "results_dir": "...",
  "image_dir": "...",
  "recursive": false,
  "limit_images": 1,
  "extensions": [".jpg", ".png"],
  "model_count": 1,
  "image_count": 1,
  "mode_count": 6,
  "request_count": 6,
  "success_count": 5,
  "error_count": 1,
  "pool_violation_count": 1,
  "python_version": "...",
  "git_commit": null
}
```

`git_commit` is best-effort. If git is unavailable or the command fails, use `null`.

Use a stable timestamp string. Prefer the project’s existing local timestamp style if one exists.

## Pool Diagnostics

Required `pools` entries:

```json
{
  "ru_plain": {
    "path": "pools/ru_plain.txt",
    "type": "plain",
    "tag_count": 617,
    "entry_count": 617,
    "sha256": "..."
  },
  "en_explained": {
    "path": "pools/en_explained_ids.tsv",
    "type": "explained",
    "tag_count": 617,
    "entry_count": 617,
    "id_prefixes": ["EN"],
    "sha256": "..."
  }
}
```

Required pool keys:

- `ru_plain`;
- `en_plain`;
- `ru_explained`;
- `en_explained`.

Pool hashes are required because old results should remain interpretable after pool files change.

## Model Diagnostics

Required fields per model:

```json
{
  "model_label": "...",
  "model_id": "...",
  "base_model_id": "...",
  "params": "4B",
  "quant": "Q4_K_M",
  "quant_bits": 4,
  "load_started_at": "...",
  "load_finished_at": "...",
  "load_duration_sec": 0.0,
  "load_ok": true,
  "load_error_type": null,
  "load_error": null,
  "instance_id": "...",
  "requested_context_length": 16384,
  "actual_context_length": 16384,
  "smoke_test_ok": true,
  "smoke_test_error": null,
  "request_count": 6,
  "success_count": 5,
  "error_count": 1,
  "pool_violation_count": 1,
  "avg_latency_sec": 1.23,
  "median_latency_sec": 1.12,
  "min_latency_sec": 0.9,
  "max_latency_sec": 1.8,
  "parse_ok_rate": 1.0,
  "schema_ok_rate": 1.0,
  "pool_ok_rate": 0.83,
  "gpu_before_load": {},
  "gpu_after_load": {},
  "gpu_after_unload": {},
  "unload_ok": true,
  "unload_error": null
}
```

When a model fails to load:

- still include a model diagnostics entry;
- set `load_ok: false`;
- set request counters to zero;
- set latency/rate fields to `null` when they cannot be computed;
- include short `load_error_type` and `load_error`;
- continue with the next model.

## Request Diagnostics

Required fields per request:

```json
{
  "request_id": "...",
  "model_label": "...",
  "model_id": "...",
  "image_id": "...",
  "image_rel_path": "...",
  "mode": "en_pool",
  "prompt_version": "v1",
  "response_format_requested": "strict_json",
  "response_format_used": "strict_json",
  "latency_sec": 1.23,
  "retry_count": 0,
  "retried_without_response_format": false,
  "parse_ok": true,
  "schema_ok": true,
  "pool_ok": false,
  "pool_violations": 1,
  "error_type": "pool_validation_failed",
  "error": "Response contains values outside configured pool",
  "finish_reason": "stop",
  "prompt_tokens": 100,
  "completion_tokens": 20,
  "total_tokens": 120,
  "requested_context_length": 16384,
  "actual_context_length": 16384,
  "context_near_limit": false,
  "context_overflow": false,
  "output_truncated": false,
  "accepted_tag_count": 5,
  "rejected_tag_count": 1,
  "rejected_id_count": 0,
  "json_extracted": false,
  "line_fallback_used": false,
  "empty_output": false,
  "raw_output_length": 120,
  "raw_path": "raw/<request_id>.json",
  "normalized_path": "normalized/<request_id>.json"
}
```

For failed requests:

- still include a request diagnostics entry;
- set parser/pool booleans consistently with the normalized result;
- set unavailable token/context fields to `null`;
- store only short error text.

If a request was skipped by resume, do not create a new request diagnostics entry unless the existing normalized or summary row is also included in the current run summary. Avoid mixing current-run work with unrelated old-run entries.

## Duplicate Rows

Detect duplicate rows in `summary.csv` for the matrix key:

```text
(image_id, mode, model_label)
```

For each duplicate key, add a warning:

```json
{
  "type": "duplicate_summary_rows",
  "key": {
    "image_id": "...",
    "mode": "...",
    "model_label": "..."
  },
  "count": 2,
  "used_request_id": "..."
}
```

`used_request_id` should be the last row in `summary.csv`, matching SPEC-14.

Do not include `prompt_version` or `response_format_requested` in this duplicate key for v1. If future prompt versions need side-by-side comparison, that should be a later spec.

## Error Classification

Use short stable `error_type` values.

Required compatible values:

- `load_failed`;
- `load_failed_oom`;
- `request_error`;
- `pool_validation_failed`;
- `context_overflow`;
- parser-related values already used by the project.

Do not introduce verbose or backend-specific error types unless they are normalized.

Keep full backend messages out of compact fields when they are very long. Store a shortened message in diagnostics and preserve details in raw/error files when available.

## GPU Diagnostics

Continue using `nvidia-smi` best-effort.

Required GPU snapshot fields when unavailable:

```json
{
  "gpu_diagnostics_available": false
}
```

Required GPU snapshot fields when available:

```json
{
  "gpu_diagnostics_available": true,
  "memory_total_mb": 0,
  "memory_used_mb": 0,
  "memory_free_mb": 0
}
```

Optional fields if available from the same cheap command:

- `gpu_name`;
- `driver_version`;
- `utilization_gpu_percent`.

If `nvidia-smi` is unavailable, diagnostics must not fail the benchmark.

## Summary CSV Compatibility

Keep `summary.csv` stable as the compact tabular view.

Allowed additions:

- paths to diagnostics/raw/normalized files;
- compact counts;
- simple flags.

Avoid adding large text fields or nested JSON that belongs in `diagnostics.json`.

If adding columns, update:

- `src/storage.py`;
- `tests/test_summary_csv.py`;
- `PROJECT_GUIDE.md`;
- `AGENTS.md` only if agent workflow changes.

## Tests

Add or update tests for:

- `diagnostics.json` is created;
- required top-level keys exist;
- run-level counts are correct;
- pool file hashes and counts are recorded;
- model-level load/smoke/unload fields are present;
- failed model load still creates a model diagnostics entry;
- request-level parser/pool/token/context fields are present;
- failed request still creates a request diagnostics entry;
- duplicate summary rows produce warnings;
- unavailable git commit does not fail diagnostics;
- unavailable `nvidia-smi` does not fail diagnostics;
- `gpu_after_unload.json` is saved after unload is attempted;
- raw output text is not duplicated into `diagnostics.json` as a large blob.

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
results/<run_id>/diagnostics.json
results/<run_id>/summary.csv
results/<run_id>/models/<model_label>/gpu_after_unload.json
```

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
