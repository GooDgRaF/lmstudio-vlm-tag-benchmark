# SPEC-21 — Accumulate result mode

## Goal

Add accumulation mode for repeated benchmark attempts without overwriting previous results.

After SPEC-18 and SPEC-19, deterministic request artifacts are the canonical source of truth. This spec adds:

- multiple attempts per logical request;
- append-only attempt directories;
- collection/report behavior that preserves attempts honestly.

This is useful when the user wants to rerun the same model/image/mode request several times and compare stability, randomness, latency, or prompt sensitivity without losing earlier attempts.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-18 Resumable request artifacts](./18-resumable-request-artifacts.md)
- [SPEC-19 Collect and merge from request artifacts](./19-collect-merge-from-artifacts.md)
- [SPEC-20 Report statistics and print-friendly output](./20-report-statistics-and-print.md)

Expected files:

- `src/config.py`
- `src/runner.py`
- `src/storage.py`
- `src/collect.py`
- `src/report.py`
- `tests/test_config.py`
- `tests/test_runner.py`
- `tests/test_storage.py`
- `tests/test_report.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Scope

Implement in this spec:

- add `accumulate` as a supported `runtime.result_mode`;
- store each attempt in a numbered attempt directory;
- keep `request.json` as the logical request descriptor;
- write attempt artifacts atomically;
- make `collect` preserve attempts in `summary.csv`;
- make primary `report.html` choose a documented attempt per matrix cell;
- make diagnostics expose all attempts;
- update docs and tests.

Do not implement in this spec:

- async or parallel inference;
- statistical judge-model evaluation;
- SQLite or external database;
- new prompt modes;
- PDF generation;
- UI for interactively switching attempts.

## Config

Extend runtime result mode:

```yaml
runtime:
  result_mode: accumulate
  resume: true
  retry_failed: true
```

Allowed `result_mode` values after this spec:

- `deterministic`;
- `overwrite`;
- `accumulate`.

Semantics:

- `accumulate` never overwrites previous attempt artifacts;
- every scheduled logical request creates a new attempt number when the runner reaches it;
- `resume: true` reuses the existing run manifest for `--run-id`, but it does not skip previous successful attempts;
- stale `running` attempts remain visible as incomplete; a later run creates a new attempt instead of replacing them;
- `retry_failed` does not replace failed attempts in accumulate mode; reruns create a new attempt.

## Artifact Layout

Use this layout:

```text
results/<run_id>/requests/<request_id>/
  request.json
  attempts/
    001/
      status.json
      raw.json
      normalized.json
      diagnostics.json
    002/
      status.json
      raw.json
      normalized.json
      diagnostics.json
```

`request.json` describes the logical request and must remain stable across attempts.

Attempt numbers:

- start at `001`;
- increment by one for each new attempt under the same request id;
- use zero-padding so lexical order matches numeric order;
- never reuse an attempt number, even if a previous attempt failed or is incomplete.

## Status

Use the SPEC-18 `status.json` shape, with `attempt` set to the numeric attempt:

```json
{
  "schema_version": 1,
  "request_id": "...",
  "status": "success",
  "attempt": 2,
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

Before sending a request, write the attempt status as `running`. After completion, replace it with `success` or `failed`.

## Runner Behavior

For `result_mode: accumulate`:

1. Build or load the run manifest as in SPEC-18.
2. For every manifest request selected by the run, allocate the next attempt directory.
3. Write `running` status before inference.
4. Save `raw.json`, `normalized.json`, `diagnostics.json`, and final status inside the attempt directory.
5. Continue after failed attempts.
6. For model load failures, create failed attempt statuses for every request belonging to that model.

Do not write or replace canonical deterministic files:

```text
requests/<request_id>/status.json
requests/<request_id>/raw.json
requests/<request_id>/normalized.json
requests/<request_id>/diagnostics.json
```

Only `request.json` lives directly under `requests/<request_id>/`.

## Collection

Update `collect` from SPEC-19.

For `result_mode: accumulate`:

- include one `summary.csv` row per attempt;
- add/populate the `attempt` column;
- add/populate the `status` column;
- include failed attempts as failed rows;
- do not create fake rows for missing or malformed attempts;
- add diagnostics warnings for malformed or `running` attempts.

Run-level diagnostics should include:

```json
{
  "attempt_count": 0,
  "successful_attempt_count": 0,
  "failed_attempt_count": 0,
  "running_or_incomplete_attempt_count": 0
}
```

Request diagnostics should expose each attempt separately. Include `attempt` and paths to attempt artifacts.

## Primary Report

The primary answer matrix remains one cell per image/mode/model.

For accumulate mode, select one attempt per cell using this rule:

1. latest successful attempt;
2. otherwise latest failed attempt;
3. otherwise empty cell.

Answer cells still render tags only. Attempt count, failed attempts, and running attempts belong in `diagnostics.html`, not in matrix cells.

The top summary from SPEC-20 should show that the run uses `accumulate` mode and should count attempts separately from logical requests when diagnostics provide both values.

## Diagnostics Report

`diagnostics.html` should make attempts visible enough for debugging:

- show attempt number in request diagnostics;
- show status;
- link to attempt `raw.json`, `normalized.json`, and `diagnostics.json`;
- include warnings for incomplete attempts.

Do not duplicate large raw model outputs into run-level diagnostics.

## Tests

Add or update tests for:

- config accepts `runtime.result_mode: accumulate`;
- runner creates `attempts/001`;
- second run with the same `--run-id` creates `attempts/002`;
- attempt numbering does not reuse failed or running attempts;
- failed model load creates failed attempt statuses for all requests of that model;
- collect writes one `summary.csv` row per attempt;
- collect populates `attempt` and `status`;
- diagnostics count successful, failed, and incomplete attempts;
- primary report selects latest successful attempt;
- primary report falls back to latest failed attempt only for ordering but keeps answer cell tag-only;
- diagnostics report shows attempt numbers and artifact links.

## Check

Automated:

```bash
python -m pytest -q
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

Manual checks:

```bash
python main.py run --config config.smoke.yaml --run-id accumulate-smoke
python main.py run --config config.smoke.yaml --run-id accumulate-smoke
python main.py collect --run results/accumulate-smoke
python main.py report --run results/accumulate-smoke
```

Inspect:

```text
results/accumulate-smoke/requests/<request_id>/attempts/001/
results/accumulate-smoke/requests/<request_id>/attempts/002/
results/accumulate-smoke/summary.csv
results/accumulate-smoke/diagnostics.html
```

## Agent report

Fill this after implementation:

- Done: implemented `runtime.result_mode: accumulate` as append-only attempts per logical request (`attempts/001..N`), including attempt status/raw/normalized/diagnostics artifacts; updated collect to emit one `summary.csv` row per attempt with `attempt/status`; added run diagnostics attempt counters; updated report selection to prefer latest successful attempt (fallback to latest failed) while keeping answer cells tag-only.
- Changed files: `src/storage.py`, `src/runner.py`, `src/collect.py`, `src/report.py`, `tests/test_collect.py`, `tests/test_report.py`, `README.md`, `PROJECT_GUIDE.md`, `specs/21-accumulate-result-mode.md`.
- Checks run:
  - `python -m pytest -q tests/test_collect.py tests/test_report.py tests/test_runner.py`
  - `python -m pytest -q`
  - `python main.py validate-config --config config.smoke.yaml`
  - `python main.py dry-run --config config.smoke.yaml`
- Notes: deterministic/overwrite behavior remains supported; accumulate mode avoids writing canonical per-request status/raw/normalized/diagnostics files and stores attempt artifacts only under `attempts/`.
