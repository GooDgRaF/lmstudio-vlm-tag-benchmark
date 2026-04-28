# SPEC-17 — Line-based prompt modernization

## Goal

Modernize active tagging prompts and switch the default active response style for tag modes from JSON-first to line-based output.

The benchmark should ask models for concise tags directly:

- one tag per line for free and plain-pool modes;
- one ID per line for explained-pool modes;
- explicit language in every prompt;
- clearer prioritization of obvious tags before optional detail tags.

Keep JSON parsing support in code. This spec changes the default active prompts/configs, not the parser's ability to handle JSON.

Implement this spec before SPEC-18 so the new `PROMPT_VERSION` and request ids become the baseline for resumable artifacts.

## Files

Related files:

- [README](../README.md)
- [Project guide](../PROJECT_GUIDE.md)
- [Architecture](../ARCHITECTURE.md)
- [pools README](../pools/README.md)

Expected files:

- `src/prompts.py`
- `src/validator.py`
- `src/config.py`
- `config.smoke.yaml`
- `config.example.yaml`
- `tests/test_prompts.py`
- `tests/test_response_parsing.py`
- `tests/test_config.py`
- `README.md`
- `PROJECT_GUIDE.md`

## Scope

Implement in this spec:

- bump `PROMPT_VERSION` from `v1` to `v2`;
- make free and plain-pool modes request `line_tags` by default;
- keep explained-pool modes requesting `line_ids`;
- keep strict JSON parsing support available in code;
- write explicit Russian/English prompts;
- encode the 3+3+4 prioritization strategy in prompts;
- keep pool-mode prompts strict about using only pool entries;
- update docs and tests.

Do not implement in this spec:

- request artifact storage;
- collect/rebuild behavior;
- report layout changes;
- new tagging modes;
- pool semantic changes;
- removal of JSON parser or JSON response_format code.

## Config Changes

Update both active configs:

```yaml
response_formats:
  free_modes:
    primary: "line_tags"
    fallback: "strict_json"
  plain_pool_modes:
    primary: "line_tags"
    fallback: "strict_json"
  explained_pool_modes:
    primary: "line_ids"
    fallback: null
```

`validation.use_response_format` may stay `true`, but `line_tags` and `line_ids` should not produce a JSON schema payload.

Keep `strict_json` support for future configs and backwards-compatible parsing of existing artifacts.

## Prompt Contract

### Russian free tag prompt

Use this structure, adapted to `limits.max_tags`:

```text
Дай теги к изображению на русском языке.

Формат ответа: один тег на строку.
Минимум 3 тега, если на изображении есть хотя бы 3 очевидных видимых признака.
Максимум 10 тегов.

Сначала дай 3 самых очевидных тега.
Если этих 3 тегов достаточно, чтобы передать главное содержание изображения, остановись.
Если важные видимые объекты ещё не отмечены, добавь ещё до 3 тегов.
Если после этого всё ещё есть важные видимые объекты, добавь ещё до 4 тегов.
Не добавляй теги просто для количества.

Правила:
- только теги, без описания изображения;
- каждый тег короткий: 1–3 слова;
- без Markdown;
- без нумерации;
- без пояснений;
- не угадывай неочевидное — если сомневаешься, пропусти тег.
```

If `limits.max_tags` is not `10`, adjust the maximum line and the staged counts so they do not exceed the configured max. Minimum acceptable behavior: keep the 3+3+remaining shape for max values above 6, and keep a simple first-3-then-remaining shape for smaller max values.

### English free tag prompt

Provide an equivalent English prompt:

```text
Give image tags in English.

Answer format: one tag per line.
At least 3 tags if the image has at least 3 obvious visible features.
At most 10 tags.

First give the 3 most obvious tags.
If those 3 tags are enough to capture the main content of the image, stop.
If important visible objects are still missing, add up to 3 more tags.
If important visible objects are still missing after that, add up to 4 more tags.
Do not add tags just to reach a number.

Rules:
- tags only, no image description;
- each tag is short: 1–3 words;
- no Markdown;
- no numbering;
- no explanations;
- do not guess non-obvious details; if unsure, skip the tag.
```

### Plain-pool prompts

For `ru_pool` and `en_pool`, use the same line-tag contract plus pool restriction:

- Russian: `Выбирай теги только из списка ниже. Не изменяй написание тегов.`
- English: `Choose tags only from the list below. Do not change tag spelling.`

Then append the plain pool text.

The model should still answer with one tag per line, not JSON.

### Explained-pool prompts

For `ru_pool_explained` and `en_pool_explained`, keep line IDs:

- Russian: `Выбери только подходящие ID из списка ниже. Формат ответа: один ID на строку.`
- English: `Choose only matching IDs from the list below. Answer format: one ID per line.`

Use the same prioritization idea, but refer to IDs instead of tags where needed. Do not ask the model to copy tag names in explained-pool modes.

## Parser Behavior

The code must continue to parse:

- `line_tags`;
- `line_ids`;
- `strict_json`.

For active configs, `line_tags` is the primary path for free/plain-pool modes.

Important behavior:

- one non-empty line becomes one raw tag;
- trim whitespace around each line;
- ignore empty lines;
- reject Markdown bullets or numbering only if current parser already does so, otherwise add focused normalization only if tests show it is needed;
- still cap accepted output by `limits.max_tags`;
- pool validation remains unchanged.

Do not remove `strict_json_response_format`; it remains useful for future configs.

## Request Identity

Bump:

```python
PROMPT_VERSION = "v2"
```

This must change request ids because `build_request_id` includes prompt version.

After SPEC-18, manifests and request artifacts should use prompt v2 as the stable baseline.

## Documentation

Update docs where they describe active response format:

- README mode descriptions if needed;
- PROJECT_GUIDE prompt/response-format sections;
- ARCHITECTURE only if it states active defaults instead of supported formats.

Make clear that JSON is still supported by the parser, but current configs use line-based prompts.

## Tests

Add or update tests for:

- `PROMPT_VERSION == "v2"`;
- Russian free prompt says `на русском языке`;
- English free prompt says `in English`;
- free prompt says one tag per line;
- free prompt includes the conditional minimum-3 rule;
- free prompt includes the 3+3+4 prioritization for default `max_tags: 10`;
- plain-pool prompt says to choose only from the pool and preserve spelling;
- explained-pool prompt asks for IDs only, one per line;
- config loads with `line_tags` as primary for free/plain-pool modes;
- line-based responses still normalize correctly;
- strict JSON responses still normalize correctly;
- request id changes when prompt version changes.

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

Inspect:

```text
results/<run_id>/raw/
results/<run_id>/normalized/
results/<run_id>/summary.csv
results/<run_id>/report.html
```

Manual review expectations:

- model answers are mostly one tag per line;
- no JSON is required for active free/plain-pool prompts;
- pool modes still reject out-of-pool values;
- reports still show accepted and rejected chips correctly.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
