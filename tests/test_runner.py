from __future__ import annotations

import json
import yaml

from src.config import load_config
from src.runner import run_benchmark
from tests.helpers import build_config


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.loaded = []
        self.unloaded = []
        self.unload_all_calls = 0
        self.chat_model_ids = []

    @classmethod
    def from_config(cls, cfg):
        return cls()

    def list_models(self):
        return [{"id": "m1@q4"}]

    def unload_all_loaded_models(self):
        self.unload_all_calls += 1
        return []

    def load_model(self, model, load_config):
        self.loaded.append(model.id)
        from src.lmstudio_client import LoadedModel

        return LoadedModel(
            id=model.id,
            base_model_id=model.base_model_id,
            label=model.label,
            instance_id="inst1",
            params=model.params,
            quant=model.quant,
            quant_bits=model.quant_bits,
            requested_context_length=load_config.get("context_length"),
            actual_context_length=load_config.get("context_length"),
            load_config=load_config,
        )

    def unload_model(self, instance_id, model_id_fallback=None):
        self.unloaded.append(instance_id)
        return {"ok": True}

    def chat_completion(self, **kwargs):
        self.chat_model_ids.append(kwargs.get("model_id"))
        return {
            "choices": [{"message": {"content": '{"tags":["cat"]}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


def test_runner_vertical_slice_saves_raw_and_normalized(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)

    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)
    run_dir = run_benchmark(cfg, limit=1)
    raw_files = list((run_dir / "raw").glob("*.json"))
    normalized_files = list((run_dir / "normalized").glob("*.json"))
    assert len(raw_files) == 1
    assert len(normalized_files) == 1
    assert (run_dir / "report.html").exists()


def test_runner_attempts_all_modes_for_image(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)
    run_dir = run_benchmark(cfg, limit=1)
    rows = (run_dir / "summary.csv").read_text(encoding="utf-8-sig").splitlines()
    # header + 6 mode rows
    assert len(rows) == 7


def test_runner_preload_unload_is_called(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)

    fake = FakeClient()
    monkeypatch.setattr("src.runner.LMStudioClient.from_config", lambda _: fake)
    run_benchmark(cfg, limit=1)
    assert fake.unload_all_calls >= 1


def test_runner_uses_loaded_instance_for_chat_requests(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)

    fake = FakeClient()
    monkeypatch.setattr("src.runner.LMStudioClient.from_config", lambda _: fake)
    run_benchmark(cfg, limit=1)
    assert fake.chat_model_ids
    assert set(fake.chat_model_ids) == {"inst1"}


def test_smoke_test_failure_skips_model(tmp_path, monkeypatch):
    class SmokeFailClient(FakeClient):
        def chat_completion(self, **kwargs):
            from src.lmstudio_client import LMStudioClientError

            if kwargs.get("max_tokens") == 16:
                raise LMStudioClientError("smoke failed")
            return super().chat_completion(**kwargs)

    path = build_config(tmp_path)
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", SmokeFailClient)
    run_dir = run_benchmark(cfg, limit=1)
    rows = (run_dir / "summary.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(rows) == 1  # header only
    smoke = json.loads((run_dir / "models" / "m1_q4" / "smoke_test.json").read_text(encoding="utf-8"))
    assert smoke["ok"] is False
