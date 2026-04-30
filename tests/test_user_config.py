from __future__ import annotations

from pathlib import Path

import pytest

from src.config import load_config
from src.user_config import UserConfigError, detect_config_style, expand_user_config
from tests.helpers import build_config


def _write_registry(root: Path) -> None:
    (root / "models.registry.yaml").write_text(
        """
generated_at: "2026-04-30T09:00:00+00:00"
source: "lmstudio"
api_base_url: "http://localhost:1234/api/v1"
models:
  - id: "qwen/qwen3.5-9b@q4_k_m"
    base_model_id: "qwen/qwen3.5-9b"
    label: "qwen3_5-9b-q4_k_m-no-think"
    reasoning: "off"
    params: "9B"
    quant: "Q4_K_M"
    quant_bits: 4
    max_context_length: 262144
""".strip(),
        encoding="utf-8",
    )


def test_detect_config_style():
    assert detect_config_style({"lmstudio": {}, "models": []}) == "full"
    assert detect_config_style({"images_folder": "ImgToTag", "models": ["a"]}) == "simple"


def test_expand_simple_config_to_full(tmp_path):
    _write_registry(tmp_path)
    simple = {
        "images_folder": "ImgToTag",
        "models": ["qwen3_5-9b-q4_k_m-no-think"],
        "modes": ["ru_free"],
        "output_folder": "results",
        "context_length": 8192,
        "max_output_tokens": 4096,
        "temperature": 0.0,
        "recursive": False,
    }
    expanded = expand_user_config(simple, root_dir=tmp_path)
    assert expanded["generation"]["max_tokens"] == 4096
    assert expanded["load"]["context_length"] == 8192
    assert expanded["models"][0]["reasoning"] == "off"


def test_expand_missing_registry_error(tmp_path):
    simple = {"images_folder": "ImgToTag", "models": ["x"], "modes": ["ru_free"]}
    with pytest.raises(UserConfigError) as exc:
        expand_user_config(simple, root_dir=tmp_path)
    assert "init-config" in str(exc.value)


def test_unknown_key_error(tmp_path):
    _write_registry(tmp_path)
    simple = {
        "images_folder": "ImgToTag",
        "models": ["qwen3_5-9b-q4_k_m-no-think"],
        "modes": ["ru_free"],
        "max_tokens": 100,
    }
    with pytest.raises(UserConfigError) as exc:
        expand_user_config(simple, root_dir=tmp_path)
    assert "max_output_tokens" in str(exc.value)


def test_full_config_still_loads(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    assert cfg.models


def test_load_config_simple_profile(tmp_path):
    _write_registry(tmp_path)
    simple_path = tmp_path / "config.yaml"
    simple_path.write_text(
        """
images_folder: "ImgToTag"
models:
  - "qwen3_5-9b-q4_k_m-no-think"
modes:
  - "ru_free"
max_output_tokens: 4096
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "ImgToTag").mkdir()
    (tmp_path / "pools").mkdir()
    for rel in ["ru_plain.txt", "en_plain.txt", "ru_explained_ids.tsv", "en_explained_ids.tsv"]:
        (tmp_path / "pools" / rel).write_text("x\n", encoding="utf-8")

    cfg = load_config(simple_path)
    assert cfg.generation.max_tokens == 4096
    assert cfg.models[0].reasoning == "off"
