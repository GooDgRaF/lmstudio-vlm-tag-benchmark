from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from src.config import BenchmarkConfig
from src.prompts import PROMPT_VERSION
from src.tag_pools import TagPools

KNOWN_MODES = {
    "ru_free",
    "ru_pool",
    "ru_pool_explained",
    "en_free",
    "en_pool",
    "en_pool_explained",
}


class ValidationError(RuntimeError):
    """Validation error."""


def validate_config(cfg: BenchmarkConfig) -> None:
    required_sections = [
        "lmstudio",
        "models",
        "input",
        "output",
        "modes",
        "pools",
        "generation",
        "load",
        "limits",
        "response_formats",
        "validation",
        "diagnostics",
        "runtime",
        "report",
        "evaluation",
    ]
    for section in required_sections:
        if section not in cfg.raw:
            raise ValidationError(f"Missing required section: {section}")

    if not cfg.models:
        raise ValidationError("Config must include at least one model")

    seen_labels: set[str] = set()
    for model in cfg.models:
        required_model_fields = {
            "id": model.id,
            "base_model_id": model.base_model_id,
            "label": model.label,
            "params": model.params,
            "quant": model.quant,
            "quant_bits": model.quant_bits,
            "max_context_length": model.max_context_length,
        }
        for field, value in required_model_fields.items():
            if value in (None, ""):
                raise ValidationError(f"Model '{model.label or model.id}' missing field '{field}'")

        if model.label in seen_labels:
            raise ValidationError(f"Duplicate model label: {model.label}")
        seen_labels.add(model.label)

        if cfg.load.context_length and model.max_context_length:
            if cfg.load.context_length > model.max_context_length:
                raise ValidationError(
                    f"load.context_length ({cfg.load.context_length}) exceeds "
                    f"max_context_length ({model.max_context_length}) for model {model.label}"
                )

    for mode in cfg.modes:
        if mode not in KNOWN_MODES:
            raise ValidationError(f"Unknown mode: {mode}")

    if cfg.runtime.result_mode not in {"deterministic", "overwrite", "accumulate"}:
        raise ValidationError(
            f"Unsupported runtime.result_mode: {cfg.runtime.result_mode}. "
            "Expected deterministic, overwrite, or accumulate."
        )

    pool_paths = [
        cfg.pools.ru_plain,
        cfg.pools.en_plain,
        cfg.pools.ru_explained,
        cfg.pools.en_explained,
    ]
    for pool_path in pool_paths:
        resolved = cfg.resolve_path(pool_path)
        if not resolved.exists():
            raise ValidationError(f"Pool file does not exist: {pool_path}")

    image_dir = cfg.resolve_path(cfg.input.image_dir)
    if not image_dir.exists():
        raise ValidationError(f"Input image directory does not exist: {cfg.input.image_dir}")


@dataclass(frozen=True)
class ParsedValues:
    tags: list[str]
    ids: list[str]
    parse_ok: bool
    schema_ok: bool
    json_extracted: bool
    line_fallback_used: bool
    error_type: str | None
    error: str | None
    response_format_used: str


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_line_values(raw_output: str) -> list[str]:
    return [line.strip() for line in raw_output.splitlines() if line.strip()]


def _parse_line_ids(raw_output: str) -> list[str]:
    ids = re.findall(r"\b(?:RU|EN)\d+\b", raw_output)
    if ids:
        return ids
    return _parse_line_values(raw_output)


def _parse_response_values(
    raw_output: str,
    expected_format: str,
    allow_json_extraction: bool,
    allow_line_fallback: bool,
    mode: str,
) -> ParsedValues:
    if expected_format == "line_ids":
        ids = _unique_preserving_order(_parse_line_ids(raw_output))
        return ParsedValues(
            tags=[],
            ids=ids,
            parse_ok=True,
            schema_ok=True,
            json_extracted=False,
            line_fallback_used=False,
            error_type=None,
            error=None,
            response_format_used="line_ids",
        )

    if expected_format == "strict_json":
        parse_source = raw_output
        json_extracted = False
        parsed: dict[str, Any] | None = None
        try:
            loaded = json.loads(parse_source)
            if isinstance(loaded, dict):
                parsed = loaded
        except json.JSONDecodeError:
            if allow_json_extraction:
                extracted = _extract_first_json_object(raw_output)
                if extracted:
                    try:
                        loaded = json.loads(extracted)
                        if isinstance(loaded, dict):
                            parsed = loaded
                            json_extracted = True
                    except json.JSONDecodeError:
                        parsed = None

        if parsed is not None and isinstance(parsed.get("tags"), list):
            tags = [str(item).strip() for item in parsed["tags"] if str(item).strip()]
            tags = _unique_preserving_order(tags)
            return ParsedValues(
                tags=tags,
                ids=[],
                parse_ok=True,
                schema_ok=True,
                json_extracted=json_extracted,
                line_fallback_used=False,
                error_type=None,
                error=None,
                response_format_used="strict_json",
            )

        if allow_line_fallback:
            tags = _unique_preserving_order(_parse_line_values(raw_output))
            return ParsedValues(
                tags=tags,
                ids=[],
                parse_ok=True,
                schema_ok=False,
                json_extracted=json_extracted,
                line_fallback_used=True,
                error_type=None,
                error=None,
                response_format_used="line_tags",
            )

        return ParsedValues(
            tags=[],
            ids=[],
            parse_ok=False,
            schema_ok=False,
            json_extracted=json_extracted,
            line_fallback_used=False,
            error_type="parse_error",
            error="Invalid strict JSON response",
            response_format_used="strict_json",
        )

    if expected_format == "line_tags":
        tags = _unique_preserving_order(_parse_line_values(raw_output))
        return ParsedValues(
            tags=tags,
            ids=[],
            parse_ok=True,
            schema_ok=True,
            json_extracted=False,
            line_fallback_used=False,
            error_type=None,
            error=None,
            response_format_used="line_tags",
        )

    return ParsedValues(
        tags=[],
        ids=[],
        parse_ok=False,
        schema_ok=False,
        json_extracted=False,
        line_fallback_used=False,
        error_type="parse_error",
        error=f"Unknown response format: {expected_format}",
        response_format_used=expected_format,
    )


