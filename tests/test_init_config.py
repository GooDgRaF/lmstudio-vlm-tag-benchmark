from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from main import main
from src.model_registry import ModelRegistry


def _registry(labels: list[str]) -> ModelRegistry:
    return ModelRegistry(
        generated_at="2026-04-30T09:00:00+00:00",
        source="lmstudio",
        api_base_url="http://localhost:1234/api/v1",
        models=[
            {
                "id": f"id-{i}",
                "base_model_id": f"base-{i}",
                "label": label,
                "reasoning": "default",
            }
            for i, label in enumerate(labels)
        ],
    )


def test_init_config_writes_yaml_and_embeds_models_and_modes(tmp_path, monkeypatch):
    out = tmp_path / "config.yaml"

    def fake_refresh_registry():
        return _registry(["qwen3-vl-4b-q4_k_m", "qwen3-vl-8b-q4_k_m"])

    monkeypatch.setattr("main.refresh_registry", fake_refresh_registry)
    rc = main(["init-config", "--output", str(out)])
    assert rc == 0

    text = out.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    assert loaded["images_folder"] == "ImgToTag"
    assert loaded["models"] == ["qwen3-vl-4b-q4_k_m"]
    assert loaded["modes"] == ["ru_free"]
    assert '# tag_files:' in text
    assert '#   ru_plus: "prompts/pools/ru_explained_ids.tsv"' in text
    assert '#   ru_pool: "prompts/ru_pool.txt"' in text
    assert '# - "qwen3-vl-8b-q4_k_m"' in text
    assert '# - "en_pool"' in text


def test_init_config_refuses_overwrite_without_force(tmp_path, monkeypatch):
    out = tmp_path / "config.yaml"
    out.write_text("x: 1\n", encoding="utf-8")

    monkeypatch.setattr("main.refresh_registry", lambda: _registry(["qwen3-vl-4b-q4_k_m"]))
    with pytest.raises(SystemExit) as exc:
        main(["init-config", "--output", str(out)])
    assert "already exists" in str(exc.value)


def test_init_config_overwrites_with_force(tmp_path, monkeypatch):
    out = tmp_path / "config.yaml"
    out.write_text("x: 1\n", encoding="utf-8")

    monkeypatch.setattr("main.refresh_registry", lambda: _registry(["qwen3-vl-4b-q4_k_m"]))
    rc = main(["init-config", "--output", str(out), "--force"])
    assert rc == 0
    assert "images_folder" in out.read_text(encoding="utf-8")


def test_init_config_no_models_fallback(tmp_path, monkeypatch):
    out = tmp_path / "config.yaml"
    monkeypatch.setattr("main.refresh_registry", lambda: _registry([]))
    rc = main(["init-config", "--output", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "No LM Studio models were found" in text

