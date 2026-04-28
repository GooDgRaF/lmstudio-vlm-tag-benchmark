# SPEC-16 — Diagnostics HTML report

## Goal

Add a separate human-readable diagnostics report:

```text
results/<run_id>/diagnostics.html
```

`diagnostics.html` is for service information, debugging, and reproducibility. It complements the primary answer matrix from SPEC-14 and renders the structured data created by SPEC-15.

The primary `report.html` should stay focused on answers. `diagnostics.html` should contain the deeper runtime details.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-14 HTML answer matrix](./14-html-answer-matrix.md)
- [SPEC-15 Diagnostics data contract](./15-diagnostics-data-contract.md)

Expected files:

- `src/report.py`
- `src/storage.py`
- `tests/test_report.py`
- `PROJECT_GUIDE.md`
- `AGENTS.md`

## Prerequisite

Implement this spec only after SPEC-15 is complete.

The primary input is:

```text
results/<run_id>/diagnostics.json
```

If `diagnostics.json` is missing for an old run, generation may create a limited fallback report from `summary.csv`, `models/<model_label>/*.json`, and `errors.log`. The fallback is optional and should remain simple. Do not recreate the full SPEC-15 data contract in this spec.

## Scope

Implement in this spec:

- generate `diagnostics.html`;
- link `report.html` to `diagnostics.html` when both exist;
- link `diagnostics.html` back to `report.html`;
- render run, model, request, pool, load/smoke/unload, GPU, warning, and error-log diagnostics;
- keep the page plain static HTML/CSS with optional small vanilla JavaScript filters.

Do not implement in this spec:

- new diagnostics collection beyond fields already available from SPEC-15;
- changes to benchmark execution behavior;
- primary answer matrix redesign;
- frontend frameworks, build steps, servers, React, or heavy client-side code.

## Inputs

Primary:

```text
results/<run_id>/diagnostics.json
```

Additional optional inputs:

```text
results/<run_id>/summary.csv
results/<run_id>/models/<model_label>/*.json
results/<run_id>/errors.log
```

Use `diagnostics.json` as the source of truth when present.

## Output

Create or overwrite:

```text
results/<run_id>/diagnostics.html
```

When both reports are generated:

- `report.html` should link to `diagnostics.html`;
- `diagnostics.html` should link back to `report.html`.

Manual command remains:

```bash
python main.py report --run results/<run_id>
```

After this spec, that command should generate or refresh both HTML files when the needed inputs exist.

## Purpose

`diagnostics.html` should answer:

- Did the run complete as expected?
- Which model failed and why?
- Which requests had pool violations?
- Are errors concentrated in a model, image, mode, or response format?
- Did context limits or output truncation matter?
- What were the load/unload and smoke-test results?
- What did VRAM look like before/after load and unload?
- Where are raw and normalized files for a suspicious request?
- Were duplicate summary rows detected?

## Layout

Use plain static HTML/CSS. No backend, no frontend build system, no React.

Required sections:

1. Run overview.
2. Model diagnostics summary.
3. Request diagnostics table.
4. Pool diagnostics.
5. Load, smoke, unload, and GPU details.
6. Warnings.
7. Error log.

Keep the page dense and table-oriented. This is a tool page, not a gallery.

## Run Overview

Show compact run-level fields from `diagnostics.run`:

- run id;
- started/finished/duration;
- git commit, if available;
- config path;
- image count;
- model count;
- mode count;
- request count;
- success/error counts;
- pool violation count.

## Model Diagnostics Summary

Show one row per model.

Required columns:

- model label;
- params;
- quant;
- load ok;
- load duration;
- smoke-test ok;
- request count;
- error count;
- pool violation count;
- avg/median/min/max latency;
- parse ok rate;
- schema ok rate;
- pool ok rate;
- requested/actual context length;
- unload ok.

Recommended GPU columns:

- GPU before load;
- GPU after load;
- GPU after unload.

Long errors should be collapsed or shown in a smaller detail area, not forced into wide table columns.

## Request Diagnostics Table

Show one row per request.

Required columns:

