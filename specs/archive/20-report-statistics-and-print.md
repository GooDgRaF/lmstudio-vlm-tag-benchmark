# SPEC-20 — Report statistics and print-friendly output

## Goal

Improve the primary answer report so it is useful both on screen and when printed/exported to PDF.

The main `report.html` should remain focused on tags in the answer matrix, but it should include a compact run summary above the matrix:

- completion status;
- request/image/model counts;
- fastest request;
- slowest request;
- average request latency;
- average image request-latency total;
- fastest image;
- slowest image.

The answer matrix cells should contain only tags. Diagnostics text belongs in `diagnostics.html`.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-14 HTML answer matrix](./14-html-answer-matrix.md)
- [SPEC-19 Collect and merge from request artifacts](./19-collect-merge-from-artifacts.md)

Expected files:

- `src/report.py`
- `tests/test_report.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Scope

Implement in this spec:

- add compact timing statistics to the top of `report.html`;
- compute image-level timing summaries from request diagnostics;
- keep answer cells tag-only;
- apply final chip colors:
  - free-mode invented tags: light blue;
  - pool-matched tags: light green;
  - out-of-pool rejected tags/IDs: light red;
- add print/PDF CSS;
- ensure `report.html` remains usable for partial runs.

Do not implement in this spec:

- new inference behavior;
- new storage artifacts;
- new diagnostics collection;
- PDF generation through browser automation;
- frontend framework or build step.

## Data Inputs

Use available derived files:

```text
summary.csv
diagnostics.json
run_manifest.json
run_state.json
```

Prefer `diagnostics.json` for timing fields when available. Fall back to `summary.csv.latency_sec` when needed.

This spec assumes SPEC-19 is complete. `report --run` should already collect stale or missing derived files before rendering. Do not reimplement collection logic in `src/report.py`.

## Top Summary

Add a compact summary block above the matrix.

Required fields:

- run id;
- completion: `complete` or `partial`;
- completed requests / expected requests;
- image count;
- model count;
- mode count;
- error count;
- pool violation count;
- average request latency;
- fastest request;
- slowest request;
- average image request-latency total;
- fastest image;
- slowest image.

Definitions:

- request latency: one model/image/mode call latency;
- image request-latency total: sum of request latencies for one image across available model/mode requests;
- fastest request: request with minimal positive latency;
- slowest request: request with maximal latency;
- fastest image: image with minimal positive total available request latency;
- slowest image: image with maximal total available request latency.

For partial runs, label image timing as based on completed/available requests only.

Do not imply that image timing includes model load, smoke-test, unload, queue time, or failed requests with no measured latency.

Keep the block small. It should not become a diagnostics dashboard.

## Answer Matrix Cell Rules

Cells must render tags only.

Allowed content:

- accepted tag chips;
- rejected tag chips;
- rejected ID chips.

Do not render in answer cells:

- `pool_validation_failed`;
- `request_error`;
- stack traces;
- backend error text;
- `not run`;
- `no answer`;
- token counts;
- latency;
- response format;
- context flags;
- GPU memory.

Empty cells are acceptable and mean that no tags are available for display.

## Tag Colors

Free modes:

```text
ru_free
en_free
```

Accepted tags from free modes:

- class: `chip free`;
- visual: light blue.

Pool modes:

```text
ru_pool
ru_pool_explained
en_pool
en_pool_explained
```

Accepted tags from pool modes:

- class: `chip ok`;
- visual: light green.

Rejected tags and rejected IDs:

- class: `chip warn`;
- visual: light red.

Use the same color rules in screen and print CSS.

## Print/PDF CSS

Add `@media print` rules.

Requirements:

- hide navigation links that are not useful in PDF;
- keep the summary and matrix visible;
- keep tag chip colors visible in print where browsers allow background printing;
- avoid clipping the left image/mode columns;
- use smaller font sizes suitable for wide tables;
- allow page breaks between image groups when practical;
- do not show diagnostics-only sections in `report.html`.

Implementation notes:

- add `print-color-adjust: exact` and `-webkit-print-color-adjust: exact` for chips;
- reset sticky positioning in print with `position: static` for sticky table columns/headers;
- reduce table padding and font size in print;
- add a stable class or grouping marker around image groups if needed for page-break rules.

Do not create a separate PDF file in this spec.

## Partial Run Behavior

If the run is partial:

- show `partial` in the summary;
- keep missing answer cells empty;
- do not show diagnostics warnings inside the answer matrix;
- link to `diagnostics.html` if available for details.

## Tests

Add or update tests for:

- top summary renders request/image/model/mode counts;
- complete vs partial state renders correctly;
- average request latency is computed;
- fastest and slowest request labels render;
- average/fastest/slowest image timing renders;
- free-mode tags use `chip free`;
- pool accepted tags use `chip ok`;
- rejected tags and IDs use `chip warn`;
- answer cells do not contain `pool_validation_failed`, `request_error`, backend error text, `not run`, or `no answer`;
- print CSS exists;
- HTML escaping still protects tag/model/image text.

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
python main.py report --run results/<run_id>
```

Open:

```text
results/<run_id>/report.html
```

Manual review expectations:

- summary is compact and readable;
- answer matrix still contains only tags;
- free/pool/rejected colors are visually distinct;
- browser print preview is usable;
- partial runs are clearly marked but not noisy inside the matrix.

## Agent report

Fill this after implementation:

- Done: expanded `report.html` top summary with complete/partial flag, completed/expected counts, avg/fastest/slowest request latency, avg/fastest/slowest image request-latency totals; kept matrix cells tag-only; added print CSS (`@media print`) with sticky reset, compact typography, and print color-adjust for chips.
- Changed files: `src/report.py`, `tests/test_report.py`, `README.md`, `PROJECT_GUIDE.md`, `specs/20-report-statistics-and-print.md`.
- Checks run:
  - `python -m pytest -q tests/test_report.py`
  - `python -m pytest -q`
  - `python main.py validate-config --config config.smoke.yaml`
  - `python main.py dry-run --config config.smoke.yaml`
- Notes: image timing summary is computed from available completed request latencies (diagnostics first, summary fallback), so partial runs are explicit but still report meaningful aggregates.
