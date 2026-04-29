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
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="strict_json",
    )
    two = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="strict_json",
    )
    three = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v2",
        response_format_requested="strict_json",
    )
    four = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="line_tags",
    )
    five = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_pool",
        prompt_version="v1",
        response_format_requested="line_tags",
        pool_hash="abc123",
    )
    assert one == two
    assert one != three
    assert one != four
    assert four != five


def test_request_id_changes_with_transport_and_reasoning():
    rest_default = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="line_tags",
    )
    openai_default = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="line_tags",
        transport="openai",
    )
    rest_on = build_request_id(
        model_id="m@q4",
        model_label="m",
        image_id="img",
        mode="en_free",
        prompt_version="v1",
        response_format_requested="line_tags",
        reasoning_requested="on",
    )
    assert rest_default != openai_default
    assert rest_default != rest_on


def test_request_artifacts_and_lock(tmp_path):
    cfg = load_config(build_config(tmp_path))
    _, storage = create_run_storage(cfg, run_id="run3")
    storage.acquire_lock()
    assert storage.lock_path.exists()
    storage.save_request_descriptor("req1", {"request_id": "req1"})
    storage.save_request_status("req1", {"status": "running"})
    storage.save_request_raw("req1", {"a": 1})
    storage.save_request_normalized("req1", {"b": 2})
    storage.save_request_diagnostics("req1", {"c": 3})
    assert storage.request_path("req1", "request").exists()
    assert storage.request_path("req1", "status").exists()
    assert storage.request_path("req1", "raw").exists()
    assert storage.request_path("req1", "normalized").exists()
    assert storage.request_path("req1", "diagnostics").exists()
    storage.release_lock()
    assert not storage.lock_path.exists()
