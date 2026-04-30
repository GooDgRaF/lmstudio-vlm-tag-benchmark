from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import yaml

from src.lmstudio_client import LMStudioClient

DEFAULT_LMSTUDIO_HOST = "http://localhost:1234"
DEFAULT_API_BASE_URL = "http://localhost:1234/api/v1"
DEFAULT_OPENAI_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_TIMEOUT_SEC = 180

RAW_MODELS_PATH = Path("models/lmstudio-models.raw.json")
ACTIVE_MODELS_PATH = Path("models/models.active.yaml")
EXCLUDED_MODELS_PATH = Path("models/models.excluded.yaml")
DEFAULT_REGISTRY_PATH = Path("models.registry.yaml")

MODEL_ID_CANDIDATE_KEYS = ["id", "model_id", "selected_variant", "selectedVariant", "key", "modelKey"]
REASONING_TOGGLE_FAMILIES = ["qwen3.5", "qwen3_5", "gemma-4", "gemma4"]


class ModelRegistryError(RuntimeError):
    """Model registry operation error."""


@dataclass(frozen=True)
class ModelRegistry:
    generated_at: str
    source: str
    api_base_url: str
    models: list[dict[str, Any]]


def _parse_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _parse_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        v = value.strip().replace("_", "")
        if v.isdigit():
            return int(v)
    return None


def _extract_model_id(raw: dict[str, Any]) -> str | None:
    for key in MODEL_ID_CANDIDATE_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_quant_from_id(model_id: str) -> str | None:
    if "@" not in model_id:
        return None
    return model_id.split("@", 1)[1]


def _extract_base_model_id(model_id: str) -> str:
    return model_id.split("@", 1)[0]


def _label_base_name(base_model_id: str) -> str:
    short = base_model_id.split("/", 1)[1] if "/" in base_model_id else base_model_id
    return short.replace(".", "_")


def _looks_like_llm(raw: dict[str, Any], model_id: str) -> bool:
    model_type = str(raw.get("type", "")).strip().lower()
    if model_type and model_type != "llm":
        return False
    text = " ".join(
        [
            model_id,
            str(raw.get("display_name") or raw.get("name") or ""),
            str(raw.get("architecture") or ""),
            str(raw.get("task") or ""),
        ]
    ).lower()
    non_llm_markers = ["embedding", "embed", "rerank", "tts", "asr", "whisper", "clip"]
    if any(marker in text for marker in non_llm_markers):
        return False
    return True


def _extract_vision(raw: dict[str, Any]) -> bool:
    if isinstance(raw.get("vision"), bool):
        return bool(raw.get("vision"))
    capabilities = raw.get("capabilities")
    if isinstance(capabilities, dict):
        if isinstance(capabilities.get("vision"), bool):
            return bool(capabilities.get("vision"))
    return False


def _parse_params_billions(raw: dict[str, Any], model_id: str) -> tuple[str | None, float | None]:
    candidates = [raw.get("params"), raw.get("parameter_count"), raw.get("parameters")]
    id_lower = model_id.lower()
    id_match = re.search(r"(\d+(?:\.\d+)?)b\b", id_lower)
    if id_match:
        value = float(id_match.group(1))
        return f"{id_match.group(1)}B", value

    for val in candidates:
        if isinstance(val, (int, float)):
            num = float(val)
            if num > 1000:
                num = num / 1_000_000_000.0
            return f"{num:g}B", num
        if isinstance(val, str):
            text = val.strip()
            m = re.search(r"(\d+(?:\.\d+)?)\s*([bBmM])", text)
            if m:
                num = float(m.group(1))
                unit = m.group(2).lower()
                if unit == "m":
                    num /= 1000.0
                return f"{m.group(1)}{m.group(2).upper()}", num
    return None, None


def _extract_allowed_reasoning(raw: dict[str, Any]) -> set[str]:
    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, dict):
        return set()
    reasoning = capabilities.get("reasoning")
    if not isinstance(reasoning, dict):
        return set()
    options = reasoning.get("allowed_options")
    if not isinstance(options, list):
        return set()
    return {str(item).strip().lower() for item in options if str(item).strip()}


def _supports_reasoning_toggle(base_model_id: str, raw: dict[str, Any]) -> bool:
    options = _extract_allowed_reasoning(raw)
    if "on" in options and "off" in options:
        return True
    base = base_model_id.lower().replace(".", "_")
    return any(token in base for token in REASONING_TOGGLE_FAMILIES)


def _label_with_reasoning(base_label: str, reasoning: str) -> str:
    if reasoning == "on":
        return f"{base_label}-think"
    if reasoning == "off":
        return f"{base_label}-no-think"
    return base_label


