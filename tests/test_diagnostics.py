from __future__ import annotations

import subprocess

from src.config import load_config
from src.diagnostics import classify_load_error, collect_gpu_memory, extract_usage_diagnostics
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

