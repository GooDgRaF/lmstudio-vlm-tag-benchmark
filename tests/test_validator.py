from __future__ import annotations

import yaml

import pytest

from src.config import ConfigError, load_config
from src.validator import ValidationError, validate_config
from tests.helpers import build_config


def test_valid_config_passes(tmp_path):
    cfg = load_config(build_config(tmp_path))
    validate_config(cfg)


def test_missing_required_section_fails(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["report"]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_duplicate_model_label_fails(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    copy = dict(data["models"][0])
    copy["id"] = "m2@q4"
    data["models"].append(copy)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    with pytest.raises(ValidationError, match="Duplicate model label"):
        validate_config(cfg)


def test_unknown_mode_fails(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["ru_free", "xx_mode"]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    with pytest.raises(ValidationError, match="Unknown mode"):
        validate_config(cfg)


def test_context_too_large_fails(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["load"]["context_length"] = 999999
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    with pytest.raises(ValidationError, match="exceeds"):
        validate_config(cfg)


def test_missing_pool_file_fails(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["pools"]["ru_plain"] = "pools/missing.txt"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    with pytest.raises(ValidationError, match="Pool file does not exist"):
        validate_config(cfg)


@pytest.mark.parametrize("reasoning", ["default", "on", "off"])
def test_reasoning_values_allowed(tmp_path, reasoning):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["models"][0]["reasoning"] = reasoning
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    validate_config(cfg)


@pytest.mark.parametrize("reasoning", ["low", "high", "custom"])
def test_reasoning_values_rejected(tmp_path, reasoning):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["models"][0]["reasoning"] = reasoning
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    with pytest.raises(ValidationError, match="Unsupported model reasoning value"):
        validate_config(cfg)


def test_duplicate_model_ids_allowed_if_labels_unique(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    copy = dict(data["models"][0])
    copy["label"] = "m1_q4_variant2"
    data["models"].append(copy)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    validate_config(cfg)


def test_repo_reasoning_configs_validate():
    for path in [
        "configs/config.smoke.yaml",
        "configs/config.example.yaml",
        "configs/config.rest-reasoning-smoke.yaml",
    ]:
        cfg = load_config(path)
        validate_config(cfg)

