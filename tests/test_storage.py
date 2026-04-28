from __future__ import annotations

import json

from src.config import load_config
from src.storage import build_request_id, create_run_storage
from tests.helpers import build_config


def test_run_folder_structure_created(tmp_path):
    cfg = load_config(build_config(tmp_path))
    _, storage = create_run_storage(cfg, run_id="run1")
    assert storage.raw_dir.exists()
    assert storage.normalized_dir.exists()
    assert storage.assets_thumbs_dir.exists()
    assert storage.models_dir.exists()


def test_save_config_models_raw_normalized_and_errors(tmp_path):
    cfg = load_config(build_config(tmp_path))
    _, storage = create_run_storage(cfg, run_id="run2")
    storage.save_raw_output("req1", {"a": 1})
    storage.save_normalized("req1", {"b": 2})
    storage.save_model_metadata("m1_q4", "load.json", {"ok": True})
    storage.save_diagnostics({"schema_version": 1})
    storage.append_error("boom")
    assert (storage.run_dir / "run_config.yaml").exists()
    assert (storage.run_dir / "models.json").exists()
    assert json.loads(storage.raw_path("req1").read_text(encoding="utf-8"))["a"] == 1
    assert json.loads((storage.run_dir / "diagnostics.json").read_text(encoding="utf-8"))["schema_version"] == 1
    assert "boom" in storage.errors_log_path.read_text(encoding="utf-8")


def test_request_id_deterministic_and_sensitive_to_version_and_format():
    one = build_request_id(
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="strict_json",
    )
    two = build_request_id(
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="strict_json",
    )
    three = build_request_id(
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v2",
        response_format_requested="strict_json",
    )
    four = build_request_id(
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="line_tags",
    )
    assert one == two
    assert one != three
    assert one != four
