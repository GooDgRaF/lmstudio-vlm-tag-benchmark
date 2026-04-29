# SPEC-25 — REST reasoning profiles and end-to-end validation

## Goal

Stabilize the REST Chat migration before any new full benchmark run.

SPEC-22, SPEC-23, and SPEC-24 moved the project to LM Studio REST Chat and separated final answers from reasoning content. The base path works, but a review of the implemented state found several follow-up issues:

- `config.example.yaml` still uses only `reasoning: "default"` for reasoning-capable models;
- think/no-think comparison profiles are not represented in the full config;
- REST truncation can be lost after response normalization;
- smoke-test success can be reported even when the model produced reasoning but no final answer;
- there is no live end-to-end check that proves a reasoning model produces correct artifacts and HTML through the full CLI pipeline.

After this spec, the project should be safe to hand back to benchmarking work.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [SPEC-22 REST Chat transport and response normalization](./archive/22-rest-chat-transport.md)
- [SPEC-23 Runner migration and REST request artifacts](./archive/23-rest-runner-artifacts.md)
- [SPEC-24 Collect, reports, configs, and docs for REST results](./archive/24-rest-collect-reporting.md)

Expected files:

- `config.example.yaml`
- optional: `config.rest-reasoning-smoke.yaml`
- `src/runner.py`
- `src/diagnostics.py`
- `src/lmstudio_client.py`
- `src/report.py`
- `src/collect.py`
- `README.md`
- `PROJECT_GUIDE.md`
- `ARCHITECTURE.md`
- `tests/test_runner.py`
- `tests/test_lmstudio_client.py`
- `tests/test_diagnostics.py`
- `tests/test_collect.py`
- `tests/test_report.py`
- this spec file

Do not change unrelated prompt semantics or pool semantics in this spec.

## Scope

Implement in this spec:

- add explicit think/no-think model profiles for reasoning-capable vision models;
- preserve REST `output_truncated` correctly;
- make smoke tests honest when final answer content is missing;
- add or update unit tests for these fixes;
- add a small live end-to-end validation procedure using a reasoning model, one image, and two modes;
- document the end-to-end validation result in `Agent report`.

Do not implement in this spec:

- a new report design;
- async or parallel benchmark execution;
- judge-model scoring;
- non-LM-Studio backends;
- large full benchmark runs;
- changing tag pools or prompt wording unless required to make the test route work.

## Current State To Verify First

Before editing, verify the current assumptions:

```bash
git status --short --branch
python -m pytest -q
python main.py validate-config --config config.example.yaml
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

Expected from the current state:

- tests pass;
- REST smoke works;
- `config.example.yaml` still has reasoning-capable models as single `reasoning: "default"` rows;
- `results/rest_smoke_check_20260429` or a fresh smoke can show `completion_tokens == generation.max_tokens` while `output_truncated` may be false.

Do not rely on old generated result folders as authoritative; use them only as hints.

## Task 1 — Add Think/No-Think Profiles

Update `config.example.yaml` so reasoning-capable vision models are represented as separate model profiles.

Keep known-good non-reasoning rows as single rows:

- `qwen3-vl-8b-q4_k_m`;
- `qwen3-vl-4b-q4_k_m`;
- `qwen3-vl-4b-q8_0`.

For reasoning-capable VLMs, use explicit profile labels.

Required minimum:

```yaml
- id: "qwen/qwen3.5-9b@q4_k_m"
  base_model_id: "qwen/qwen3.5-9b"
  label: "qwen3_5-9b-q4_k_m-think"
  reasoning: "on"
  ...

- id: "qwen/qwen3.5-9b@q4_k_m"
  base_model_id: "qwen/qwen3.5-9b"
  label: "qwen3_5-9b-q4_k_m-no-think"
  reasoning: "off"
  ...
