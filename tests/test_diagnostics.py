from __future__ import annotations

import subprocess

from src.config import load_config
from src.diagnostics import (
    build_pool_diagnostics,
    classify_load_error,
    collect_gpu_memory,
    detect_git_commit,
    extract_usage_diagnostics,
    summarize_model_requests,
)
from src.tag_pools import load_tag_pools
from tests.helpers import build_config


def test_nvidia_smi_unavailable_not_fatal(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))

    def fake_run(*args, **kwargs):
        raise OSError("missing")

    monkeypatch.setattr(subprocess, "run", fake_run)
    data = collect_gpu_memory(cfg)
    assert data["gpu_diagnostics_available"] is False


def test_parse_csv_style_nvidia_smi_output(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))

    class FakeProc:
        returncode = 0
        stdout = "12227, 1000, 11227\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeProc())
    data = collect_gpu_memory(cfg)
    assert data["memory_total_mb"] == 12227
    assert data["memory_used_mb"] == 1000


def test_malformed_nvidia_output_does_not_crash(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))

    class FakeProc:
        returncode = 0
        stdout = "bad line\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeProc())
    data = collect_gpu_memory(cfg)
    assert data["gpu_diagnostics_available"] is False


def test_oom_load_error_classification():
    assert classify_load_error("CUDA out of memory") == "load_failed_oom"
    assert classify_load_error("something else") == "load_failed"


def test_usage_and_context_flags():
    payload = {
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "choices": [{"finish_reason": "length"}],
    }
    out = extract_usage_diagnostics(payload, actual_context_length=160, warning_ratio=0.85, error_ratio=0.97)
    assert out["prompt_tokens"] == 100
    assert out["context_near_limit"] is True
    assert out["output_truncated"] is True


def test_pool_diagnostics_has_hashes(tmp_path):
    cfg = load_config(build_config(tmp_path))
    pools = load_tag_pools(cfg)
    payload = build_pool_diagnostics(cfg, pools)
    assert set(payload.keys()) == {"ru_plain", "en_plain", "ru_explained", "en_explained"}
    assert payload["ru_plain"]["sha256"]
    assert payload["en_explained"]["entry_count"] >= 1


def test_model_request_summary_stats():
    reqs = [
        {"latency_sec": 1.0, "parse_ok": True, "schema_ok": True, "pool_ok": True, "pool_violations": 0},
        {"latency_sec": 2.0, "parse_ok": False, "schema_ok": True, "pool_ok": False, "pool_violations": 1, "error_type": "request_error"},
    ]
    out = summarize_model_requests(reqs)
    assert out["request_count"] == 2
    assert out["error_count"] == 1
    assert out["median_latency_sec"] == 1.5


def test_detect_git_commit_best_effort(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeProc())
    assert detect_git_commit() is None


def test_rest_stats_usage_mapping_and_truncation_inference():
    payload = {
        "stats": {"input_tokens": 20, "total_output_tokens": 64},
        "max_output_tokens": 64,
    }
    out = extract_usage_diagnostics(payload, actual_context_length=100, warning_ratio=0.85, error_ratio=0.97)
    assert out["prompt_tokens"] == 20
    assert out["completion_tokens"] == 64
    assert out["total_tokens"] == 84
    assert out["output_truncated"] is True
