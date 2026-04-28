# SPEC-14 — HTML answer matrix report

## Goal

Refine the primary HTML report so it is optimized for manual comparison of model answers.

This spec changes only the main report:

```text
results/<run_id>/report.html
```

The report should show user-facing answers in a matrix:

```text
image x mode x model -> answer
```

Runtime diagnostics, token counts, GPU details, load details, and error logs are out of scope for this spec. They are handled later by SPEC-15 and SPEC-16.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [Previous HTML report spec](./archive/12-html-report.md)
- [SPEC-15 Diagnostics data contract](./15-diagnostics-data-contract.md)
- [SPEC-16 Diagnostics HTML report](./16-diagnostics-html-report.md)

Expected files:

- `src/report.py`
- `tests/test_report.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Scope

Implement in this spec:

- replace the current gallery-style primary report with an answer matrix;
- keep report generation plain static HTML/CSS;
- generate best-effort thumbnails under `results/<run_id>/assets/thumbs/`;
- keep answer cells focused on accepted/rejected tags and compact error states;
- keep manual report regeneration working through `python main.py report --run results/<run_id>`.

Do not implement in this spec:

- `diagnostics.json`;
- `diagnostics.html`;
- detailed diagnostics tables;
- new runner diagnostics aggregation;
- frontend frameworks, build steps, servers, or JavaScript-heavy UI.

If `results/<run_id>/diagnostics.html` already exists, `report.html` may link to it. This spec must not require creating `diagnostics.html`.

## Inputs

The report is generated from existing run artifacts:

- `results/<run_id>/summary.csv`;
- `results/<run_id>/run_config.yaml`, if available;
- original image paths from summary rows.

Optional fallback inputs:

- `results/<run_id>/normalized/*.json`, only if a value needed for an answer cell is missing from `summary.csv`.

Do not require `diagnostics.json` or `diagnostics.html`.

The runner should continue to create `report.html` automatically when:

```yaml
report:
  generate_html: true
```

Manual report generation should still work:

```bash
python main.py report --run results/<run_id>
```

## Output

Create or overwrite:

```text
results/<run_id>/report.html
```

Do not create `diagnostics.html` in this spec.

## Primary Report Purpose

`report.html` should answer:

- What did each model return for this image?
- How do model answers differ for the same mode?
- Which tags were accepted?
- Which tags were invented or rejected by pool validation?
- Which cells failed to produce a usable answer?

It should not be the place for detailed latency, token, context, GPU, response-format, load, unload, or smoke-test diagnostics.

## Layout

Use an answer matrix:

```text
| Image | Mode | Model 1 | Model 2 | Model 3 | ... |
```

Rows are grouped by image. Each image group contains one row per mode.

The image cell should span all mode rows for that image when practical. If row spanning makes the implementation brittle, repeating a compact image label per mode is acceptable, but each image group must remain visually clear.

Recommended mode labels:

```text
ru_free            -> RU free
ru_pool            -> RU pool
ru_pool_explained  -> RU pool+
en_free            -> EN free
en_pool            -> EN pool
en_pool_explained  -> EN pool+
```

`pool+` means ID-based explained-pool mode.

## Image Column

For each image group, show:

- thumbnail;
- image display label;
- relative image path or short image id;
- optional link to the original image path.

Thumbnail generation:

```text
results/<run_id>/assets/thumbs/
```

Thumbnail generation must remain best-effort. Report generation must not fail if Pillow cannot open an image or the original image path is unavailable.

Use a stable thumbnail filename derived from `image_id` or sanitized image path. Do not create one duplicate thumbnail per model/mode request if several rows reference the same image.

## Model Columns

Each configured or observed model gets a column.

Column headers should use `model_label` from `summary.csv`.

Model order:

1. If `models.json` exists, use the order from `models.json`.
2. Otherwise use stable first appearance in `summary.csv`.

If there are many models, the table may be wider than the viewport. Prefer horizontal scrolling over squeezing the content.

Recommended layout behavior:

- sticky model header;
- sticky left image/mode columns if practical with plain HTML/CSS;
- clear vertical separators between model columns;
- clear horizontal separators between image groups.

## Answer Cell

Each cell represents one `(image_id, mode, model_label)` request.

The cell should show answer content only:

- accepted tags;
- rejected tags;
- rejected IDs;
- compact error state if there is no usable answer.

Do not show latency, token counts, context flags, GPU memory, raw JSON, load config, response-format details, stack traces, or long backend messages in answer cells.

Accepted tags:

- show as neutral tag chips or compact wrapped text;
- preserve tag text;
- keep the cell readable when there are many tags.

Rejected tags / invented tags:

- show in a visually distinct style;
- use a warm warning color or red-tinted chip;
- label the group as `out of pool` or another short equivalent.

Rejected IDs:

- show separately from rejected tag text;
- use monospace styling for IDs if helpful.

Errors:

- show a compact error badge or short error type;
- trim long error messages;
- do not print long stack traces or large API messages.

Empty result:

- show a muted empty state such as `no answer`.

Missing matrix cell:

- show a muted placeholder such as `not run`.

## Top Summary

At the top of `report.html`, include a compact summary bar:

- run id;
- image count;
- model count;
- mode count;
- request count;
- total errors;
- total pool violations.

The summary should support orientation, not dominate the report.

## Legend

Include a compact legend for:

- mode labels;
- accepted tag style;
- out-of-pool / rejected tag style;
- error state;
- missing/not-run state.

Keep the legend short and close to the matrix.

## Data Grouping Rules

Build the matrix primarily from `summary.csv`.

Group and sort:

1. Images by stable first appearance in `summary.csv`.
2. Modes by configured mode order from `run_config.yaml`.
3. If `run_config.yaml` is unavailable, use the canonical order from this spec.
4. Models by `models.json` order when available, otherwise stable first appearance in `summary.csv`.

If duplicate rows exist for the same `(image_id, mode, model_label)`, use the last row in `summary.csv` for the matrix cell. Add a small non-blocking note near the summary such as `Duplicate request rows: N`. Detailed duplicate diagnostics are deferred to SPEC-15.

## Styling Rules

Use plain HTML/CSS and optional small vanilla JavaScript only if it directly improves navigation.

Preferred visual character:

- quiet benchmark tool;
- dense but readable;
- high contrast text;
- no decorative hero;
- no card gallery as the main report;
- no nested cards;
- no frontend build step.

Recommended features:

- horizontal scroll wrapper around the matrix;
- sticky header;
- compact tag chips;
- image-group separators;
- model column separators;
- responsive behavior that remains usable on narrow screens.

All user/model-provided text must be HTML-escaped:

- tags;
- IDs;
- errors;
- model labels;
- image paths;
- file names.

Do not inline raw model HTML.

## Tests

Update or add tests for:

- `report.html` is created;
- main report contains answer matrix structure;
- main report groups rows by image and mode;
- model labels appear as columns;
- configured model order is respected when `models.json` exists;
- accepted tags are visible in answer cells;
- rejected tags and rejected IDs are visible with distinct classes/text;
- compact error state is visible without dumping long diagnostics;
- diagnostic fields such as latency, token counts, context flags, and GPU memory are absent from answer cells;
- duplicate rows use the last row and show a compact duplicate note;
- missing matrix cells render a muted placeholder;
- HTML escaping prevents raw model/user text from becoming markup;
- thumbnail generation remains best-effort;
- if `diagnostics.html` already exists, `report.html` links to it;
- if `diagnostics.html` does not exist, report generation still succeeds.

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
```

Manual review expectations:

- `report.html` starts with the compact summary and answer matrix;
- each image group is easy to identify;
- each image has one row per configured mode;
- each model is a column;
- accepted tags are easy to scan;
- invented/out-of-pool tags are visually distinct;
- detailed diagnostics are not mixed into the main answer matrix.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