```

Also apply the same pattern to any other reasoning-capable vision models already present in the current config, including Gemma rows:

```text
gemma-4-e2b-q8_0-think
gemma-4-e2b-q8_0-no-think
gemma-4-e4b-q4_k_m-think
gemma-4-e4b-q4_k_m-no-think
gemma-4-e4b-q6_k-think
gemma-4-e4b-q6_k-no-think
```

For Qwen3.5 Q6, keep or add profiles only if that model remains an intended benchmark row:

```text
qwen3_5-9b-q6_k-think
qwen3_5-9b-q6_k-no-think
```

Rules:

- labels must be unique;
- duplicate `id` values are allowed when labels differ;
- preserve existing metadata fields (`display_name`, `params`, `architecture`, `quant`, `quant_bits`, `size_bytes`, `max_context_length`);
- do not invent model ids that are not already in this project;
- do not add text-only models to image benchmark config.

Update documentation if it describes the model list or reasoning comparison shape.

## Task 2 — Add A Small Reasoning E2E Config

Add a dedicated config if useful:

```text
config.rest-reasoning-smoke.yaml
```

This config is for live validation, not everyday quick smoke.

Required properties:

- one small reasoning-capable vision model;
- two rows for the same model id:
  - one `reasoning: "on"`;
  - one `reasoning: "off"`;
- one image via `limits.limit_images: 1`;
- exactly two modes to keep runtime small.

Recommended modes:

```yaml
modes:
  - ru_free
  - en_free
```

If a pool mode is more useful for catching report issues, use one free mode and one pool mode, but keep total modes at two.

Recommended model:

- prefer `google/gemma-4-e2b@q8_0` if available and reasonably fast;
- otherwise use the smallest available reasoning-capable vision model from `python main.py list-models --config config.example.yaml`;
- do not use a large 20B+ model for this e2e check.

Keep:

```yaml
runtime:
  result_mode: "deterministic"
  image_request_smoke_test: true
```

Use a higher enough `generation.max_tokens` for reasoning-on to allow final content:

```yaml
generation:
  max_tokens: 2048
