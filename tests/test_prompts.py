from __future__ import annotations

from src.config import load_config
from src.prompts import PROMPT_VERSION, build_prompt
from src.tag_pools import load_tag_pools
from tests.helpers import build_config


def test_prompt_differs_by_mode_and_language(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    ru = build_prompt(cfg, "ru_pool", pools)
    en = build_prompt(cfg, "en_pool", pools)
    assert "Выбирай" in ru.prompt
    assert "Pick tags" in en.prompt


def test_prompt_version_present(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "ru_free", pools)
    assert prompt.prompt_version == PROMPT_VERSION


def test_plain_pool_prompt_contains_allowed_tags(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "en_pool", pools)
    assert "cat" in prompt.prompt
    assert "dog" in prompt.prompt


def test_explained_prompt_contains_ids_and_explanations(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "ru_pool_explained", pools)
    assert "RU001" in prompt.prompt
    assert "[RU001]" not in prompt.prompt
    assert "Безопасно" in prompt.prompt


def test_explained_prompt_asks_for_ids_without_brackets(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "en_pool_explained", pools)
    assert "without square brackets" in prompt.prompt
