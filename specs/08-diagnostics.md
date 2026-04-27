# SPEC-08 — Diagnostics

## Goal

Add context and GPU diagnostics without making them fragile or mandatory.

Diagnostics should help compare models and understand failures, but they must not break the benchmark when optional data is unavailable.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-03](./03-lmstudio-client.md)
- [SPEC-07](./07-storage.md)

Expected files:

- `src/diagnostics.py`
- `tests/test_diagnostics.py`

## Tasks

- Add optional GPU memory collection through configured `nvidia-smi` command.
- Prefer the CSV-friendly query form when possible:

```bash
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader,nounits
```

- Record total, used, and free VRAM when available.
- If `nvidia-smi` is missing or fails, return `gpu_diagnostics_available: false` and continue.
- Keep the parser tolerant of minor output changes. Do not depend on localized table formatting.
- Classify model load errors:
  - `load_failed`;
  - `load_failed_oom` when the error looks memory-related.
- Extract token usage from chat completion responses when available:
  - `prompt_tokens`;
  - `completion_tokens`;
  - `total_tokens`.
- Record `finish_reason` when available.
- Classify context-related warnings and errors:
  - `context_overflow` for API errors that look like context overflow;
  - `context_near_limit` when usage is close to actual context length;
  - `output_truncated` when `finish_reason == "length"`.
- Use warning and error ratios from config.

## Check

Automated check:

```bash
pytest
```

Tests should cover:

- `nvidia-smi` unavailable does not fail;
- sample CSV-style `nvidia-smi` output is parsed;
- malformed `nvidia-smi` output does not crash diagnostics;
- OOM-looking load error is classified;
- token usage is extracted;
- context near-limit warning is set;
- output truncation is detected.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