```

The exact value may be adjusted if live evidence shows the selected model needs less or more.

## Task 3 — Preserve REST Truncation Correctly

Review the interaction between:

- `normalize_rest_chat_response`;
- `extract_usage_diagnostics`;
- `runner.py` merge order into normalized artifacts.

Observed risk:

- `normalize_rest_chat_response` can infer `output_truncated: true` when `completion_tokens >= max_output_tokens`;
- `runner.py` may later overwrite this with `extract_usage_diagnostics(...)`;
- `extract_usage_diagnostics` currently may not know REST `max_output_tokens`, so the final normalized artifact and summary may incorrectly show `output_truncated: false`.

Required behavior:

- final normalized artifact must preserve REST truncation inference;
- summary CSV must preserve the same value;
- diagnostics HTML must show the same value;
- if `completion_tokens == generation.max_tokens` and no stronger stop reason exists, treat as truncated or at least as output-budget-exhausted according to a clearly named field.

Preferred minimal fix:

- ensure REST payload passed to `extract_usage_diagnostics` includes `max_output_tokens`, or
- merge `usage_diag` before `rest_meta`, so `rest_meta["output_truncated"]` wins, or
- update `extract_usage_diagnostics` to accept `max_output_tokens` explicitly.

Add tests for the chosen behavior.

## Task 4 — Make Smoke Test Honest

The model smoke test currently verifies that the API call succeeds, but it must also verify that a final answer exists.

Required behavior:

- if REST returns reasoning content but no non-empty final message, smoke must not report a normal success;
- smoke result should include:
  - `ok`;
  - `preview`;
  - `output_source`;
  - `no_final_answer`;
  - `reasoning_content_present`;
  - `reasoning_content_length`;
  - a short `error` when `no_final_answer` is true.

Suggested behavior:

```json
{
  "ok": false,
  "error": "REST smoke response did not contain a non-empty final message",
  "no_final_answer": true,
  "reasoning_content_present": true
}
```

If the existing runner semantics would skip an entire model on failed smoke, keep that behavior. It is better to skip honestly than to fill reports with reasoning-only cells.

Add unit tests:

- smoke succeeds when final message exists;
- smoke fails when only reasoning exists;
- smoke preview uses final content only.

## Task 5 — Live End-To-End Validation

This is mandatory.

Run a real end-to-end validation through LM Studio using a reasoning-capable model.

The testing agent must:

1. Choose the smallest practical reasoning-capable vision model available in LM Studio.
2. Use one image.
3. Use exactly two tagging modes.
4. Run both reasoning profiles:
   - `reasoning: "on"`;
   - `reasoning: "off"`.
5. Generate all normal artifacts:
   - `run_manifest.json`;
   - request `raw.json`;
   - request `normalized.json`;
   - request `diagnostics.json`;
   - `summary.csv`;
   - `diagnostics.json`;
   - `report.html`;
   - `diagnostics.html`.

Recommended commands:

```bash
python main.py validate-config --config config.rest-reasoning-smoke.yaml
python main.py dry-run --config config.rest-reasoning-smoke.yaml
python main.py run --config config.rest-reasoning-smoke.yaml --run-id rest-reasoning-e2e
python main.py collect --run results/rest-reasoning-e2e --write-reports
```

If `config.rest-reasoning-smoke.yaml` is not created, use a temporary documented config or CLI-safe equivalent, but keep the run small.

## E2E Content Checks

The live e2e check must inspect file contents, not only command exit codes.

Check `summary.csv`:

- exactly expected row count:
  - `2 models x 1 image x 2 modes = 4` rows;
- `transport` is `rest` for every row;
- both `reasoning_requested` values are present:
  - `on`;
  - `off`;
- `no_final_answer` is false for successful rows;
- `reasoning_content_present` is true for at least one reasoning-on row if the selected model emits reasoning;
- `reasoning_tokens` is nonzero for reasoning-on if LM Studio reports it;
- `reasoning_tokens` is zero or empty for reasoning-off;
- `accepted_tags` are populated for successful rows;
- no row contains reasoning prose in `accepted_tags`, `rejected_tags`, or rendered answer content.

Check request raw artifacts:

- every raw artifact has `transport: "rest"`;
- every raw artifact has `final_content`;
- every raw artifact has `reasoning_content`;
- reasoning-on raw artifact separates final and reasoning content;
- reasoning-off raw artifact has empty or absent reasoning content according to LM Studio output.

Check normalized artifacts:

- `raw_output == final_content`;
- `reasoning_content_used` is false;
- `final_content_empty` is false for successful rows;
- `no_final_answer` is false for successful rows;
- `output_truncated` is consistent with token budget.

Check `report.html`:

- file exists;
- contains both model profile labels;
- contains tags from final answers;
- does not contain full reasoning prose such as:
  - `Thinking Process`;
  - `Анализ объектов`;
  - long markdown reasoning bullets;
- if no-final-answer occurs, report shows a compact no-final state instead of reasoning text.

Check `diagnostics.html`:

- file exists;
- contains `transport`;
- contains `reasoning requested` / `reasoning req` column;
- contains `reasoning tokens`;
- contains `no final`;
- links raw/normalized/request diagnostics artifacts.

Record the exact run id and key observations in this spec's `Agent report`.

## Unit Tests

Add or update tests for:

- think/no-think duplicate model ids with unique labels validate;
- `config.example.yaml` validates after profile split;
- optional `config.rest-reasoning-smoke.yaml` validates;
- REST truncation survives runner merge into normalized output and summary row;
- smoke test fails on reasoning-only REST response;
- smoke test succeeds on final message REST response;
- report does not render reasoning prose in answer cells;
- collect preserves `reasoning_requested`, `reasoning_tokens`, `no_final_answer`, and `output_truncated`.

Run:

```bash
python -m pytest -q
python main.py validate-config --config config.example.yaml
python main.py validate-config --config config.smoke.yaml
```

If created:

```bash
python main.py validate-config --config config.rest-reasoning-smoke.yaml
python main.py dry-run --config config.rest-reasoning-smoke.yaml
```

## Acceptance Criteria

- Reasoning-capable models in `config.example.yaml` have explicit think/no-think profile rows.
- Normal smoke remains small and fast.
- A dedicated reasoning e2e route exists and is documented.
- REST truncation is not lost after runner normalization.
- Smoke test does not treat reasoning-only output as a normal success.
- Unit tests pass.
- Live reasoning e2e run completes with one image, two modes, and both reasoning modes.
- Generated HTML and CSV are inspected for correct content.
- Reasoning text is never rendered as answer tags.
- `Agent report` documents checks run, live run id, and any model-specific caveats.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Live e2e:
- Notes:
