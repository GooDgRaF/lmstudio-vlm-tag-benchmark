# User Manual

## What It Does

Runs local VLM models through LM Studio, asks them to tag images, and writes:

- raw model responses;
- normalized parsed responses;
- `summary.csv`;
- `report.html`;
- `diagnostics.html`.

## Quick Start

1. Start the LM Studio server on `localhost:1234`.
2. Put images into `ImgToTag/`.
3. Generate the user config:

```bash
python main.py init-config
```

4. Edit `config.yaml`:

- keep the model labels you want under `models`;
- keep the modes you want under `modes`;
- optionally change `images_folder` or `limit_images`.

5. Check the plan without inference:

```bash
python main.py dry-run --config config.yaml
```

6. Run:

```bash
python main.py run --config config.yaml
```

## Useful Commands

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

## Outputs

Open these after a run:

- `results/<run_id>/report.html`: main answer matrix;
- `results/<run_id>/diagnostics.html`: technical diagnostics;
- `results/<run_id>/summary.csv`: table for analysis.

`collect --write-reports` rebuilds summary and reports from request artifacts.

## Notes

- `dry-run` validates and prints request counts only.
- `run` sends real requests to LM Studio.
- `pool_validation_failed` means the model returned values outside the configured pool.
- Some reasoning-capable models may write reasoning into the final answer; the report marks this as `thought anyway` when detected.
