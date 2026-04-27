from __future__ import annotations

import json
import yaml

from src.config import load_config
from src.runner import _resume_decision
from tests.helpers import build_config


def test_success_existing_result_is_skipped(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    result_path = tmp_path / "ok.json"
    result_path.write_text(
        json.dumps({"error_type": None, "parse_ok": True, "pool_ok": True}),
        encoding="utf-8",
    )
    assert _resume_decision(cfg, result_path, "en_pool") == "skip"


def test_existing_error_retried_when_enabled(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    result_path = tmp_path / "err.json"
    result_path.write_text(
        json.dumps({"error_type": "request_error", "parse_ok": False, "pool_ok": False}),
        encoding="utf-8",
    )
    assert _resume_decision(cfg, result_path, "en_pool") == "retry"


def test_existing_error_skipped_when_retry_disabled(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["runtime"]["retry_existing_errors"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    result_path = tmp_path / "err.json"
    result_path.write_text(
        json.dumps({"error_type": "request_error", "parse_ok": False, "pool_ok": False}),
        encoding="utf-8",
    )
    assert _resume_decision(cfg, result_path, "en_pool") == "skip"


def test_pool_ok_false_not_success(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    result_path = tmp_path / "badpool.json"
    result_path.write_text(
        json.dumps({"error_type": None, "parse_ok": True, "pool_ok": False}),
        encoding="utf-8",
    )
    assert _resume_decision(cfg, result_path, "en_pool") == "retry"


def test_resume_disabled_forces_run(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["runtime"]["resume"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    result_path = tmp_path / "ok.json"
    result_path.write_text(
        json.dumps({"error_type": None, "parse_ok": True, "pool_ok": True}),
        encoding="utf-8",
    )
    assert _resume_decision(cfg, result_path, "en_pool") == "run"

