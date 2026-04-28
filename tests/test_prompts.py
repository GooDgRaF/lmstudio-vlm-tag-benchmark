from __future__ import annotations

from src.config import load_config
from src.prompts import PROMPT_VERSION, build_prompt
from src.tag_pools import load_tag_pools
from tests.helpers import build_config


def test_prompt_version_is_v2(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "ru_free", pools)
    assert PROMPT_VERSION == "v2"
    assert prompt.prompt_version == "v2"


def test_ru_free_prompt_language_and_line_format(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "ru_free", pools)
    assert "на русском языке" in prompt.prompt
    assert "Формат ответа: один тег на строку" in prompt.prompt


def test_en_free_prompt_language_and_line_format(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "en_free", pools)
    assert "in English" in prompt.prompt
    assert "Answer format: one tag per line" in prompt.prompt


def test_free_prompt_contains_min3_and_staged_prioritization(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    prompt = build_prompt(cfg, "en_free", pools)
    assert "At least 3 tags" in prompt.prompt
    assert "First give the 3 most obvious tags" in prompt.prompt
    assert "add up to 3 more tags" in prompt.prompt
    assert "add up to 4 more tags" in prompt.prompt


def test_plain_pool_prompt_contains_pool_restriction_and_preserve_spelling(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    ru_prompt = build_prompt(cfg, "ru_pool", pools)
    en_prompt = build_prompt(cfg, "en_pool", pools)
    assert "Выбирай теги только из списка ниже" in ru_prompt.prompt
    assert "Не изменяй написание тегов" in ru_prompt.prompt
    assert "Choose tags only from the list below" in en_prompt.prompt
    assert "Do not change tag spelling" in en_prompt.prompt


def test_explained_prompt_asks_for_ids_only_per_line(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    ru_prompt = build_prompt(cfg, "ru_pool_explained", pools)
    en_prompt = build_prompt(cfg, "en_pool_explained", pools)
    assert "Формат ответа: один ID на строку" in ru_prompt.prompt
    assert "Answer format: one ID per line" in en_prompt.prompt


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