- image id or short image label;
- mode;
- model label;
- latency;
- response format requested/used;
- parse ok;
- schema ok;
- pool ok;
- pool violations;
- error type;
- finish reason;
- prompt/completion/total tokens;
- context near limit;
- context overflow;
- output truncated;
- accepted/rejected counts;
- raw file link;
- normalized file link.

The table can be wide. Prefer horizontal scrolling.

Optional filters with vanilla JS:

- only errors;
- only pool violations;
- model select;
- mode select.

Filters are optional. If implemented, they must not be required for reading the page.

## Pool Diagnostics

Show one row per pool file:

- pool key;
- path;
- type;
- tag/entry count;
- id prefixes for explained pools;
- sha256.

This helps interpret old runs after pool files change.

## Load, Smoke, Unload, And GPU Details

Show per-model details from `diagnostics.models`.

Optional supporting files may be linked or summarized:

```text
models/<model_label>/load.json
models/<model_label>/smoke_test.json
models/<model_label>/gpu_before_load.json
models/<model_label>/gpu_after_load.json
models/<model_label>/gpu_after_unload.json
```

Keep JSON details readable:

- use escaped `<pre>` blocks for compact JSON snippets;
- do not dump enormous payloads;
- show missing optional files as `not available`.

## Warnings

Render `diagnostics.warnings`.

At minimum, duplicate summary row warnings from SPEC-15 should be visible with:

- warning type;
- image id;
- mode;
- model label;
- count;
- used request id.

## Error Log

If `errors.log` exists, include it near the bottom.

Rules:

- preserve line breaks;
- escape HTML;
- keep it visually secondary;
- avoid making it the first thing the user sees.

## Safety And Escaping

All user/model-provided text must be HTML-escaped:

- tags;
- IDs;
- errors;
- warnings;
- file names;
- paths;
- raw snippets;
- JSON snippets.

Do not inline raw model HTML.

## Styling

Preferred visual character:

- utilitarian;
- compact;
- readable tables;
- restrained color;
- clear ok/warn/error badges.

Suggested classes:

- `.ok`;
- `.warn`;
- `.error`;
- `.muted`;
- `.mono`;
- `.scroll-table`.

## Fallback Behavior

If `diagnostics.json` is missing:

- `python main.py report --run results/<run_id>` should still regenerate `report.html`;
- `diagnostics.html` may be skipped, or a limited fallback page may be generated;
- if a fallback page is generated, clearly mark it as limited.

Do not fail report generation solely because `diagnostics.json` is missing.

## Tests

Add or update tests for:

- `diagnostics.html` is created when `diagnostics.json` exists;
- `diagnostics.html` links back to `report.html`;
- `report.html` links to `diagnostics.html` when both exist;
- run overview fields render;
- model diagnostics table renders;
- request diagnostics table renders;
- pool diagnostics render;
- warnings render, including duplicate summary row warnings;
- `errors.log` is escaped and included when present;
- missing optional model JSON files do not crash report generation;
- missing `diagnostics.json` does not prevent `report.html` regeneration;
- HTML escaping prevents raw model/user text from becoming markup.

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

Then open:

```text
results/<run_id>/report.html
results/<run_id>/diagnostics.html
```

Manual review expectations:

- answer comparison remains in `report.html`;
- diagnostics are easy to find but separate;
- diagnostic tables are dense and readable;
- links between reports work;
- errors and pool violations are easy to locate;
- duplicate warnings are visible when present.

## Agent report

Fill this after implementation:

- Done:
- Done: Added `diagnostics.html` generation from `diagnostics.json`, linked `report.html` -> `diagnostics.html` when available, added back-link from diagnostics page to answer matrix, and updated CLI/report flow to refresh both reports.
- Changed files: src/report.py; src/runner.py; main.py; tests/test_report.py; README.md; PROJECT_GUIDE.md; AGENTS.md
- Checks run: python -m pytest -q; python main.py validate-config --config config.smoke.yaml; python main.py dry-run --config config.smoke.yaml
- Notes: Diagnostics rendering is static table-first HTML and intentionally keeps heavy payloads in linked JSON artifacts.
