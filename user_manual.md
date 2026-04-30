# User Manual (Short)

## 1. What this project does

Runs local VLM models via LM Studio on images and saves:
- raw responses;
- normalized responses;
- `summary.csv`;
- HTML reports (`report.html`, `diagnostics.html`).

## 2. Quick start

1. Start LM Studio server on `localhost:1234`.
2. Put images into your input folder (default: `ImgToTag`).
3. Generate user config:

```bash
python main.py init-config
```

4. Edit `config.yaml`:
- keep only needed model labels in `models`;
- keep only needed modes in `modes`;
- optionally change `images_folder` / `limit_images`.

5. Check plan (no inference):

```bash
python main.py dry-run --config config.yaml
```

6. Run benchmark:

```bash
python main.py run --config config.yaml
```

## 3. Core commands

```bash
python main.py init-config
python main.py refresh-models
python main.py list-models
python main.py validate-config --config config.yaml
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
python main.py report --run results/<run_id>
python main.py collect --run results/<run_id> --write-reports
```

## 4. Where to look after run

- `results/<run_id>/report.html` — main answer matrix
- `results/<run_id>/diagnostics.html` — technical diagnostics
- `results/<run_id>/summary.csv` — tabular summary

## 5. Notes

- `dry-run` validates and prints request counts only.
- `run` sends real requests to LM Studio and writes artifacts.
- `pool_validation_failed` is a quality signal, not always a code bug.
