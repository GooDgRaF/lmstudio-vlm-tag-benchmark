# SPEC-24 — Collect, reports, configs, and docs for REST results

## Goal

Update all result-reading and result-rendering layers so REST benchmark runs are collected, summarized, and displayed correctly.

After this spec:

- `collect` can rebuild `summary.csv` from REST request artifacts;
- old OpenAI-style artifacts remain readable;
- `report.html` renders only parsed final-answer tags;
- `diagnostics.html` shows REST/reasoning diagnostics;
- configs and docs explain the REST migration clearly;
- a dedicated reasoning smoke config exists if useful.

This spec assumes SPEC-22 and SPEC-23 are implemented.

## Files

Related files:

- [SPEC-22 REST Chat transport and response normalization](./22-rest-chat-transport.md)
- [SPEC-23 Runner migration and REST request artifacts](./23-rest-runner-artifacts.md)
- [Specs workflow](./README.md)
- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)

Expected files to change:

- `src/collect.py`
- `src/report.py`
- `src/diagnostics.py`
- `src/storage.py` only if summary fields need a final adjustment
- `README.md`
- `PROJECT_GUIDE.md`
- `ARCHITECTURE.md`
- `config.example.yaml`
- `config.smoke.yaml`
- optional: `config.rest-reasoning-smoke.yaml`
- `specs/README.md`
- `tests/test_collect.py`
- `tests/test_report.py`
- `tests/test_diagnostics.py`

Avoid changing in this spec unless fixing integration bugs from prior specs:

- `src/lmstudio_client.py`
- `src/runner.py`

## Preconditions

SPEC-22 and SPEC-23 must already be done.

Expected artifact fields from SPEC-23:

- `transport`;
- `reasoning_requested`;
- `final_content`;
- `reasoning_content`;
- `final_content_empty`;
- `final_content_length`;
- `reasoning_content_present`;
- `reasoning_content_length`;
- `reasoning_tokens`;
- `no_final_answer`;
- `normalization_error_type`;
- compatibility aliases `raw_output`, `content_empty`, `content_length`, `reasoning_content_used`.

If these fields are missing in runner artifacts, fix SPEC-23 behavior before changing collect/report.

## Collect goals

`collect` must rebuild summary rows from request artifacts and attempt artifacts without losing REST metadata.

It must support:

- new REST deterministic/overwrite artifacts;
- new REST accumulate attempt artifacts;
- old OpenAI-style artifacts without REST fields;
- failed request artifacts;
- partially written artifacts where raw exists but normalized does not, using current project behavior.

## Collect field mapping

When reading normalized artifacts, collect should prefer explicit normalized fields.

Required fields in rebuilt rows:

```text
transport
reasoning_requested
final_content_empty
final_content_length
reasoning_content_present
reasoning_content_length
reasoning_tokens
no_final_answer
normalization_error_type
tokens_per_second
time_to_first_token_seconds
```

Keep existing fields:

```text
content_empty
content_length
reasoning_content_used
output_truncated
prompt_tokens
completion_tokens
total_tokens
```

Compatibility rules:

- If `transport` is missing, use empty string or `"openai_legacy"` consistently. Prefer `"openai_legacy"` in diagnostics and empty string only if old CSV compatibility requires it.
- If `reasoning_requested` is missing, use `""`.
- If `final_content_empty` is missing, derive it from `content_empty` when present.
- If `final_content_length` is missing, derive it from `content_length` when present.
- If `reasoning_content_present` is missing, derive it from `reasoning_content_length > 0` when possible.
- If `no_final_answer` is missing, derive it as `final_content_empty and reasoning_content_present` only for display, not as a hard historical fact.
- If `reasoning_content_used` is missing for REST, treat it as `False`.

Forbidden collect behavior:

- Do not read raw `reasoning_content` and parse it as tags.
- Do not synthesize `accepted_tags` from `final_content` in collect if normalized parsed tags are already present.
- Do not silently drop REST rows because old fields are missing.

## Accumulate collect behavior

For `runtime.result_mode == "accumulate"`, collect must read attempt artifacts.

Required behavior:

- Preserve the `attempt` number in summary rows.
- Include REST metadata from each attempt normalized artifact.
- If an attempt failed, include REST metadata from attempt diagnostics/status when normalized artifact is incomplete.
- Do not collapse think/no-think attempts into one row unless current collect semantics already aggregate attempts.
- Do not use only request-level artifacts and ignore attempts.

Test with at least two attempts for the same request id:

- one `reasoning_requested: "on"`;
- one `reasoning_requested: "off"` is not normally expected for the same request id after SPEC-23, but test that collect does not overwrite rows by request id only.

## Summary CSV requirements

`summary.csv` should include the REST columns added in SPEC-23.

Column placement recommendation:

- Put `transport` and `reasoning_requested` near model fields.
- Put final/reasoning length booleans near parse/output diagnostics.
- Put `reasoning_tokens`, `tokens_per_second`, and `time_to_first_token_seconds` near token fields.

Do not include full text columns:

- no full `final_content`;
- no full `reasoning_content`;
- no raw REST response.

Those stay in JSON artifacts.

## Main report behavior

`report.html` is the human-facing comparison matrix.

Required behavior:

- Render answer/tag cells only from parsed normalized fields:
  - `accepted_tags`;
  - `accepted_ids` if the mode uses ids;
  - `rejected_tags` or pool violation info only if current report already shows them.
- Never render `reasoning_content` in the main answer matrix.
- Never render `raw_output` directly if `raw_output` might be legacy reasoning fallback text.
- If a row has `no_final_answer: true`, show a compact status marker instead of tags.
- If report already has error/status display, reuse it.
- If report does not have state display, use a short marker such as:

```text
no final answer
```

Do not redesign the report layout in this spec.

Recommended visual/state fields in matrix tooltips or small metadata areas:

- `transport`;
- `reasoning_requested`;
- `reasoning_tokens`;
- `final_content_empty`;
- `reasoning_content_present`.

But keep the main cell focused on tags.

## Diagnostics report behavior

`diagnostics.html` should make REST/reasoning problems easy to spot.

Add columns or detail fields:

```text
transport
reasoning_requested
final_content_empty
reasoning_content_present
no_final_answer
normalization_error_type
reasoning_tokens
reasoning_content_length
final_content_length
tokens_per_second
time_to_first_token_seconds
output_source
output_truncated
raw_path
normalized_path
request_diagnostics_path
```

Required behavior:

- `reasoning_content_present` should be visible as yes/no.
- `no_final_answer` should be visible as yes/no.
- Rows with `no_final_answer` should be easy to find or sort if current report supports sorting.
- Do not print full reasoning text by default.
- Keep links to raw and normalized artifacts.

Optional but useful:

- Add a small aggregate summary:
  - count by `transport`;
  - count by `reasoning_requested`;
  - count of `no_final_answer`;
  - count of `reasoning_content_present`;
  - sum/average of `reasoning_tokens` when available.

## Diagnostics JSON or internal summaries

If the project writes diagnostics JSON, include aggregate REST metrics:

```json
{
  "transport_counts": { "rest": 120 },
  "reasoning_requested_counts": { "default": 60, "on": 30, "off": 30 },
  "no_final_answer_count": 2,
  "reasoning_content_present_count": 30,
  "reasoning_tokens_total": 12345
}
```

Rules:

- Missing token fields should not break aggregation.
- Treat non-numeric token values as missing.
- Do not infer quality from reasoning token count.

## Config updates

### `config.example.yaml`

Ensure example config explains:

- REST Chat is the primary transport.
- `reasoning` is model-level and accepts only `default`, `on`, `off` in this project.
- Think/no-think comparisons should be represented as separate model rows with unique labels.
- OpenAI `response_format` is not sent to REST Chat.
- `validation.use_response_format` is retained only as a parser/legacy compatibility setting unless a future spec renames it.

Recommended comments:

```yaml
# REST Chat reasoning control for this model profile:
# - default: omit the field and let LM Studio choose;
# - on: request reasoning;
# - off: disable reasoning when supported by the model.
reasoning: "default"
```

```yaml
# REST Chat does not receive OpenAI response_format payloads.
# The project still uses response format names as local parser expectations.
use_response_format: true
```

### `config.smoke.yaml`

Keep regular smoke small and stable:

- one small vision model;
- `limit_images: 1`;
- `reasoning: "default"` or `"off"`;
- no large 20B+ models.

### Optional `config.rest-reasoning-smoke.yaml`

Create a separate config if useful:

- one reasoning-capable vision model with two rows:
  - `<label>-think`, `reasoning: "on"`;
  - `<label>-no-think`, `reasoning: "off"`;
- same image limit and modes as smoke;
- comments saying it is slower and intended specifically for REST reasoning checks.

Do not make normal smoke slower just to test reasoning.

## Documentation updates

### README

Update README to say:

- project uses LM Studio REST Chat as primary inference transport;
- OpenAI-compatible chat completions are not the normal path;
- final answer and reasoning are separated;
- only final answer is parsed as tags;
- reasoning diagnostics are stored for debugging but not displayed as tags.

Add a small example model profile:

```yaml
models:
  - id: "..."
    label: "my-vlm-no-think"
    reasoning: "off"
```

### PROJECT_GUIDE

Update run workflow:

- start LM Studio server;
- load/run through REST Chat;
- use `validate-config`, `dry-run`, `run`, `collect` as before;
- explain where to inspect REST raw/normalized artifacts.

Add troubleshooting notes:

- REST request fails because reasoning unsupported by model: set `reasoning: "default"` or `"off"`.
- Report cell says `no final answer`: inspect normalized artifact; reasoning may exist but was intentionally not parsed.
- Summary has reasoning tokens but empty tags: model spent output budget on reasoning and did not produce final message.

### ARCHITECTURE

Update architecture diagram/text:

```text
LM Studio REST Chat
  -> REST response normalizer
  -> final_content only
  -> tag parser
  -> request artifacts
  -> collect
  -> reports
```

Explicitly state:

```text
reasoning_content is diagnostic data, not model output for tag parsing.
```

### specs/README

Update active sequence:

- mark SPEC-22, SPEC-23, SPEC-24 in order;
- if SPEC-22 and SPEC-23 are already done, move them to archive according to project convention;
- list the active split specs in order and do not leave obsolete monolithic REST migration specs active.

## Backward compatibility

Old runs should still be readable.

Required behavior:

- Old `summary.csv` without REST columns should still render.
- Old normalized JSON without `transport` should not crash collect/report.
- Old diagnostics JSON without REST fields should not crash diagnostics report.
- Old `content_empty` should map to `final_content_empty` for display when needed.
- Old `reasoning_content_used: true` should be displayed as legacy behavior, not repeated for REST.

Suggested display label for old rows:

```text
openai_legacy
```

Do not rewrite old artifacts.

## Tests

Add or update collect tests:

- Collect reads REST deterministic normalized artifact and writes REST columns.
- Collect reads REST accumulate attempt artifacts and preserves attempt numbers.
- Collect tolerates old artifact without `transport`.
- Collect tolerates old artifact without `final_content_empty`.
- Collect derives `reasoning_content_present` from length when explicit boolean is missing.
- Collect does not parse `reasoning_content` as tags.
- Collect does not put full reasoning text into summary CSV.
- Collect includes failed REST request rows with `error_type` and REST metadata.

Add or update report tests:

- Main report renders accepted tags from normalized parsed fields.
- Main report does not render reasoning text when `reasoning_content` contains prose.
- Main report does not render `Thinking Process` as a tag/chip.
- Main report shows compact no-final-answer state when `no_final_answer` is true.
- Diagnostics report includes `transport`.
- Diagnostics report includes `reasoning_requested`.
- Diagnostics report includes `reasoning_tokens`.
- Diagnostics report includes `reasoning_content_present`.
- Diagnostics report includes `no_final_answer`.
- Diagnostics report links raw/normalized artifacts.

Add or update documentation/config tests if the project has them:

- `config.example.yaml` validates.
- `config.smoke.yaml` validates.
- optional `config.rest-reasoning-smoke.yaml` validates.

## Manual check

Run tests:

```bash
python -m pytest -q tests/test_collect.py tests/test_report.py tests/test_diagnostics.py
python -m pytest -q
```

Validate configs:

```bash
python main.py validate-config --config config.example.yaml
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
```

If optional reasoning smoke config exists:

```bash
python main.py validate-config --config config.rest-reasoning-smoke.yaml
python main.py dry-run --config config.rest-reasoning-smoke.yaml
```

Run a real smoke and collect:

```bash
python main.py run --config config.smoke.yaml --run-id rest-report-smoke
python main.py collect --run results/rest-report-smoke --write-reports
```

Inspect:

```text
results/rest-report-smoke/summary.csv
results/rest-report-smoke/report.html
results/rest-report-smoke/diagnostics.html
```

Manual acceptance observations:

- `summary.csv` has REST columns.
- `report.html` answer cells show only tags from final answers.
- `report.html` does not show reasoning prose as chips.
- `diagnostics.html` shows transport and reasoning fields.
- If reasoning exists with empty final answer, diagnostics show that clearly.
- Old sample run artifacts, if available, still render.

## Acceptance criteria

- Collect rebuilds summary from new REST artifacts.
- Collect remains backward-compatible with old artifacts.
- Main report never renders reasoning content as answer tags.
- Diagnostics report exposes REST/reasoning status without dumping full reasoning text.
- Example and smoke configs validate.
- Documentation describes REST as the primary transport and explains reasoning separation.
- Specs workflow lists the split specs and no longer points only to the obsolete monolithic spec.

## Out of scope

Do not implement in this spec:

- report redesign;
- interactive filters;
- quality scoring;
- judge model;
- database storage;
- image thumbnail redesign;
- async or parallel runner;
- support for remote non-LM-Studio providers.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
