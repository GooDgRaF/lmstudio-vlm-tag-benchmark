from __future__ import annotations

import yaml

from src.config import load_config
from src.runner import _status_decision
from tests.helpers import build_config


def test_success_status_is_skipped_in_deterministic_resume(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    assert _status_decision(cfg, {"status": "success"}) == "skip"


def test_failed_status_retried_when_enabled(tmp_path):
    path = build_config(tmp_path)
    cfg = load_config(path)
    assert _status_decision(cfg, {"status": "failed"}) == "run"


def test_failed_status_skipped_when_retry_disabled(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["runtime"]["retry_failed"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    assert _status_decision(cfg, {"status": "failed"}) == "skip"


def test_resume_disabled_forces_run(tmp_path):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["runtime"]["resume"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    assert _status_decision(cfg, {"status": "success"}) == "run"
