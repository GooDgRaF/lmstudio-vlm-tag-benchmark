# SPEC-11 — Summary CSV

## Goal

Write `summary.csv` incrementally, with one row per model/image/mode request.

The CSV is the main table for Excel review and should be updated after every request, not only at the end of the run.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-07](./07-storage.md)
- [SPEC-09](./09-runner-loop.md)
- [SPEC-10](./10-resume.md)

Expected files:

- `src/storage.py`
- `src/runner.py`
- `tests/test_summary_csv.py`
- `README.md`

## Tasks

- Create `results/<run_id>/summary.csv` with a header before requests start.
- Append one row immediately after each normal model/image/mode request is processed.
- Do not write image smoke-test calls as normal request rows.
- Include the architecture's recommended fields where available:
  - run and request IDs;
  - model identity and quantization;
  - image identity and path;
  - `image_rel_path`;
  - mode;
  - `prompt_version`;
  - response format requested and used;
  - accepted and rejected tags/IDs;
  - parse/schema/pool flags;
  - latency;
  - token usage;
  - context diagnostics;
  - GPU memory before and after load;
  - error type and error message.
- Store list-like CSV values as JSON strings inside CSV cells.
- Make the CSV safe to open in Excel.
- Use UTF-8 with BOM for Windows Excel compatibility, or clearly document a different encoding decision in the README.
- Preserve existing rows when resume is used.
- Avoid duplicate rows for skipped successful requests during resume.

## Check

Manual check after a one-image run:

```bash
python main.py run --config config.example.yaml --limit 1
```

Expected result:

```text
results/<run_id>/summary.csv
```

Automated check:

```bash
pytest
```

Tests should cover:

- header is created;
- request rows are appended;
- `prompt_version` is written;
- `image_rel_path` is written;
- list values are serialized consistently as JSON strings;
- UTF-8 BOM or the documented encoding behavior is enforced;
- error rows are written;
- smoke-test calls are not written as normal rows;
- resume does not duplicate existing successful rows.

## Agent report

Fill this after implementation:

- Done: Implemented incremental `summary.csv` writing with header initialization, JSON-string serialization for list-like fields, UTF-8 BOM for Excel compatibility, and deduplication guard for resumed requests.
- Changed files: `src/storage.py`, `src/runner.py`, `tests/test_summary_csv.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`.
- Notes: Smoke-test requests are stored in model metadata and excluded from normal request rows.
