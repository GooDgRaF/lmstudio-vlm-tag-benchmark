from __future__ import annotations

import yaml

import pytest

from src.config import ConfigError, load_config
from tests.helpers import build_config


def test_load_example_like_config(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    assert cfg.lmstudio.api_base_url.endswith("/api/v1")
    assert cfg.models[0].label == "m1_q4"
    assert cfg.limits.max_tags == 10
    assert cfg.response_formats.free_modes.primary == "line_tags"
    assert cfg.response_formats.free_modes.fallback == "strict_json"
    assert cfg.response_formats.plain_pool_modes.primary == "line_tags"
    assert cfg.response_formats.plain_pool_modes.fallback == "strict_json"
    assert cfg.runtime.result_mode == "deterministic"
    assert cfg.runtime.retry_failed is True


def test_missing_required_section_raises(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["runtime"]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
