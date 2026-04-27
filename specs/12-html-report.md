# SPEC-12 — HTML report

## Goal

Generate a static `report.html` for manual visual comparison of model outputs.

The report should be simple, local, and easy to open in a browser. No backend and no frontend build system are needed.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-07](./07-storage.md)
- [SPEC-11](./11-summary-csv.md)

Expected files:

- `src/report.py`
- `src/storage.py`
- `tests/test_report.py`
- `README.md`
- `requirements.txt`

## Tasks

- Add `report` CLI command:

```bash
python main.py report --run results/<run_id>
```

- Generate `results/<run_id>/report.html`.
- Read data from `summary.csv` and normalized JSON files.
- Add a model summary section with:
  - request count;
  - average latency;
  - parse success rate;
  - schema success rate;
  - line fallback rate;
  - pool violations;
  - errors;
  - context warnings;
  - load and VRAM diagnostics when available.
- Add a gallery section:
  - original image or thumbnail;
  - model label;
  - mode;
  - accepted tags;
  - rejected tags/IDs;
  - error message if any.
- Generate thumbnails under `assets/thumbs/` using configured `report.thumbnail_size`.
- Use Pillow for thumbnail generation and add it to `requirements.txt` if it is not already present.
- If thumbnail generation fails for an image, keep report generation working and fall back to the original image path when safe.
- Escape HTML content safely.
- Keep the report dependency-light.
- Do not add React, a backend server, or a frontend build system.

## Check

Manual check:

```bash
python main.py report --run results/<run_id>
```

Then open:

```text
results/<run_id>/report.html
```

Automated check:

```bash
pytest
```

Tests should cover:

- report file is created;
- HTML is escaped;
- model summary includes key metrics;
- gallery includes image entries and tags;
- thumbnail generation uses configured size;
- missing thumbnails or missing optional diagnostics do not crash report generation;
- Pillow dependency is present if thumbnails are implemented with Pillow.

## Agent report

Fill this after implementation:

- Done: Added `report` CLI command and static HTML report generation from `summary.csv`, with model summary metrics, gallery cards, safe HTML escaping, and thumbnail generation via Pillow with graceful fallback.
- Changed files: `src/report.py`, `main.py`, `tests/test_report.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`.
- Notes: Thumbnail size is read from `run_config.yaml` when present; missing/failed thumbnail generation does not stop report creation.
