# SPEC-05 — Image discovery

## Goal

Find input images from the configured folder and assign stable image IDs.

This stage should not call any model yet.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-02](./02-config-validation.md)

Expected files:

- `src/image_loader.py`
- `tests/test_image_loader.py`
- `README.md`

## Tasks

- Read image discovery settings from config:
  - `input.image_dir`;
  - `input.recursive`;
  - `input.extensions`.
- Support v1 extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`.
- Make extension matching case-insensitive.
- Default to non-recursive traversal.
- Return images in stable sorted order.
- Add stable `image_id` values suitable for filenames and CSV rows.
- Build `image_id` from the image path relative to `input.image_dir`.
- Use a short hash or safe slug so `image_id` remains deterministic and Windows-safe.
- Store both the absolute/original `image_path` and the relative `image_rel_path` in image metadata.
- Add `--limit N` support for quick test runs.
- Apply `--limit N` after stable sorting.
- Add a `dry-run` CLI command that validates config and prints models, modes, and discovered image count.
- Do not send images to LM Studio yet.

## Check

Manual check:

```bash
python main.py dry-run --config config.example.yaml --limit 1
```

Automated check:

```bash
pytest
```

Tests should cover:

- only configured extensions are included;
- extension matching is case-insensitive;
- recursive mode can be enabled;
- non-recursive mode ignores nested files;
- limit is applied after stable sorting;
- `image_id` is deterministic for the same relative path;
- `image_id` is Windows-safe;
- both `image_path` and `image_rel_path` are available;
- missing image directory gives a clear error.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
