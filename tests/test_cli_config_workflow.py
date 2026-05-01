from __future__ import annotations

import pytest

from main import build_parser, main
from src.model_registry import ModelRegistry


def _registry() -> ModelRegistry:
    return ModelRegistry(
        generated_at="2026-04-30T09:00:00+00:00",
        source="lmstudio",
        api_base_url="http://localhost:1234/api/v1",
        models=[
            {
                "id": "qwen/qwen3-vl-4b@q4_k_m",
                "base_model_id": "qwen/qwen3-vl-4b",
                "label": "qwen3-vl-4b-q4_k_m",
                "reasoning": "default",
                "params": "4B",
                "quant": "Q4_K_M",
                "max_context_length": 262144,
            }
        ],
    )


def test_parser_has_new_commands():
    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices  # noqa: SLF001
    assert "init-config" in choices
    assert "refresh-models" in choices
    assert "list-models" in choices


def test_list_models_reads_registry(monkeypatch, capsys):
    monkeypatch.setattr("main.load_registry", lambda: _registry())
    rc = main(["list-models"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Available model labels:" in out
    assert "qwen3-vl-4b-q4_k_m" in out


def test_list_models_registry_missing(monkeypatch, capsys):
    from src.model_registry import ModelRegistryError

    def boom():
        raise ModelRegistryError("missing")

    monkeypatch.setattr("main.load_registry", boom)
    rc = main(["list-models"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "models.registry.yaml not found" in out


def test_refresh_models(monkeypatch, capsys):
    monkeypatch.setattr("main.refresh_registry", lambda: _registry())
    rc = main(["refresh-models"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Registry entries: 1" in out


def test_dry_run_accepts_simple_config(tmp_path, monkeypatch, capsys):
    (tmp_path / "models.registry.yaml").write_text(
        """
generated_at: "2026-04-30T09:00:00+00:00"
source: "lmstudio"
api_base_url: "http://localhost:1234/api/v1"
models:
  - id: "qwen/qwen3-vl-4b@q4_k_m"
    base_model_id: "qwen/qwen3-vl-4b"
    label: "qwen3-vl-4b-q4_k_m"
    reasoning: "default"
    params: "4B"
    quant: "Q4_K_M"
    quant_bits: 4
    max_context_length: 262144
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "ImgToTag").mkdir()
    (tmp_path / "ImgToTag" / "a.jpg").write_bytes(b"x")
    (tmp_path / "prompts" / "pools").mkdir(parents=True)
    (tmp_path / "prompts").mkdir(exist_ok=True)
    for rel in ["ru_plain.txt", "en_plain.txt", "ru_explained_ids.tsv", "en_explained_ids.tsv"]:
        (tmp_path / "prompts" / "pools" / rel).write_text("x\n", encoding="utf-8")
    for rel in ["ru_free.txt", "ru_pool.txt", "ru_pool_explained.txt", "en_free.txt", "en_pool.txt", "en_pool_explained.txt"]:
        (tmp_path / "prompts" / rel).write_text("x\n", encoding="utf-8")

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
images_folder: "ImgToTag"
models:
  - "qwen3-vl-4b-q4_k_m"
modes:
  - "ru_free"
""".strip(),
        encoding="utf-8",
    )

    rc = main(["dry-run", "--config", str(cfg)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Total requests: 1" in out

