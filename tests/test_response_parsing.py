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


def test_line_tags_parses_as_primary_format(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="cat\ndog",
        mode="en_free",
        requested_response_format="line_tags",
    )
    assert out["parse_ok"] is True
    assert out["accepted_tags"] == ["cat", "dog"]
    assert out["response_format_used"] == "line_tags"


def test_line_tags_filters_reasoning_prose_and_keeps_tag_candidates(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output=(
            "Thinking Process:\n"
            "1. **Analyze the image:** The image contains pixel art weapons.\n"
            "2. **Obvious tags:** axe, sword\n"
            "3. Sword\n"
            "Pixel art\n"
            "This long sentence is an explanation and should not become a tag."
        ),
        mode="en_free",
        requested_response_format="line_tags",
    )
    assert out["parse_ok"] is True
    assert out["accepted_tags"] == ["axe", "sword", "Sword", "Pixel art"]
    assert "Thinking Process:" not in out["accepted_tags"]


def test_line_tags_strips_trailing_parenthetical_notes(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="кот (животное).\nсобака (питомец)",
        mode="ru_pool",
        requested_response_format="line_tags",
    )
    assert out["accepted_tags"] == ["кот", "собака"]
    assert out["rejected_tags"] == []


def test_line_tags_reasoning_only_is_parse_error(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output=(
            "General analysis of the image:\n"
            "The image is a pixel art representation of a game item display."
        ),
        mode="en_pool",
        requested_response_format="line_tags",
    )
    assert out["parse_ok"] is False
    assert out["error_type"] == "parse_error"
    assert out["accepted_tags"] == []
    assert out["rejected_tags"] == []


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


def test_pool_tags_with_inline_reasoning_use_bottom_valid_group(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output=(
            "The user wants me to generate image tags.\n"
            "1. **Analyze the image:** It contains a cat and a dog.\n"
            "Tags selected: cat, invented, dogcat\n"
            "\n"
            "Final selection based on rules:\n"
            "cat\n"
            "dog"
        ),
        mode="en_pool",
        requested_response_format="line_tags",
    )
    assert out["accepted_tags"] == ["cat", "dog"]
    assert out["rejected_tags"] == []
    assert out["pool_ok"] is True
    assert out["reasoning_leak_detected"] is True
    assert out["reasoning_leak_recovered"] is True


def test_unknown_explained_ids_rejected(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output="EN001\nEN999",
        mode="en_pool_explained",
        requested_response_format="line_ids",
    )
    assert out["accepted_ids"] == ["EN001"]
    assert out["rejected_ids"] == ["EN999"]


def test_pool_ids_with_inline_reasoning_use_bottom_valid_group(tmp_path):
    out = _normalize(
        tmp_path,
        raw_output=(
            "* **Analyze the image:** choose from the ID list.\n"
            "EN999 appears in the reasoning but is invalid.\n"
            "\n"
            "* **Final List Construction:** EN001, EN002.\n"
            "EN001\n"
            "EN002"
        ),
        mode="en_pool_explained",
        requested_response_format="line_ids",
    )
    assert out["accepted_ids"] == ["EN001", "EN002"]
    assert out["accepted_tags"] == ["General", "Anime"]
    assert out["rejected_ids"] == []
    assert out["reasoning_leak_detected"] is True
    assert out["reasoning_leak_recovered"] is True


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


def test_tag_count_is_not_capped_by_parser(tmp_path):
    tags = [f"t{i}" for i in range(20)]
    out = _normalize(
        tmp_path,
        raw_output='{"tags":' + str(tags).replace("'", '"') + "}",
        mode="en_free",
        requested_response_format="strict_json",
    )
    assert len(out["accepted_tags"]) == 20
