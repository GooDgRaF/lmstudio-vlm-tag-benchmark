from __future__ import annotations

import yaml
import pytest

from src.config import load_config
from src.tag_pools import TagPoolError, load_tag_pools
from tests.helpers import build_config


def test_plain_pools_skip_comments_and_keep_spelling(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    assert "кот" in pools.ru_plain
    assert "собака" in pools.ru_plain


def test_explained_tsv_parsing_and_mapping(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    assert pools.ru_explained[0].id == "RU001"
    assert pools.ids_to_tags("ru", ["RU002"]) == ["Аниме"]


def test_duplicate_ids_fail(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    tsv_path = cfg.resolve_path(cfg.pools.ru_explained)
    tsv_path.write_text("RU001\tA\tB\nRU001\tC\tD\n", encoding="utf-8")
    with pytest.raises(TagPoolError, match="Duplicate ID"):
        load_tag_pools(cfg)


def test_prompt_text_contains_id_tag_explanation(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    text = pools.explained_prompt_text("en")
    assert "[EN001] General - Safe" in text

