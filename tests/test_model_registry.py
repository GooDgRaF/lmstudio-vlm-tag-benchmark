from __future__ import annotations

from pathlib import Path

import pytest

from src.model_registry import (
    ModelRegistry,
    ModelRegistryError,
    _build_candidate_entries,
    _label_base_name,
    _parse_params_billions,
    list_registry_labels,
    load_registry,
    resolve_model_labels,
)


def test_label_base_name_replaces_dots():
    assert _label_base_name("qwen/qwen3.5-9b") == "qwen3_5-9b"


def test_params_parsing_from_id_and_string():
    text, value = _parse_params_billions({"params": "4.6B"}, "x/y")
    assert text == "4.6B"
    assert value == pytest.approx(4.6)

    text2, value2 = _parse_params_billions({}, "qwen/qwen3-vl-8b@q4_k_m")
    assert text2 == "8B"
    assert value2 == pytest.approx(8.0)


def test_build_candidate_entries_filters_and_expands_variants_and_reasoning():
    raw_models = [
        {
            "id": "qwen/qwen3-vl-4b",
            "type": "llm",
            "vision": True,
            "params": "4B",
            "variants": [
                {"id": "qwen/qwen3-vl-4b@q4_k_m", "quant": "Q4_K_M"},
                {"id": "qwen/qwen3-vl-4b@q8_0", "quant": "Q8_0"},
            ],
        },
        {
            "id": "qwen/qwen3.5-9b@q4_k_m",
            "type": "llm",
            "vision": True,
            "params": "9B",
            "capabilities": {"reasoning": {"allowed_options": ["on", "off"]}},
            "quant": "Q4_K_M",
        },
        {
            "id": "google/gemma-27b@q4_k_m",
            "type": "llm",
            "vision": True,
            "params": "27B",
        },
        {
            "id": "other/not-vision@q4_k_m",
            "type": "llm",
            "vision": False,
            "params": "4B",
        },
    ]

    active, excluded = _build_candidate_entries(raw_models)
    labels = [m["label"] for m in active]

    assert "qwen3-vl-4b-q4_k_m" in labels
    assert "qwen3-vl-4b-q8_0" in labels
    assert "qwen3_5-9b-q4_k_m-think" in labels
    assert "qwen3_5-9b-q4_k_m-no-think" in labels
    reasons = {item.get("reason") for item in excluded}
    assert "params_over_10b" in reasons
    assert "not_vision" in reasons


def test_collision_labels_are_uniquified():
    raw_models = [
        {
            "id": "foo/model@q4_k_m",
            "type": "llm",
            "vision": True,
            "params": "4B",
            "quant": "Q4_K_M",
        },
        {
            "id": "foo/model@Q4_K_M",
            "type": "llm",
            "vision": True,
            "params": "4B",
            "quant": "Q4_K_M",
        },
    ]
    active, _ = _build_candidate_entries(raw_models)
    labels = [m["label"] for m in active]
    assert len(labels) == len(set(labels))


def test_registry_roundtrip_and_label_resolution(tmp_path):
    path = tmp_path / "models.registry.yaml"
    path.write_text(
        """
generated_at: "2026-04-30T09:00:00+00:00"
source: "lmstudio"
api_base_url: "http://localhost:1234/api/v1"
models:
  - id: "qwen/qwen3-vl-4b@q4_k_m"
    base_model_id: "qwen/qwen3-vl-4b"
    label: "qwen3-vl-4b-q4_k_m"
    reasoning: "default"
""".strip(),
        encoding="utf-8",
    )
    registry = load_registry(path)
    assert isinstance(registry, ModelRegistry)
    assert list_registry_labels(registry) == ["qwen3-vl-4b-q4_k_m"]

    resolved = resolve_model_labels(["qwen3-vl-4b-q4_k_m"], registry)
    assert resolved[0]["id"] == "qwen/qwen3-vl-4b@q4_k_m"


def test_unknown_label_error_has_hints():
    registry = ModelRegistry(
        generated_at="",
        source="lmstudio",
        api_base_url="http://localhost:1234/api/v1",
        models=[
            {"label": "qwen3-vl-4b-q4_k_m", "id": "a", "base_model_id": "a", "reasoning": "default"},
            {"label": "qwen3-vl-4b-q8_0", "id": "b", "base_model_id": "b", "reasoning": "default"},
        ],
    )

    with pytest.raises(ModelRegistryError) as exc:
        resolve_model_labels(["qwen3-vl-4b-q4"], registry)
    message = str(exc.value)
    assert "Unknown model label" in message
    assert "qwen3-vl-4b-q4_k_m" in message
