# SPEC-14 — HTML answer matrix report

## Goal

Refine the primary HTML report so it is optimized for manual comparison of model answers.

The main `report.html` should show only user-facing answers in a matrix:

```text
image x mode x model -> answer
```

Diagnostic and service information must be moved out of the primary report into a separate HTML file. The main report should be pleasant to scan visually and should not feel like a log viewer.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [Previous HTML report spec](./archive/12-html-report.md)

Expected files:

- `src/report.py`
- `tests/test_report.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Current Inputs

The report is generated from:

- `results/<run_id>/summary.csv`;
- `results/<run_id>/run_config.yaml`;
- `results/<run_id>/raw/*.json`;
- `results/<run_id>/normalized/*.json`;
- original image paths from summary rows.

The runner should continue to create reports automatically when:

```yaml
report:
  generate_html: true
```

Manual report generation should still work:

```bash
python main.py report --run results/<run_id>
```

## Primary Report: `report.html`

### Purpose

`report.html` is the main manual review surface. It should answer:

- What did each model return for this image?
- How do model answers differ for the same mode?
- Which tags were accepted?
- Which tags were invented or rejected by pool validation?
- Which cells failed to produce a usable answer?

It should not be the place for detailed latency, token, context, GPU, response-format, or load diagnostics.

### Layout

Use an answer matrix:

```text
| Image | Mode | Model 1 | Model 2 | Model 3 | ... |
```

Rows are grouped by image. Each image group contains one row per mode.

The image cell should span all mode rows for that image.

Recommended mode labels:

```text
RU free
RU pool
RU pool+
EN free
EN pool
EN pool+
```

Where `pool+` means ID-based explained-pool mode.

Mode mapping:

```text
ru_free            -> RU free
ru_pool            -> RU pool
ru_pool_explained  -> RU pool+
en_free            -> EN free
en_pool            -> EN pool
en_pool_explained  -> EN pool+
```

### Image Column

For each image group, show:

- thumbnail;
- image display label;
- relative image path or short image id;
- optional link to the original image path.

The thumbnail should be generated under:

```text
results/<run_id>/assets/thumbs/
```

Thumbnail generation must remain best-effort: report generation should not fail if Pillow cannot open an image.

### Model Columns

Each configured model gets a column.

Column headers should use `model_label` from `summary.csv`.

If there are many models, the table may be wider than the viewport. Prefer horizontal scrolling over squeezing the content.

Recommended layout behavior:

- sticky model header;
- sticky left image/mode columns if practical with plain HTML/CSS;
- clear vertical separators between model columns;
- clear horizontal separators between image groups.

Do not add a frontend framework or build system.

### Answer Cell

Each cell represents one `(image_id, mode, model_label)` request.

The cell should show answer content only:

- accepted tags;
- rejected tags;
- rejected IDs;
- compact error state if there is no usable answer.

Do not show latency, token counts, context flags, GPU memory, raw JSON, load config, or response format details in this cell.

Accepted tags:

- show as neutral tag chips or compact wrapped text;
- preserve tag text;
- keep the cell readable when there are many tags.

Rejected tags / invented tags:

- show in a visually distinct style;
- use a warm warning color or red-tinted chip;
- label the group as `out of pool` or equivalent short text.

Rejected IDs:

- show separately from rejected tag text;
- use monospace styling for IDs if helpful.

Errors:

- show a compact error badge or short message;
- do not print long stack traces or large API messages in the main matrix;
- link or refer to diagnostics report when details exist.

Empty result:

- show a muted empty state such as `no answer`.

### Top Summary

At the top of `report.html`, include a compact summary bar:

- run id;
- image count;
- model count;
- request count;
- total errors;
- total pool violations.

Keep it small. It should support orientation, not dominate the report.

### Legend

Include a compact legend for:

- mode labels;
- accepted tag style;
- out-of-pool / rejected tag style;
- error state.

The legend should be short and close to the matrix.

## Diagnostics Report

Move service and diagnostic information to a separate file:

```text
results/<run_id>/diagnostics.html
```

`diagnostics.html` should include information that is not part of the main visual answer comparison:

- model summary metrics;
- request count;
- average latency;
- parse success rate;
- schema success rate;
- line fallback rate;
- pool violations;
- errors;
- context warnings;
- token usage;
- requested and actual context length;
- response format requested/used;
- GPU before/after;
- load diagnostics;
- smoke-test diagnostics;
- detailed per-request diagnostic table.

It may be denser than `report.html`, but must still escape HTML safely.

The primary report should link to `diagnostics.html` when it exists.

## Data Grouping Rules

Build the matrix from `summary.csv`.

Group and sort:

1. Images by stable first appearance in `summary.csv`.
2. Modes by configured mode order from `run_config.yaml`; fall back to the canonical order from this spec.
3. Models by stable first appearance in `summary.csv`.

For a missing `(image_id, mode, model_label)` cell, show a muted placeholder.

If duplicate rows exist for the same key, prefer the last row and include a diagnostics note in `diagnostics.html`.

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

## Tests

Update or add tests for:

- `report.html` is created;
- `diagnostics.html` is created;
- main report contains answer matrix structure;
- main report groups rows by image and mode;
- model labels appear as columns;
- accepted tags are visible in answer cells;
- rejected tags and rejected IDs are visible with distinct classes/text;
- diagnostic fields are absent from primary answer cells;
- diagnostics report contains latency/token/context/model summary fields;
- HTML escaping still works;
- thumbnail generation remains best-effort.

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

- `report.html` starts with the compact summary and answer matrix;
- each image appears once on the left;
- each image has six mode rows;
- each model is a column;
- accepted tags are easy to scan;
- invented/out-of-pool tags are visually distinct;
- detailed diagnostics are not mixed into the main answer matrix;
- diagnostics are available in `diagnostics.html`.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
