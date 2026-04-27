# SPEC-06 — Prompts and response parsing

## Goal

Implement prompts for all six tagging modes and normalize model responses into one internal result format.

This stage should be testable without LM Studio by feeding sample raw outputs into the parser.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Tag pools README](../pools/README.md)
- [SPEC-04](./04-tag-pools.md)

Expected files:

- `src/prompts.py`
- `src/validator.py`
- `tests/test_prompts.py`
- `tests/test_response_parsing.py`

## Tasks

- Implement the six modes:
  - `ru_free`;
  - `ru_pool`;
  - `ru_pool_explained`;
  - `en_free`;
  - `en_pool`;
  - `en_pool_explained`.
- Define a prompt version string, for example `prompts.version: "v1"`.
- Include `prompt_version` in prompt metadata and normalized results.
- Enforce prompt rules:
  - maximum 10 tags;
  - no image description;
  - no Markdown;
  - no explanations in the answer;
  - prefer no tag over a doubtful tag.
- For free and plain-pool modes, support `strict_json` as primary response format.
- For free and plain-pool modes, support one-tag-per-line fallback.
- For explained-pool modes, support one-ID-per-line response format.
- In explained-pool modes, accept only IDs as model output.
- If an explained-pool response returns tag text instead of IDs, record it as rejected output instead of silently mapping it.
- For strict JSON, accept `{"tags": ["tag1", "tag2"]}`.
- Implement optional extraction of the first JSON object from a messy answer when configured.
- Enforce `limits.max_tags`.
- Trim parsed tags and IDs.
- Remove exact duplicates while preserving order.
- Do not silently fix out-of-pool tags by case-insensitive, fuzzy, synonym, or translation matching.
- In pool modes, reject tags or IDs that are not in the configured pool.
- Keep raw values in diagnostics before rejection so model mistakes remain visible.
- Return the normalized fields described in the architecture: raw tags, raw IDs, accepted values, rejected values, parse flags, pool flags, and error fields.

## Check

Automated check:

```bash
pytest
```

Tests should cover:

- prompt text differs correctly by mode and language;
- `prompt_version` is present in prompt metadata and normalized results;
- plain pool prompt includes only allowed tags;
- explained pool prompt includes IDs and explanations;
- strict JSON parses;
- JSON extraction works when enabled;
- line fallback works;
- invalid JSON is reported clearly;
- exact duplicates are removed while order is preserved;
- out-of-pool tags are rejected without fuzzy repair;
- unknown explained IDs are rejected;
- explained-pool tag text is rejected when IDs are expected;
- tag count is capped at 10.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
