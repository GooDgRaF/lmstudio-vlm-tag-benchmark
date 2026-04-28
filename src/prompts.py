from __future__ import annotations

from dataclasses import dataclass

from src.config import BenchmarkConfig
from src.tag_pools import TagPools

PROMPT_VERSION = "v2"


@dataclass(frozen=True)
class PromptBuildResult:
    mode: str
    language: str
    prompt: str
    prompt_version: str
    response_format_requested: str


def mode_language(mode: str) -> str:
    return "ru" if mode.startswith("ru_") else "en"


def _stage_chunks(max_tags: int) -> tuple[int, int, int]:
    first = min(3, max_tags)
    if max_tags <= first:
        return first, 0, 0
    second = min(3, max_tags - first)
    third = max(max_tags - first - second, 0)
    return first, second, third


def _base_rules(language: str, max_tags: int, *, ids_only: bool = False) -> str:
    first, second, third = _stage_chunks(max_tags)
    value_label = "ID" if ids_only else "тег"
    value_label_pl = "ID" if ids_only else "тегов"
    value_label_en = "ID" if ids_only else "tag"
    value_label_en_pl = "IDs" if ids_only else "tags"

    if language == "ru":
        lines = [
            f"Дай {value_label_pl} к изображению на русском языке.",
            "",
            f"Формат ответа: один {value_label} на строку.",
            "Минимум 3 тега, если на изображении есть хотя бы 3 очевидных видимых признака."
            if not ids_only
            else "Минимум 3 ID, если на изображении есть хотя бы 3 очевидных видимых признака.",
            f"Максимум {max_tags} {value_label_pl}.",
            "",
            f"Сначала дай {first} самых очевидных {value_label_pl}.",
            (
                f"Если этих {first} {value_label_pl} достаточно, чтобы передать главное содержание изображения, остановись."
                if first > 0
                else "Если достаточно, чтобы передать главное содержание изображения, остановись."
            ),
        ]
        if second > 0:
            lines.append(
                f"Если важные видимые объекты ещё не отмечены, добавь ещё до {second} {value_label_pl}."
            )
        if third > 0:
            lines.append(
                f"Если после этого всё ещё есть важные видимые объекты, добавь ещё до {third} {value_label_pl}."
            )
        lines.extend(
            [
                f"Не добавляй {value_label_pl} просто для количества.",
                "",
                "Правила:",
                "- только теги, без описания изображения;" if not ids_only else "- только ID, без описания изображения;",
                "- каждый тег короткий: 1-3 слова;" if not ids_only else "- без квадратных скобок;",
                "- без Markdown;",
                "- без нумерации;",
                "- без пояснений;",
                "- не угадывай неочевидное: если сомневаешься, пропусти.",
            ]
        )
        return "\n".join(lines)

    lines = [
        f"Give image {value_label_en_pl} in English.",
        "",
        f"Answer format: one {value_label_en} per line.",
        (
            "At least 3 tags if the image has at least 3 obvious visible features."
            if not ids_only
            else "At least 3 IDs if the image has at least 3 obvious visible features."
        ),
        f"At most {max_tags} {value_label_en_pl}.",
        "",
        f"First give the {first} most obvious {value_label_en_pl}.",
        (
            f"If those {first} {value_label_en_pl} are enough to capture the main content of the image, stop."
            if first > 0
            else "If the response is enough to capture the main content of the image, stop."
        ),
    ]
    if second > 0:
        lines.append(
            f"If important visible objects are still missing, add up to {second} more {value_label_en_pl}."
        )
    if third > 0:
        lines.append(
            f"If important visible objects are still missing after that, add up to {third} more {value_label_en_pl}."
        )
    lines.extend(
        [
            f"Do not add {value_label_en_pl} just to reach a number.",
            "",
            "Rules:",
            "- tags only, no image description;" if not ids_only else "- IDs only, no image description;",
            "- each tag is short: 1-3 words;" if not ids_only else "- no square brackets;",
            "- no Markdown;",
            "- no numbering;",
            "- no explanations;",
            "- do not guess non-obvious details; if unsure, skip.",
        ]
    )
    return "\n".join(lines)


def _pool_rule(language: str) -> str:
    if language == "ru":
        return (
            "Выбирай теги только из списка ниже.\n"
            "Не изменяй написание тегов."
        )
    return "Choose tags only from the list below.\nDo not change tag spelling."


def _explained_rule(language: str) -> str:
    if language == "ru":
        return (
            "Выбери только подходящие ID из списка ниже.\n"
            "Формат ответа: один ID на строку."
        )
    return "Choose only matching IDs from the list below.\nAnswer format: one ID per line."


def response_format_for_mode(cfg: BenchmarkConfig, mode: str) -> str:
    if mode.endswith("_pool_explained"):
        return cfg.response_formats.explained_pool_modes.primary
    if mode.endswith("_pool"):
        return cfg.response_formats.plain_pool_modes.primary
    return cfg.response_formats.free_modes.primary


def build_prompt(cfg: BenchmarkConfig, mode: str, pools: TagPools) -> PromptBuildResult:
    language = mode_language(mode)
    if mode.endswith("_pool_explained"):
        rules = _base_rules(language, cfg.limits.max_tags, ids_only=True)
        pool_text = pools.explained_prompt_text(language)
        prompt = f"{rules}\n{_explained_rule(language)}\n\n{pool_text}"
    elif mode.endswith("_pool"):
        rules = _base_rules(language, cfg.limits.max_tags)
        pool = pools.ru_plain if language == "ru" else pools.en_plain
        pool_text = "\n".join(pool)
        prompt = f"{rules}\n{_pool_rule(language)}\n\n{pool_text}"
    else:
        prompt = _base_rules(language, cfg.limits.max_tags)
    return PromptBuildResult(
        mode=mode,
        language=language,
        prompt=prompt,
        prompt_version=PROMPT_VERSION,
        response_format_requested=response_format_for_mode(cfg, mode),
    )


def strict_json_response_format(max_tags: int) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "image_tags",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": max_tags,
                    }
                },
                "required": ["tags"],
            },
        },
    }
