# SPEC-02 — Config validation

## Goal

Implement practical validation for `config.example.yaml` and model entries before any benchmark run starts.

The program should catch obvious config mistakes early and explain them clearly.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [Active models](../models/models.active.yaml)
- [Excluded models](../models/models.excluded.yaml)
- [SPEC-01](./01-project-skeleton.md)

Expected files:

- `src/config.py`
- `src/validator.py`
- `tests/test_config.py`
- `tests/test_validator.py`

## Tasks

- Parse the main YAML config into a simple typed structure or validated dictionaries.
- Validate required top-level sections: `lmstudio`, `models`, `input`, `output`, `modes`, `pools`, `generation`, `load`, `limits`, `response_formats`, `validation`, `diagnostics`, `runtime`, `report`, `evaluation`.
- Validate model fields used by the runner: `id`, `base_model_id`, `label`, `params`, `quant`, `quant_bits`, `max_context_length`.
- Validate that model labels are unique.
- Validate that `load.context_length` does not exceed a model's known `max_context_length` when that value is present.
- Validate that all configured modes are known.
- Validate that configured pool file paths exist.
- Keep validation simple. Do not add a large schema framework unless it is already clearly useful.

## Check

Manual check:

```bash
python main.py validate-config --config config.example.yaml
```

Automated check:

```bash
pytest
```

Tests should cover:

- valid example config passes;
- missing required section fails;
- duplicate model label fails;
- unknown mode fails;
- context length larger than model maximum fails;
- missing pool file fails.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
