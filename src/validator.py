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
        "prompt_files",
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
    allowed_reasoning = {"default", "on", "off"}
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

        if model.reasoning not in allowed_reasoning:
            raise ValidationError(
                f"Unsupported model reasoning value '{model.reasoning}' for model {model.label}. "
                "Expected default, on, or off."
            )

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

    prompt_paths = [
        cfg.prompt_files.ru_free,
        cfg.prompt_files.ru_pool,
        cfg.prompt_files.ru_pool_explained,
        cfg.prompt_files.en_free,
        cfg.prompt_files.en_pool,
        cfg.prompt_files.en_pool_explained,
    ]
    for prompt_path in prompt_paths:
        resolved = cfg.resolve_path(prompt_path)
        if not resolved.exists():
            raise ValidationError(f"Prompt file does not exist: {prompt_path}")

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
    return _filter_line_tag_candidates(raw_output)[0]


def _strip_line_markup(line: str) -> str:
    value = line.strip()
    value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s*)", "", value).strip()
    value = value.replace("**", "").replace("__", "").replace("`", "").strip()
    value = value.strip(" \t\r\n.,;")
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    return value.strip(" \t\r\n.,;")


def _looks_like_reasoning_line(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    lower = text.lower()
    if lower.strip(" :：") in {"tags", "tag", "теги", "тег"}:
        return True
    reasoning_markers = [
        "thinking process",
        "analysis of the image",
        "image analysis",
        "general analysis",
        "analyze the image",
        "obvious visible features",
        "obvious features",
        "the user wants",
        "i must",
        "i need",
        "identify obvious objects",
        "determine the main content",
        "select initial",
        "selecting the top",
        "review against rules",
        "these three capture",
        "format",
        "minimum",
        "maximum",
        "use only",
        "short tags",
        "one tag per line",
        "at least",
        "at most",
        "no markdown",
        "no explanations",
        "процесс анализа",
        "анализ изображения",
        "пользователь предоставил",
        "мне нужно",
        "я должен",
        "идентификация",
        "определение признаков",
        "выбор тегов",
        "выбор тегов из списка",
        "поиск тегов",
        "проверка правил",
        "проверка списка",
        "проверка на достаточность",
        "самые очевидные теги",
        "дополнительные теги",
        "первые 3",
        "итоговый набор",
        "формат ответа",
        "минимум",
        "максимум",
        "сначала",
        "не добавлять",
        "использовать только",
        "теги короткие",
        "один тег",
        "без markdown",
        " - есть",
    ]
    if any(marker in lower for marker in reasoning_markers):
        return True
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if len(text) > 80 or len(words) > 5:
        return True
    if text.endswith(":") and len(words) > 1:
        return True
    if "," in text and len(words) > 2:
        return True
    if "/" in text and len(words) > 3:
        return True
    if (":" in text or "." in text) and len(words) > 3:
        return True
    return False


def _detect_inline_reasoning(raw_output: str) -> bool:
    lower = raw_output.lower()
    strong_markers = [
        "the user wants",
        "analyze the image",
        "analyse the image",
        "identify obvious features",
        "review and finalize",
        "review against rules",
        "final selection",
        "final list construction",
        "tags selected",
        "self-correction",
        "let's refine",
        "let's use",
    ]
    if any(marker in lower for marker in strong_markers):
        return True
    reasoning_lines = 0
    for raw_line in raw_output.splitlines():
        value = _strip_line_markup(raw_line)
        if value.lower().strip(" :：") in {"tags", "tag", "теги", "тег"}:
            continue
        if _looks_like_reasoning_line(value):
            reasoning_lines += 1
    return reasoning_lines >= 2


def _line_value_candidates(raw_line: str) -> list[str]:
    value = _strip_line_markup(raw_line)
    if not value:
        return []
    if ":" in value:
        _prefix, tail = value.split(":", 1)
        comma_parts = [part.strip(" \t\r\n.,;") for part in tail.split(",")]
        comma_parts = [part for part in comma_parts if part]
        if len(comma_parts) >= 2:
            return comma_parts
    return [value]


def _extract_bottom_valid_tags(raw_output: str, allowed: set[str]) -> list[str]:
    group: list[str] = []
    seen: set[str] = set()
    started = False
    for raw_line in reversed(raw_output.splitlines()):
        if not raw_line.strip():
            if started:
                break
            continue
        values = _line_value_candidates(raw_line)
        valid = [value for value in values if value in allowed]
        if valid:
            started = True
            for value in reversed(valid):
                if value not in seen:
                    seen.add(value)
                    group.append(value)
            continue
        if started:
            break
    return list(reversed(group))


def _extract_bottom_valid_ids(raw_output: str, valid_ids: set[str]) -> list[str]:
    group: list[str] = []
    seen: set[str] = set()
    started = False
    for raw_line in reversed(raw_output.splitlines()):
        if not raw_line.strip():
            if started:
                break
            continue
        ids = [item for item in re.findall(r"\b(?:RU|EN)\d+\b", raw_line) if item in valid_ids]
        if ids:
            started = True
            for value in reversed(ids):
                if value not in seen:
                    seen.add(value)
                    group.append(value)
            continue
        if started:
            break
    return list(reversed(group))


def _split_inline_tag_list(value: str) -> list[str]:
    if ":" not in value:
        return []
    prefix, tail = value.split(":", 1)
    if not re.search(r"\b(tags?|теги)\b", prefix, flags=re.IGNORECASE):
        return []
    parts = [part.strip(" \t\r\n.,;") for part in tail.split(",")]
    return [part for part in parts if part and not _looks_like_reasoning_line(part)]


def _filter_line_tag_candidates(raw_output: str) -> tuple[list[str], list[str]]:
    tags: list[str] = []
    ignored: list[str] = []
    for raw_line in raw_output.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        inline_tags = _split_inline_tag_list(_strip_line_markup(raw_line))
        if inline_tags:
            tags.extend(inline_tags)
            continue
        value = _strip_line_markup(raw_line)
        if not value:
            continue
        if _looks_like_reasoning_line(value):
            ignored.append(raw_line)
            continue
        tags.append(value)
    return _unique_preserving_order(tags), ignored


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
            tags, ignored = _filter_line_tag_candidates(raw_output)
            if not tags and ignored:
                return ParsedValues(
                    tags=[],
                    ids=[],
                    parse_ok=False,
                    schema_ok=False,
                    json_extracted=json_extracted,
                    line_fallback_used=True,
                    error_type="parse_error",
                    error="Response contained reasoning prose but no line tags",
                    response_format_used="line_tags",
                )
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
        tags, ignored = _filter_line_tag_candidates(raw_output)
        if not tags and ignored:
            return ParsedValues(
                tags=[],
                ids=[],
                parse_ok=False,
                schema_ok=False,
                json_extracted=False,
                line_fallback_used=False,
                error_type="parse_error",
                error="Response contained reasoning prose but no line tags",
                response_format_used="line_tags",
            )
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
    reasoning_leak_detected = _detect_inline_reasoning(raw_output)
    reasoning_leak_recovered = False
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
            if reasoning_leak_detected:
                bottom_ids = _extract_bottom_valid_ids(raw_output, set(id_to_tag.keys()))
                if bottom_ids:
                    raw_ids = bottom_ids
                    raw_tags = []
                    reasoning_leak_recovered = True

            for value in raw_ids:
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
            if reasoning_leak_detected:
                bottom_tags = _extract_bottom_valid_tags(raw_output, allowed)
                if bottom_tags:
                    raw_tags = bottom_tags
                    reasoning_leak_recovered = True
            for tag in raw_tags:
                if tag in allowed:
                    accepted_tags.append(tag)
                else:
                    rejected_tags.append(tag)
            pool_ok = len(rejected_tags) == 0
        else:
            accepted_tags = raw_tags
            pool_ok = True
    else:
        pool_ok = False if is_pool_mode else True

    if not drop_tags_not_in_pool and mode.endswith("_pool"):
        accepted_tags.extend(rejected_tags)
        rejected_tags = []
        pool_ok = True

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
        "reasoning_leak_detected": reasoning_leak_detected,
        "reasoning_leak_recovered": reasoning_leak_recovered,
        "error_type": error_type,
        "error": error,
    }
    return normalized
