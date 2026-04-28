# SPEC-09 — Sequential benchmark runner

## Goal

Implement the main sequential benchmark loop: load one model, test image support, run images and modes, save results, unload the model, then continue.

This is the first stage that connects the previously built modules into the actual benchmark.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Example config](../config.example.yaml)
- [SPEC-03](./03-lmstudio-client.md)
- [SPEC-04](./04-tag-pools.md)
- [SPEC-05](./05-image-discovery.md)
- [SPEC-06](./06-prompts-and-parsing.md)
- [SPEC-07](./07-storage.md)
- [SPEC-08](./08-diagnostics.md)

Expected files:

- `src/runner.py`
- `src/lmstudio_client.py`
- `src/storage.py`
- `tests/test_runner.py`
- `README.md`

## Tasks

- Add `run` CLI command:

```bash
python main.py run --config config.example.yaml
python main.py run --config config.example.yaml --limit 1
```

- Validate config before starting.
- Check LM Studio availability before the full run.
- Load tag pools once.
- Discover images once.
- Create a result run folder.
- Implement the smallest vertical slice first:
  - one configured model;
  - one discovered image;
  - one tagging mode;
  - one raw output;
  - one normalized output;
  - unload model.
- After the vertical slice works, generalize to all configured models, images, and modes.
- For each configured model:
  - collect GPU diagnostics before load;
  - load model with configured load options;
  - collect GPU diagnostics after load;
  - save load metadata under `models/<model_label>/load.json`;
  - run `image_request_smoke_test` if enabled;
  - save smoke-test result under `models/<model_label>/smoke_test.json`;
  - do not write smoke-test requests as normal `summary.csv` request rows;
  - skip this model if smoke test fails;
  - process images and modes sequentially;
  - save raw and normalized outputs for every request;
  - unload model after the model run if configured.
- If `response_format` is unsupported, retry the affected request without `response_format` when configured and record the fallback diagnostically.
- Continue to the next request after request-level errors.
- Continue to the next model after model-level errors when possible.
- Keep v1 sequential. Do not add async or parallel processing.

## Check

Manual check with LM Studio running and at least one image in the configured folder:

```bash
python main.py run --config config.example.yaml --limit 1
```

Automated check:

```bash
pytest
```

Tests should use mocked LM Studio calls and cover:

- model load and unload are called in order;
- the vertical slice saves one raw and one normalized result;
- all configured modes are attempted for an image after generalization;
- raw and normalized outputs are saved;
- request-level errors do not stop the whole run;
- model-level errors do not stop later models when possible;
- smoke test failure skips that model;
- smoke test results are saved separately from normal request rows;
- unsupported `response_format` can be retried without hiding the diagnostic;
- `--limit 1` limits image count.

## Agent report

Fill this after implementation:

- Done: Implemented sequential benchmark loop with model load/unload, smoke test, per-request inference flow, fallback retry without `response_format`, raw+normalized persistence, per-model diagnostics metadata, and incremental `summary.csv` rows.
- Changed files: `src/runner.py`, `main.py`, `tests/test_runner.py`.
- Checks run: `python -m pytest -q --basetemp C:\Users\anton\AppData\Local\Temp\codex_pytest`; `python main.py dry-run --config config.example.yaml --limit 1`.
- Notes: Run remains strictly sequential (no async/parallel processing).
