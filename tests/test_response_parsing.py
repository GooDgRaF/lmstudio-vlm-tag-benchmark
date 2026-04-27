from __future__ import annotations

from src.config import load_config
from src.prompts import PROMPT_VERSION
from src.tag_pools import load_tag_pools
from src.validator import normalize_model_output
from tests.helpers import build_config


def _normalize(tmp_path, **kwargs):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    return normalize_model_output(
        pools=pools,
        max_tags=cfg.limits.max_tags,
        allow_json_extraction=True,
        allow_line_fallback=True,
        drop_tags_not_in_pool=True,
        prompt_version=PROMPT_VERSION,
        **kwargs,
    )


def test_strict_json_parses(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output='{"tags":["cat","dog"]}',
        mode="en_free",
        requested_response_format="strict_json",
    )
    assert out["parse_ok"] is True
    assert out["accepted_tags"] == ["cat", "dog"]


def test_json_extraction_works(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output='noise {"tags":["cat"]} trailing',
        mode="en_free",
        requested_response_format="strict_json",
    )
    assert out["json_extracted"] is True
    assert out["accepted_tags"] == ["cat"]


def test_line_fallback_works(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="cat\ndog",
        mode="en_free",
        requested_response_format="strict_json",
    )
    assert out["line_fallback_used"] is True
    assert out["accepted_tags"] == ["cat", "dog"]


def test_duplicates_removed_order_preserved(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output='{"tags":["cat","cat","dog"]}',
        mode="en_free",
        requested_response_format="strict_json",
    )
    assert out["accepted_tags"] == ["cat", "dog"]


def test_pool_rejects_out_of_pool_without_fuzzy(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output='{"tags":["cat","DOG"]}',
        mode="en_pool",
        requested_response_format="strict_json",
    )
    assert out["accepted_tags"] == ["cat"]
    assert out["rejected_tags"] == ["DOG"]


def test_unknown_explained_ids_rejected(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="EN001\nEN999",
        mode="en_pool_explained",
        requested_response_format="line_ids",
    )
    assert out["accepted_ids"] == ["EN001"]
    assert out["rejected_ids"] == ["EN999"]


def test_bracketed_explained_ids_are_mapped_to_tags(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="[EN001]\n[EN002]",
        mode="en_pool_explained",
        requested_response_format="line_ids",
    )
    assert out["accepted_ids"] == ["EN001", "EN002"]
    assert out["accepted_tags"] == ["General", "Anime"]
    assert out["rejected_ids"] == []


def test_comma_separated_explained_ids_are_mapped_to_tags(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="[EN001], [EN002]",
        mode="en_pool_explained",
        requested_response_format="line_ids",
    )
    assert out["accepted_ids"] == ["EN001", "EN002"]
    assert out["accepted_tags"] == ["General", "Anime"]


def test_explained_mode_tag_text_rejected(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="General\nAnime",
        mode="en_pool_explained",
        requested_response_format="line_ids",
    )
    assert out["accepted_ids"] == []
    assert out["rejected_ids"] == ["General", "Anime"]


def test_tag_count_capped_at_10(tmp_path):
    tags = [f"t{i}" for i in range(20)]
    out = _normalize(
        tmp_path,
        raw_output='{"tags":' + str(tags).replace("'", '"') + "}",
        mode="en_free",
        requested_response_format="strict_json",
    )
    assert len(out["accepted_tags"]) == 10
