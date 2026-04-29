# SPEC-19 — Collect and merge from request artifacts

## Goal

Add a separate collection step that rebuilds final run-level files from per-request artifacts.

After SPEC-18, request artifacts are the durable source of truth. This spec makes final artifacts reproducible even after interruption:

```text
summary.csv
diagnostics.json
report.html
diagnostics.html
```

The benchmark should be able to run requests, stop halfway, and still build a truthful partial summary and reports from completed/failed artifacts.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-18 Resumable request artifacts](./18-resumable-request-artifacts.md)
- [SPEC-15 Diagnostics data contract](./15-diagnostics-data-contract.md)
- [SPEC-16 Diagnostics HTML report](./16-diagnostics-html-report.md)

Expected files:

- `main.py`
- `src/collect.py`
- `src/storage.py`
- `src/runner.py`
- `src/diagnostics.py`
- `src/report.py`
- `tests/test_storage.py`
- `tests/test_runner.py`
- `tests/test_report.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Scope

Implement in this spec:

- add a `collect` CLI command;
- rebuild `summary.csv` from request artifacts;
- rebuild run-level `diagnostics.json` from request/model/run artifacts;
- make `report` call collect first when final files are missing or stale;
- mark partial runs clearly in diagnostics;
- avoid duplicating large raw model outputs in run-level diagnostics.

Do not implement in this spec:

- new inference behavior;
- new report visual design;
- timing summary UI in the primary report;
- print/PDF CSS;
- async or parallel execution;
- SQLite or external database.

## CLI

Add:

```bash
python main.py collect --run results/<run_id>
```

Optional useful flags:

```bash
python main.py collect --run results/<run_id> --write-reports
python main.py collect --run results/<run_id> --strict
```

Required behavior:

- `collect` reads `run_manifest.json`, `run_state.json`, `requests/**`, `models/**`, and `errors.log`;
- writes `summary.csv`;
- writes `diagnostics.json`;
- exits successfully for partial runs unless `--strict` is supplied.

Implement collection logic in a small dedicated module, for example `src/collect.py`. Keep `main.py` as CLI wiring and keep `src/report.py` focused on rendering derived files.

`--strict` behavior:

- fail with nonzero exit if `run_manifest.json` is missing or invalid;
- fail if any request artifact JSON is malformed;
- fail if any manifest request is incomplete;
- fail if any request has `status: failed`.

Without `--strict`, malformed artifacts should become diagnostics warnings when possible, and partial runs should still produce derived files.

If `run.lock` exists, `collect` may still run in non-strict mode, but it must add a diagnostics warning that the run may still be active. In `--strict` mode, fail if `run.lock` exists.

Update existing command:

```bash
python main.py report --run results/<run_id>
```

It should:

1. run collection when `summary.csv` or `diagnostics.json` is missing or older than request artifacts;
2. generate `report.html`;
3. generate `diagnostics.html` when `diagnostics.json` exists.

## Source Of Truth

After this spec:

- request artifacts are canonical for request-level results;
- model artifacts are canonical for load/smoke/unload/GPU details;
- `summary.csv` and run-level `diagnostics.json` are derived files;
- HTML reports are derived files.

Document this in `PROJECT_GUIDE.md`.

## Summary CSV Rebuild

Rebuild `summary.csv` using:

```text
run_manifest.json
models.json
requests/<request_id>/normalized.json
requests/<request_id>/status.json
requests/<request_id>/diagnostics.json
```

Include one row per logical request attempt selected for reporting.

Deterministic mode:

- include the canonical request result;
- if a request has no successful result but has a failed status, include the failed row;
- if a request has only `running` or missing artifacts, include no row in `summary.csv` but count it as incomplete in diagnostics.

Keep existing summary columns compatible unless a new column is necessary.

Allowed new columns:

- `attempt`;
- `status`;
- `raw_path`;
- `normalized_path`;
- `request_diagnostics_path`.

When rebuilding rows, use the manifest/request metadata to fill fields that are not guaranteed to exist in `normalized.json`, including:

- `model_id`;
- `base_model_id`;
- `model_label`;
- `params`;
- `quant`;
- `quant_bits`;
- `image_id`;
- `image_path`;
- `image_rel_path`;
- `mode`;
- `prompt_version`;
- `response_format_requested`.

If the request failed before inference, for example because model loading failed in SPEC-18, write a failed summary row with empty tag fields and the status error.

Accumulation attempts are out of scope for this spec and are specified in SPEC-21.

## Run Diagnostics Rebuild

Rebuild `diagnostics.json` with the SPEC-15 top-level shape:

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

Add run-level fields:

```json
{
  "is_partial": true,
  "expected_request_count": 2016,
  "completed_request_count": 1223,
  "failed_request_count": 0,
  "running_or_incomplete_request_count": 793
}
```

If `run_complete.json` exists, `is_partial` should be false.

## Incomplete Requests

For requests present in `run_manifest.json` but missing successful/failed artifacts, add diagnostics warning:

```json
{
  "type": "incomplete_request",
  "request_id": "...",
  "model_label": "...",
  "image_id": "...",
  "mode": "en_free"
}
```

Do not create fake `summary.csv` rows for incomplete requests unless the status is explicitly `failed`.

Reports should use manifest/model order so missing cells are visible as empty cells in the answer matrix.

## Staleness Detection

Minimum acceptable behavior:

- if `summary.csv` is missing, collect must rebuild it;
- if `diagnostics.json` is missing, collect must rebuild it;
- if any request artifact is newer than `summary.csv` or `diagnostics.json`, collect should rebuild derived files.

Do not overcomplicate with checksums in this spec.

## Tests

Add or update tests for:

- `collect` rebuilds `summary.csv` from request artifacts;
- `collect` rebuilds `diagnostics.json`;
- partial runs are marked `is_partial: true`;
- complete runs are marked `is_partial: false`;
- incomplete manifest requests produce warnings;
- failed request artifacts appear in summary and diagnostics;
- deterministic mode does not duplicate rows;
- `report --run` triggers collect when derived files are missing;
- `report --run` does not fail for partial runs.

Accumulation-specific collection tests belong to SPEC-21.

## Check

Automated:

```bash
python -m pytest -q
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

Manual checks:

```bash
python main.py run --config config.smoke.yaml
python main.py collect --run results/<run_id>
python main.py report --run results/<run_id>
```

Manual partial-run check:

1. Use an existing interrupted run or interrupt a new multi-request run.
2. Run `python main.py collect --run results/<run_id>`.
3. Confirm `summary.csv`, `diagnostics.json`, and `report.html` represent the partial state honestly.

## Agent report

Fill this after implementation:

- Done: added `collect` pipeline from request artifacts (`run_manifest + requests/* + models.json`) to rebuild `summary.csv` and `diagnostics.json`; added staleness-driven auto-collect hook before `report`; added strict/non-strict behavior and lock warning semantics for collect.
- Changed files: `src/collect.py`, `main.py`, `README.md`, `PROJECT_GUIDE.md`, `tests/test_collect.py`, `specs/19-collect-merge-from-artifacts.md`.
- Checks run:
  - `python -m pytest -q tests/test_collect.py tests/test_report.py`
  - `python -m pytest -q`
  - `python main.py validate-config --config config.smoke.yaml`
  - `python main.py dry-run --config config.smoke.yaml`
- Notes: collect keeps graceful behavior for partial runs by emitting `incomplete_request` warnings and not creating fake summary rows for missing/running requests.