def _make_unique_labels(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in models:
        label = str(item["label"])
        if label in seen:
            digest = hashlib.sha1(str(item["id"]).encode("utf-8")).hexdigest()[:6]
            label = f"{label}-{digest}"
        seen.add(label)
        cloned = dict(item)
        cloned["label"] = label
        out.append(cloned)
    return out


def _normalized_variants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    variants = raw.get("variants")
    if isinstance(variants, list) and variants:
        out: list[dict[str, Any]] = []
        for variant in variants:
            if isinstance(variant, dict):
                merged = dict(raw)
                merged.update(variant)
                out.append(merged)
            elif isinstance(variant, str):
                merged = dict(raw)
                merged["id"] = variant
                out.append(merged)
        return out
    return [raw]


def _build_candidate_entries(raw_models: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for raw in raw_models:
        for item in _normalized_variants(raw):
            model_id = _extract_model_id(item)
            if not model_id:
                excluded.append({"reason": "missing_model_id", "raw": {"id": item.get("id"), "name": item.get("name")}})
                continue

            if not _looks_like_llm(item, model_id):
                excluded.append({"id": model_id, "reason": "not_llm"})
                continue

            if not _extract_vision(item):
                excluded.append({"id": model_id, "reason": "not_vision"})
                continue

            params_text, params_b = _parse_params_billions(item, model_id)
            if params_b is None:
                excluded.append({"id": model_id, "reason": "unknown_params"})
                continue
            if params_b >= 10.0:
                excluded.append({"id": model_id, "reason": "params_over_10b", "params": params_text})
                continue

            base_model_id = _extract_base_model_id(model_id)
            quant = _extract_quant_from_id(model_id) or str(item.get("quant") or "").strip() or None
            quant_bits = _parse_int(item.get("quant_bits"))
            if quant_bits is None and quant:
                q_match = re.match(r"q(\d+)", quant.lower())
                if q_match:
                    quant_bits = int(q_match.group(1))

            display_name = item.get("display_name") or item.get("name")
            architecture = item.get("architecture")
            size_bytes = _parse_int(item.get("size_bytes") or item.get("size"))
            max_context = _parse_int(item.get("max_context_length") or item.get("context_length"))

            quant_for_label = (quant or "unknown").lower()
            base_label = f"{_label_base_name(base_model_id)}-{quant_for_label}"
            if _supports_reasoning_toggle(base_model_id, item):
                reasonings = ["on", "off"]
            else:
                reasonings = ["default"]

            for reasoning in reasonings:
                active.append(
                    {
                        "id": model_id,
                        "base_model_id": base_model_id,
                        "label": _label_with_reasoning(base_label, reasoning),
                        "reasoning": reasoning,
                        "display_name": display_name,
                        "params": params_text,
                        "architecture": architecture,
                        "quant": quant,
                        "quant_bits": quant_bits,
                        "size_bytes": size_bytes,
                        "max_context_length": max_context,
                    }
                )

    return _make_unique_labels(active), excluded


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8")


def _model_registry_to_dict(registry: ModelRegistry) -> dict[str, Any]:
    return {
        "generated_at": registry.generated_at,
        "source": registry.source,
        "api_base_url": registry.api_base_url,
        "models": registry.models,
    }


def refresh_registry(output_path: Path = DEFAULT_REGISTRY_PATH) -> ModelRegistry:
    client = LMStudioClient(
        api_base_url=DEFAULT_API_BASE_URL,
        openai_base_url=DEFAULT_OPENAI_BASE_URL,
        api_key=DEFAULT_API_KEY,
        timeout_sec=DEFAULT_TIMEOUT_SEC,
    )
    raw_models = client.list_models()

    RAW_MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_MODELS_PATH.write_text(json.dumps(raw_models, ensure_ascii=False, indent=2), encoding="utf-8")

    active_models, excluded_models = _build_candidate_entries(raw_models)
    _write_yaml(ACTIVE_MODELS_PATH, {"models": active_models})
    _write_yaml(EXCLUDED_MODELS_PATH, {"models": excluded_models})

    registry = ModelRegistry(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        source="lmstudio",
        api_base_url=DEFAULT_API_BASE_URL,
        models=active_models,
    )
    _write_yaml(output_path, _model_registry_to_dict(registry))
    return registry


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> ModelRegistry:
    if not path.exists():
        raise ModelRegistryError(f"Registry file not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ModelRegistryError("Registry root must be a mapping")
    models = payload.get("models")
    if not isinstance(models, list):
        raise ModelRegistryError("Registry must contain a models list")
    return ModelRegistry(
        generated_at=str(payload.get("generated_at") or ""),
        source=str(payload.get("source") or ""),
        api_base_url=str(payload.get("api_base_url") or DEFAULT_API_BASE_URL),
        models=[dict(item) for item in models if isinstance(item, dict)],
    )


def list_registry_labels(registry: ModelRegistry) -> list[str]:
    labels = [str(item.get("label") or "") for item in registry.models]
    return [label for label in labels if label]


def resolve_model_labels(labels: list[str], registry: ModelRegistry) -> list[dict[str, Any]]:
    index = {str(item.get("label")): item for item in registry.models if item.get("label")}
    resolved: list[dict[str, Any]] = []
    known = sorted(index.keys())
    for label in labels:
        if label not in index:
            hints = get_close_matches(label, known, n=3, cutoff=0.4)
            hint_lines = "\n".join(f"- {item}" for item in hints)
            if hints:
                raise ModelRegistryError(
                    f"Unknown model label: {label}\n"
                    "Run `python main.py init-config --force` to refresh config, or use one of:\n"
                    f"{hint_lines}"
                )
            raise ModelRegistryError(
                f"Unknown model label: {label}\n"
                "Run `python main.py list-models` to see available labels."
            )
        resolved.append(dict(index[label]))
    return resolved
