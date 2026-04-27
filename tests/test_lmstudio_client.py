from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests

from src.config import load_config
from src.lmstudio_client import LMStudioClient, LMStudioClientError, ResponseFormatUnsupportedError
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
    assert seen["json"]["instance_id"] == "abc"


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
