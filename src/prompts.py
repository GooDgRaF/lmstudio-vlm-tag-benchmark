from __future__ import annotations

from dataclasses import dataclass

from src.config import BenchmarkConfig
from src.tag_pools import TagPools

PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class PromptBuildResult:
    mode: str
    language: str
    prompt: str
    prompt_version: str
    response_format_requested: str


def mode_language(mode: str) -> str:
    return "ru" if mode.startswith("ru_") else "en"


def _base_rules(language: str, max_tags: int) -> str:
    if language == "ru":
        return (
            f"Верни до {max_tags} тегов.\n"
            "Не описывай изображение.\n"
            "Не используй Markdown.\n"
            "Не добавляй пояснения.\n"
            "Если сомневаешься, лучше пропусти тег."
        )
    return (
        f"Return up to {max_tags} tags.\n"
        "Do not describe the image.\n"
        "Do not use Markdown.\n"
        "Do not include explanations.\n"
        "Prefer no tag over a doubtful tag."
    )


def response_format_for_mode(cfg: BenchmarkConfig, mode: str) -> str:
    if mode.endswith("_pool_explained"):
        return cfg.response_formats.explained_pool_modes.primary
    if mode.endswith("_pool"):
        return cfg.response_formats.plain_pool_modes.primary
    return cfg.response_formats.free_modes.primary


def build_prompt(cfg: BenchmarkConfig, mode: str, pools: TagPools) -> PromptBuildResult:
    language = mode_language(mode)
    rules = _base_rules(language, cfg.limits.max_tags)
    if mode.endswith("_pool_explained"):
        pool_text = pools.explained_prompt_text(language)
        if language == "ru":
            prompt = (
                f"{rules}\n"
                "Выбери только подходящие ID из списка ниже.\n"
                "Формат ответа: один ID на строку.\n\n"
                f"{pool_text}"
            )
        else:
            prompt = (
                f"{rules}\n"
                "Choose only matching IDs from the list below.\n"
                "Answer format: one ID per line.\n\n"
                f"{pool_text}"
            )
    elif mode.endswith("_pool"):
        pool = pools.ru_plain if language == "ru" else pools.en_plain
        pool_text = "\n".join(pool)
        if language == "ru":
            prompt = (
                f"{rules}\n"
                "Выбирай теги только из списка ниже.\n"
                "Ответ: JSON {'tags': [...]} или fallback один тег на строку.\n\n"
                f"{pool_text}"
            )
        else:
            prompt = (
                f"{rules}\n"
                "Pick tags only from the list below.\n"
                "Answer: JSON {'tags': [...]} or fallback one tag per line.\n\n"
                f"{pool_text}"
            )
    else:
        if language == "ru":
            prompt = (
                f"{rules}\n"
                "Ответ: JSON {'tags': [...]} или fallback один тег на строку."
            )
        else:
            prompt = (
                f"{rules}\n"
                "Answer: JSON {'tags': [...]} or fallback one tag per line."
            )
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

