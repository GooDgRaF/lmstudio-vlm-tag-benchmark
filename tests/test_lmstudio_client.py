from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests

from src.config import load_config
from src.lmstudio_client import (
    LMStudioClient,
    LMStudioClientError,
    ResponseFormatUnsupportedError,
    build_rest_input_items,
    normalize_rest_chat_response,
)
from tests.helpers import build_config


@dataclass
class FakeResponse:
    status_code: int
    payload: dict | list | None = None
    text: str = ""

    def json(self):
        if self.payload is None:
            raise ValueError("no json")
        return self.payload


def test_list_models(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)

    def fake_request(method, url, timeout=None, **kwargs):
        assert method == "GET"
        assert url.endswith("/api/v1/models")
        return FakeResponse(200, {"data": [{"id": "m1"}]}, text='{"data":[{"id":"m1"}]}')

    monkeypatch.setattr(client.session, "request", fake_request)
    models = client.list_models()
    assert models[0]["id"] == "m1"


def test_load_includes_context_length(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    seen = {}

    def fake_request(method, url, timeout=None, **kwargs):
        seen["json"] = kwargs.get("json")
        return FakeResponse(200, {"data": {"id": "inst1", "load_config": {"context_length": 4096}}}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    loaded = client.load_model(cfg.models[0], cfg.load.as_payload())
    assert seen["json"]["load_config"]["context_length"] == 4096
    assert loaded.instance_id == "inst1"


def test_load_fallback_for_flat_body(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    calls = []

    def fake_request(method, url, timeout=None, **kwargs):
        calls.append(kwargs.get("json"))
        if len(calls) == 1:
            return FakeResponse(
                400,
                payload=None,
                text='{"error":{"message":"Unrecognized key(s) in object: \'identifier\', \'load_config\'"}}',
            )
        return FakeResponse(200, {"id": "inst2", "load_config": {"context_length": 4096}}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    loaded = client.load_model(cfg.models[0], cfg.load.as_payload())
    assert loaded.instance_id == "inst2"
    assert calls[0].get("load_config") is not None
    assert calls[1].get("context_length") == 4096


def test_load_fallback_for_model_not_found_uses_base_id(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    calls = []

    def fake_request(method, url, timeout=None, **kwargs):
        calls.append(kwargs.get("json"))
        if len(calls) == 1:
            return FakeResponse(
                404,
                payload=None,
                text='{"error":{"type":"model_not_found","message":"Model m1@q4 not found"}}',
            )
        return FakeResponse(200, {"id": "inst3", "load_config": {"context_length": 4096}}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    loaded = client.load_model(cfg.models[0], cfg.load.as_payload())
    assert loaded.instance_id == "inst3"
    assert calls[0]["model"] == "m1@q4"
    assert calls[1]["model"] == "m1"


def test_unload_uses_instance_id(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    seen = {}

    def fake_request(method, url, timeout=None, **kwargs):
        seen["json"] = kwargs.get("json")
        return FakeResponse(200, {"ok": True}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    client.unload_model("abc")
    assert "id" not in seen["json"]
    assert seen["json"]["instance_id"] == "abc"


def test_unload_does_not_fallback_on_unrecognized_instance_payload(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    calls = []

    def fake_request(method, url, timeout=None, **kwargs):
        calls.append(kwargs.get("json"))
        return FakeResponse(
            400,
            payload=None,
            text='{"error":{"message":"Unrecognized key(s) in object: \'id\'","code":"unrecognized_keys"}}',
        )

    monkeypatch.setattr(client.session, "request", fake_request)
    with pytest.raises(LMStudioClientError, match="Unrecognized key"):
        client.unload_model("abc", "m1@q4")
    assert calls == [{"instance_id": "abc"}]


def test_chat_completion_response_format_unsupported(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)

    def fake_request(method, url, timeout=None, **kwargs):
        return FakeResponse(400, payload=None, text="unsupported response_format json_schema")

    monkeypatch.setattr(client.session, "request", fake_request)
    with pytest.raises(ResponseFormatUnsupportedError):
        client.chat_completion(
            model_id="m1",
            messages=[{"role": "user", "content": "x"}],
            temperature=0,
            top_p=1,
            max_tokens=16,
            response_format={"type": "json_schema"},
        )


def test_connection_error_readable(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)

    def fake_request(method, url, timeout=None, **kwargs):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(client.session, "request", fake_request)
    with pytest.raises(LMStudioClientError, match="Failed to connect"):
        client.list_models()


def test_unload_all_loaded_models(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    calls = []

    def fake_request(method, url, timeout=None, **kwargs):
        if method == "GET":
            return FakeResponse(
                200,
                {"models": [{"selected_variant": "m1@q4", "key": "m1", "loaded_instances": [{"id": "inst-a"}]}]},
                text="ok",
            )
        calls.append(kwargs.get("json"))
        return FakeResponse(200, {"ok": True}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    unloaded = client.unload_all_loaded_models()
    assert len(unloaded) == 1
    assert calls[0]["instance_id"] == "inst-a"


def test_build_rest_input_items_shape():
    out = build_rest_input_items("system prompt", "user prompt", "data:image/jpeg;base64,abc")
    assert out == [
        {"type": "text", "content": "user prompt"},
        {"type": "image", "data_url": "data:image/jpeg;base64,abc"},
    ]


def test_chat_rest_posts_expected_body(tmp_path, monkeypatch):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    seen = {}

    def fake_request(method, url, timeout=None, **kwargs):
        seen["method"] = method
        seen["url"] = url
        seen["json"] = kwargs.get("json")
        return FakeResponse(200, {"ok": True}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    client.chat_rest(
        model_id="inst1",
        system_prompt="sys",
        input_items=build_rest_input_items("sys", "usr", "data:image/jpeg;base64,x"),
        temperature=0.0,
        top_p=1.0,
        max_output_tokens=64,
        reasoning="on",
    )
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/api/v1/chat")
    assert "messages" not in seen["json"]
    assert "response_format" not in seen["json"]
    assert seen["json"]["system_prompt"] == "sys"
    assert seen["json"]["input"][0] == {"type": "text", "content": "usr"}
    assert seen["json"]["input"][1]["type"] == "image"
    assert seen["json"]["max_output_tokens"] == 64
    assert seen["json"]["store"] is False
    assert seen["json"]["reasoning"] == "on"


@pytest.mark.parametrize("reasoning", ["default", "off"])
def test_chat_rest_reasoning_default_omit_or_off(tmp_path, monkeypatch, reasoning):
    cfg = load_config(build_config(tmp_path))
    client = LMStudioClient.from_config(cfg)
    seen = {}

    def fake_request(method, url, timeout=None, **kwargs):
        seen["json"] = kwargs.get("json")
        return FakeResponse(200, {"ok": True}, text="ok")

    monkeypatch.setattr(client.session, "request", fake_request)
    client.chat_rest(
        model_id="inst1",
        system_prompt="sys",
        input_items=build_rest_input_items("sys", "usr", "data:image/jpeg;base64,x"),
        temperature=0.0,
        top_p=1.0,
        max_output_tokens=64,
        reasoning=reasoning,
    )
    if reasoning == "default":
        assert "reasoning" not in seen["json"]
    else:
        assert seen["json"]["reasoning"] == "off"


def test_normalize_rest_message_and_reasoning_separated():
    payload = {
        "output": [
            {"type": "reasoning", "content": "chain"},
            {"type": "message", "content": "cat\ndog"},
        ],
        "stats": {"input_tokens": 10, "total_output_tokens": 5, "reasoning_output_tokens": 3},
    }
    out = normalize_rest_chat_response(payload, reasoning_requested="on", max_output_tokens=64)
    assert out["final_content"] == "cat\ndog"
    assert out["reasoning_content"] == "chain"
    assert out["raw_output"] == "cat\ndog"
    assert out["reasoning_content_used"] is False
    assert out["prompt_tokens"] == 10
    assert out["completion_tokens"] == 5
    assert out["reasoning_tokens"] == 3
    assert out["total_tokens"] == 15


def test_normalize_rest_reasoning_only_sets_no_final():
    payload = {"output": [{"type": "reasoning", "content": "think"}]}
    out = normalize_rest_chat_response(payload, reasoning_requested="on", max_output_tokens=64)
    assert out["final_content"] == ""
    assert out["no_final_answer"] is True
    assert out["normalization_error_type"] == "no_final_answer"


def test_normalize_rest_empty_and_bad_output():
    out1 = normalize_rest_chat_response({"output": []}, reasoning_requested="default", max_output_tokens=64)
    assert out1["normalization_error_type"] == "empty_rest_output"
    out2 = normalize_rest_chat_response({"x": 1}, reasoning_requested="default", max_output_tokens=64)
    assert out2["bad_rest_response"] is True
    assert out2["normalization_error_type"] == "bad_rest_response"


def test_normalize_rest_multiple_blocks_and_truncation():
    payload = {
        "output": [
            {"type": "message", "content": ""},
            {"type": "reasoning", "content": "a"},
            {"type": "reasoning", "content": "b"},
            {"type": "message", "content": "ok"},
        ],
        "stats": {"total_output_tokens": 64},
    }
    out = normalize_rest_chat_response(payload, reasoning_requested="off", max_output_tokens=64)
    assert out["final_content"] == "ok"
    assert out["reasoning_content"] == "a\nb"
    assert out["output_truncated"] is True
