from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.model_registry import ModelRegistryError, load_registry, resolve_model_labels

ALLOWED_MODES = [
    "ru_free",
    "ru_pool",
    "ru_pool_explained",
    "en_free",
    "en_pool",
    "en_pool_explained",
]

FULL_CONFIG_KEYS = {
    "lmstudio",
    "input",
    "output",
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
}

SIMPLE_ALLOWED_KEYS = {
    "images_folder",
    "limit_images",
    "models",
    "modes",
    "tag_files",
    "mode_prompt_files",
    "output_folder",
    "context_length",
    "max_output_tokens",
    "temperature",
    "recursive",
}


class UserConfigError(RuntimeError):
    """User-facing config validation error."""


def detect_config_style(data: dict[str, Any]) -> str:
    has_full = any(key in data for key in FULL_CONFIG_KEYS)
    models_value = data.get("models")
    models_are_simple = (
        isinstance(models_value, list)
        and len(models_value) > 0
        and all(isinstance(item, str) for item in models_value)
    )
    has_simple_marker = "images_folder" in data or models_are_simple
    if has_full and has_simple_marker:
        raise UserConfigError(
            "Config mixes user profile and full internal config fields.\n"
            "Use either generated `config.yaml` style or full `config.example.yaml` style, not both."
        )
    if has_full:
        return "full"
    if has_simple_marker:
        return "simple"
    return "unknown"


def _check_unknown_keys(data: dict[str, Any]) -> None:
    unknown = sorted([key for key in data.keys() if key not in SIMPLE_ALLOWED_KEYS])
    if not unknown:
        return
    key = unknown[0]
    if key == "max_tokens":
        raise UserConfigError("Unknown simple config key: max_tokens\nDid you mean: max_output_tokens?")
    raise UserConfigError(f"Unknown simple config key: {key}")


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UserConfigError(f"Simple config requires non-empty string field: {key}")
    return value.strip()


def _require_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise UserConfigError(f"Simple config requires non-empty list field: {key}")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise UserConfigError(f"Simple config field '{key}' must be a list of non-empty strings")
    return [item.strip() for item in value]


def _optional_int(data: dict[str, Any], key: str, default: int | None) -> int | None:
    value = data.get(key, default)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise UserConfigError(f"Simple config field '{key}' must be integer or null")


