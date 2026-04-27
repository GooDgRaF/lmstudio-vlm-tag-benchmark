from __future__ import annotations

import yaml

import pytest

from src.config import load_config
from src.image_loader import ImageDiscoveryError, build_image_id, discover_images
from tests.helpers import build_config


def test_extensions_case_insensitive_and_sorted(tmp_path):
    cfg = load_config(build_config(tmp_path))
    images = discover_images(cfg)
    assert [item.image_rel_path for item in images] == ["a.jpg", "B.PNG"]


def test_recursive_mode_enabled(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["input"]["recursive"] = True
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    images = discover_images(cfg)
    assert any(item.image_rel_path == "nested/c.webp" for item in images)


def test_limit_applied_after_sort(tmp_path):
    cfg = load_config(build_config(tmp_path))
    images = discover_images(cfg, limit=1)
    assert len(images) == 1
    assert images[0].image_rel_path == "a.jpg"


def test_image_id_is_deterministic_and_windows_safe():
    one = build_image_id("nested/a b(c).jpg")
    two = build_image_id("nested/a b(c).jpg")
    assert one == two
    assert " " not in one
    assert "(" not in one


def test_missing_image_dir_clear_error(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["input"]["image_dir"] = str(tmp_path / "missing_dir")
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    with pytest.raises(ImageDiscoveryError):
        discover_images(cfg)

