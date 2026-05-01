from __future__ import annotations

import json
import yaml

from src.config import load_config
from src.runner import run_benchmark
from tests.helpers import build_config


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.chat_rest_calls = []
        self.chat_completion_calls = 0

    @classmethod
    def from_config(cls, cfg):
        return cls()

    def list_models(self):
        return [{"id": "m1@q4"}]

    def unload_all_loaded_models(self):
        return []

    def load_model(self, model, load_config):
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
        return {"ok": True}

    def chat_completion(self, **kwargs):
        self.chat_completion_calls += 1
        return {}

    def chat_rest(self, **kwargs):
        self.chat_rest_calls.append(kwargs)
        return {
            "output": [{"type": "message", "content": "cat"}],
            "stats": {"input_tokens": 10, "total_output_tokens": 5, "reasoning_output_tokens": 0},
        }


def test_runner_uses_rest_not_chat_completion(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)

    fake = FakeClient()
    monkeypatch.setattr("src.runner.LMStudioClient.from_config", lambda _: fake)
    run_benchmark(cfg, limit=1)
    assert fake.chat_rest_calls
    assert fake.chat_completion_calls == 0
    assert fake.chat_rest_calls[0]["model_id"] == "inst1"


def test_runner_passes_reasoning_and_rest_input_items(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["models"][0]["reasoning"] = "off"
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)

    fake = FakeClient()
    monkeypatch.setattr("src.runner.LMStudioClient.from_config", lambda _: fake)
    run_benchmark(cfg, limit=1)
    call = fake.chat_rest_calls[0]
    assert call["reasoning"] == "off"
    assert "Answer format: one tag per line" in call["system_prompt"]
    assert call["input_items"][0]["type"] == "image"


def test_reasoning_not_parsed_when_no_final_answer(tmp_path, monkeypatch):
    class ReasoningOnlyClient(FakeClient):
        def chat_rest(self, **kwargs):
            self.chat_rest_calls.append(kwargs)
            return {
                "output": [{"type": "reasoning", "content": "cat\ndog"}],
                "stats": {"input_tokens": 10, "total_output_tokens": 5, "reasoning_output_tokens": 5},
            }

    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", ReasoningOnlyClient)
    run_dir = run_benchmark(cfg, limit=1)

    normalized = json.loads(next((run_dir / "normalized").glob("*.json")).read_text(encoding="utf-8"))
    assert normalized["no_final_answer"] is True
    assert normalized["error_type"] == "no_final_answer"
    assert normalized["accepted_tags"] == []
    assert normalized["raw_output"] == ""
    assert normalized["reasoning_content_used"] is False


def test_bad_rest_response_mapped_to_error(tmp_path, monkeypatch):
    class BadPayloadClient(FakeClient):
        def chat_rest(self, **kwargs):
            self.chat_rest_calls.append(kwargs)
            return {"output": {"broken": True}}

    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", BadPayloadClient)
    run_dir = run_benchmark(cfg, limit=1)
    normalized = json.loads(next((run_dir / "normalized").glob("*.json")).read_text(encoding="utf-8"))
    assert normalized["error_type"] == "bad_rest_response"


def test_smoke_test_uses_rest(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = True
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    fake = FakeClient()
    monkeypatch.setattr("src.runner.LMStudioClient.from_config", lambda _: fake)
    run_dir = run_benchmark(cfg, limit=1)
    smoke = json.loads((run_dir / "models" / "m1_q4" / "smoke_test.json").read_text(encoding="utf-8"))
    assert smoke["ok"] is True
    assert fake.chat_rest_calls


def test_smoke_fails_when_only_reasoning_present(tmp_path, monkeypatch):
    class SmokeReasoningOnlyClient(FakeClient):
        def chat_rest(self, **kwargs):
            self.chat_rest_calls.append(kwargs)
            return {"output": [{"type": "reasoning", "content": "thinking"}]}

    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = True
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", SmokeReasoningOnlyClient)
    run_dir = run_benchmark(cfg, limit=1)
    smoke = json.loads((run_dir / "models" / "m1_q4" / "smoke_test.json").read_text(encoding="utf-8"))
    assert smoke["ok"] is False
    assert smoke["no_final_answer"] is True


def test_output_truncated_survives_runner_merge(tmp_path, monkeypatch):
    class TruncatedClient(FakeClient):
        def chat_rest(self, **kwargs):
            self.chat_rest_calls.append(kwargs)
            return {
                "output": [{"type": "message", "content": "cat"}],
                "stats": {"input_tokens": 10, "total_output_tokens": kwargs["max_output_tokens"]},
            }

    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    data["generation"]["max_tokens"] = 64
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", TruncatedClient)
    run_dir = run_benchmark(cfg, limit=1)
    normalized = json.loads(next((run_dir / "normalized").glob("*.json")).read_text(encoding="utf-8"))
    assert normalized["output_truncated"] is True