def normalize_model_output(
    *,
    raw_output: str,
    mode: str,
    requested_response_format: str,
    pools: TagPools,
    max_tags: int,
    allow_json_extraction: bool,
    allow_line_fallback: bool,
    drop_tags_not_in_pool: bool,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    parsed = _parse_response_values(
        raw_output=raw_output,
        expected_format=requested_response_format,
        allow_json_extraction=allow_json_extraction,
        allow_line_fallback=allow_line_fallback,
        mode=mode,
    )

    raw_tags = parsed.tags.copy()
    raw_ids = parsed.ids.copy()
    accepted_tags: list[str] = []
    accepted_ids: list[str] = []
    rejected_tags: list[str] = []
    rejected_ids: list[str] = []
    pool_ok = True

    language = "ru" if mode.startswith("ru_") else "en"
    is_explained = mode.endswith("_pool_explained")
    is_pool_mode = mode.endswith("_pool") or is_explained

    if parsed.parse_ok:
        if is_explained:
            id_to_tag = pools.ru_explained_id_to_tag if language == "ru" else pools.en_explained_id_to_tag
            tag_set = pools.ru_explained_tag_set if language == "ru" else pools.en_explained_tag_set
            id_pattern = r"^RU\d+$" if language == "ru" else r"^EN\d+$"

            for value in raw_ids[:max_tags]:
                if re.match(id_pattern, value) and value in id_to_tag:
                    accepted_ids.append(value)
                    accepted_tags.append(id_to_tag[value])
                else:
                    rejected_ids.append(value)

            # If model returned tags in explained mode via line fallback, keep them visibly rejected.
            for value in raw_tags:
                if value in tag_set:
                    rejected_tags.append(value)
                elif value:
                    rejected_tags.append(value)
            pool_ok = len(rejected_ids) == 0 and len(rejected_tags) == 0
        elif mode.endswith("_pool"):
            allowed = pools.ru_plain_set if language == "ru" else pools.en_plain_set
            for tag in raw_tags[:max_tags]:
                if tag in allowed:
                    accepted_tags.append(tag)
                else:
                    rejected_tags.append(tag)
            pool_ok = len(rejected_tags) == 0
        else:
            accepted_tags = raw_tags[:max_tags]
            pool_ok = True
    else:
        pool_ok = False if is_pool_mode else True

    if not drop_tags_not_in_pool and mode.endswith("_pool"):
        accepted_tags.extend(rejected_tags)
        rejected_tags = []
        pool_ok = True

    if len(accepted_tags) > max_tags:
        accepted_tags = accepted_tags[:max_tags]
    if len(accepted_ids) > max_tags:
        accepted_ids = accepted_ids[:max_tags]

    error_type = parsed.error_type
    error = parsed.error
    if is_pool_mode and parsed.parse_ok and not pool_ok and error_type is None:
        error_type = "pool_validation_failed"
        error = "Response contains values outside configured pool"

    normalized = {
        "prompt_version": prompt_version,
        "raw_output": raw_output,
        "response_format_requested": requested_response_format,
        "response_format_used": parsed.response_format_used,
        "raw_tags": raw_tags,
        "raw_ids": raw_ids,
        "accepted_tags": accepted_tags,
        "accepted_ids": accepted_ids,
        "rejected_tags": rejected_tags,
        "rejected_ids": rejected_ids,
        "parse_ok": parsed.parse_ok,
        "schema_ok": parsed.schema_ok,
        "json_extracted": parsed.json_extracted,
        "line_fallback_used": parsed.line_fallback_used,
        "pool_ok": pool_ok,
        "pool_violations": len(rejected_tags) + len(rejected_ids),
        "error_type": error_type,
        "error": error,
    }
    return normalized