def _optional_float(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    raise UserConfigError(f"Simple config field '{key}' must be number")


def _optional_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    raise UserConfigError(f"Simple config field '{key}' must be boolean")


def _resolve_tag_files(profile: dict[str, Any]) -> dict[str, str]:
    defaults = {
        "ru": "prompts/pools/ru_plain.txt",
        "ru_plus": "prompts/pools/ru_explained_ids.tsv",
        "en": "prompts/pools/en_plain.txt",
        "en_plus": "prompts/pools/en_explained_ids.tsv",
    }
    raw = profile.get("tag_files")
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        raise UserConfigError("Simple config field 'tag_files' must be an object")

    unknown = sorted([key for key in raw.keys() if key not in defaults])
    if unknown:
        raise UserConfigError(
            f"Unknown tag_files key: {unknown[0]}. Allowed keys: ru, ru_plus, en, en_plus"
        )

    resolved = dict(defaults)
    for key, value in raw.items():
        if not isinstance(value, str) or not value.strip():
            raise UserConfigError(f"Simple config field 'tag_files.{key}' must be a non-empty string path")
        resolved[key] = value.strip()
    return resolved


def _resolve_mode_prompt_files(profile: dict[str, Any]) -> dict[str, str]:
    defaults = {
        "ru_free": "prompts/ru_free.txt",
        "ru_pool": "prompts/ru_pool.txt",
        "ru_pool_explained": "prompts/ru_pool_explained.txt",
        "en_free": "prompts/en_free.txt",
        "en_pool": "prompts/en_pool.txt",
        "en_pool_explained": "prompts/en_pool_explained.txt",
    }
    raw = profile.get("mode_prompt_files")
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        raise UserConfigError("Simple config field 'mode_prompt_files' must be an object")
    unknown = sorted([key for key in raw.keys() if key not in defaults])
    if unknown:
        raise UserConfigError(
            "Unknown mode_prompt_files key: "
            f"{unknown[0]}. Allowed keys: ru_free, ru_pool, ru_pool_explained, en_free, en_pool, en_pool_explained"
        )
    resolved = dict(defaults)
    for key, value in raw.items():
        if not isinstance(value, str) or not value.strip():
            raise UserConfigError(f"Simple config field 'mode_prompt_files.{key}' must be a non-empty string path")
        resolved[key] = value.strip()
    return resolved


def expand_user_config(profile: dict[str, Any], *, root_dir: Path, registry_path: Path | None = None) -> dict[str, Any]:
    _check_unknown_keys(profile)

    images_folder = _require_string(profile, "images_folder")
    model_labels = _require_string_list(profile, "models")
    modes = _require_string_list(profile, "modes")
    for mode in modes:
        if mode not in ALLOWED_MODES:
            raise UserConfigError(f"Unknown mode: {mode}")

    output_folder = str(profile.get("output_folder", "results"))
    limit_images = _optional_int(profile, "limit_images", None)
    context_length = _optional_int(profile, "context_length", 8192)
    max_output_tokens = _optional_int(profile, "max_output_tokens", 4096)
    temperature = _optional_float(profile, "temperature", 0.0)
    recursive = _optional_bool(profile, "recursive", False)
    tag_files = _resolve_tag_files(profile)
    mode_prompt_files = _resolve_mode_prompt_files(profile)

    reg_path = registry_path or (root_dir / "models.registry.yaml")
    try:
        registry = load_registry(reg_path)
        models = resolve_model_labels(model_labels, registry)
    except ModelRegistryError as exc:
        raise UserConfigError(
            "This looks like a simple user config. Failed to expand it because models.registry.yaml is missing or invalid.\n"
            "Run `python main.py init-config` first.\n"
            f"Details: {exc}"
        ) from exc

    return {
        "lmstudio": {
            "host": "http://localhost:1234",
            "api_base_url": "http://localhost:1234/api/v1",
            "openai_base_url": "http://localhost:1234/v1",
            "api_key": "lm-studio",
        },
        "models": models,
        "input": {
            "image_dir": images_folder,
            "recursive": recursive,
            "extensions": [".jpg", ".jpeg", ".png", ".webp", ".bmp"],
        },
        "output": {"results_dir": output_folder},
        "modes": modes,
        "pools": {
            "ru_plain": tag_files["ru"],
            "en_plain": tag_files["en"],
            "ru_explained": tag_files["ru_plus"],
            "en_explained": tag_files["en_plus"],
        },
        "prompt_files": {
            "ru_free": mode_prompt_files["ru_free"],
            "ru_pool": mode_prompt_files["ru_pool"],
            "ru_pool_explained": mode_prompt_files["ru_pool_explained"],
            "en_free": mode_prompt_files["en_free"],
            "en_pool": mode_prompt_files["en_pool"],
            "en_pool_explained": mode_prompt_files["en_pool_explained"],
        },
        "generation": {
            "temperature": temperature,
            "top_p": 1.0,
            "max_tokens": max_output_tokens,
        },
        "load": {
            "context_length": context_length,
            "flash_attention": True,
            "offload_kv_cache_to_gpu": True,
            "echo_load_config": True,
        },
        "limits": {
            "timeout_sec": 180,
            "retries": 1,
            "limit_images": limit_images,
        },
        "response_formats": {
            "free_modes": {"primary": "line_tags", "fallback": "strict_json"},
            "plain_pool_modes": {"primary": "line_tags", "fallback": "strict_json"},
            "explained_pool_modes": {"primary": "line_ids", "fallback": None},
        },
        "validation": {
            "use_response_format": True,
            "allow_json_extraction": True,
            "allow_line_fallback": True,
            "drop_tags_not_in_pool": True,
            "save_invalid_results": True,
        },
        "diagnostics": {
            "gpu_memory": {"enabled": True, "command": "nvidia-smi", "fail_if_unavailable": False},
            "context": {
                "record_usage_tokens": True,
                "warning_ratio": 0.85,
                "error_ratio": 0.97,
                "classify_context_errors": True,
            },
        },
        "runtime": {
            "result_mode": "deterministic",
            "unload_model_after_run": True,
            "resume": True,
            "retry_failed": True,
            "sleep_after_load_sec": 2,
            "image_request_smoke_test": True,
        },
        "report": {
            "generate_csv": True,
            "generate_html": True,
            "open_html_after_run": False,
            "thumbnail_size": 256,
        },
        "evaluation": {
            "track_quality_for_manual_review": True,
            "track_speed": True,
            "track_json_stability": True,
            "track_pool_compliance": True,
            "track_hallucinated_tags": True,
        },
    }


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise UserConfigError("Config root must be a YAML mapping")
    return payload

