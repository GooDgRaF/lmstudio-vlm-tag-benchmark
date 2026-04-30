from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def _mode_prompt_path(cfg: BenchmarkConfig, mode: str) -> Path:
    by_mode = {
        "ru_free": cfg.prompt_files.ru_free,
        "ru_pool": cfg.prompt_files.ru_pool,
        "ru_pool_explained": cfg.prompt_files.ru_pool_explained,
        "en_free": cfg.prompt_files.en_free,
        "en_pool": cfg.prompt_files.en_pool,
        "en_pool_explained": cfg.prompt_files.en_pool_explained,
    }
    return cfg.resolve_path(by_mode[mode])


def _render_mode_header(cfg: BenchmarkConfig, mode: str) -> str:
    first, second, third = _stage_chunks(cfg.limits.max_tags)
    content = _mode_prompt_path(cfg, mode).read_text(encoding="utf-8")
    values = {
        "max_tags": str(cfg.limits.max_tags),
        "first_chunk": str(first),
        "second_chunk": str(second),
        "third_chunk": str(third),
    }
    return content.format_map(values).strip()


def response_format_for_mode(cfg: BenchmarkConfig, mode: str) -> str:
    if mode.endswith("_pool_explained"):
        return cfg.response_formats.explained_pool_modes.primary
    if mode.endswith("_pool"):
        return cfg.response_formats.plain_pool_modes.primary
    return cfg.response_formats.free_modes.primary


def build_prompt(cfg: BenchmarkConfig, mode: str, pools: TagPools) -> PromptBuildResult:
    language = mode_language(mode)
    header = _render_mode_header(cfg, mode)
    if mode.endswith("_pool_explained"):
        pool_text = pools.explained_prompt_text(language)
        prompt = f"{header}\n\n{pool_text}"
    elif mode.endswith("_pool"):
        pool = pools.ru_plain if language == "ru" else pools.en_plain
        pool_text = "\n".join(pool)
        prompt = f"{header}\n\n{pool_text}"
    else:
        prompt = header
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
