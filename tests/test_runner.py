from __future__ import annotations

import json
from base64 import b64decode
import yaml

from PIL import Image

from src.config import load_config
from src.runner import _extract_text_from_completion, _to_data_url, run_benchmark
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
    assert (run_dir / "diagnostics.json").exists()
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "run_state.json").exists()
    assert (run_dir / "run_complete.json").exists()


def test_to_data_url_normalizes_non_png_jpeg_images(tmp_path):
    image_path = tmp_path / "image.bmp"
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(image_path)

    data_url = _to_data_url(str(image_path))

    assert data_url.startswith("data:image/jpeg;base64,")
    payload = data_url.split(",", 1)[1]
    assert b64decode(payload).startswith(b"\xff\xd8")


def test_to_data_url_normalizes_webp_images(tmp_path):
    image_path = tmp_path / "image.webp"
    Image.new("RGB", (2, 2), color=(0, 255, 0)).save(image_path)

    data_url = _to_data_url(str(image_path))

    assert data_url.startswith("data:image/jpeg;base64,")
    payload = data_url.split(",", 1)[1]
    assert b64decode(payload).startswith(b"\xff\xd8")


def test_runner_attempts_all_modes_for_image(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)
    run_dir = run_benchmark(cfg, limit=1)
    rows = (run_dir / "summary.csv").read_text(encoding="utf-8-sig").splitlines()
    # header + 6 mode rows
    assert len(rows) == 7


def test_run_with_explicit_run_id_and_manifest_reuse(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)

    run_dir = run_benchmark(cfg, limit=1, run_id="fixed")
    manifest1 = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    run_dir2 = run_benchmark(cfg, limit=1, run_id="fixed", force_lock=True)
    manifest2 = json.loads((run_dir2 / "run_manifest.json").read_text(encoding="utf-8"))
    assert run_dir == run_dir2
    assert manifest1["request_count"] == manifest2["request_count"]


def test_stale_lock_fails_without_force_lock(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)
    run_dir = run_benchmark(cfg, limit=1, run_id="locked")
    (run_dir / "run.lock").write_text("stale", encoding="utf-8")

    try:
        run_benchmark(cfg, limit=1, run_id="locked")
        assert False, "Expected lock error"
    except RuntimeError as exc:
        assert "Run is locked" in str(exc)


def test_force_lock_allows_continue(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)
    run_dir = run_benchmark(cfg, limit=1, run_id="locked-force")
    (run_dir / "run.lock").write_text("stale", encoding="utf-8")
    run_dir2 = run_benchmark(cfg, limit=1, run_id="locked-force", force_lock=True)
    assert run_dir2 == run_dir


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


def test_runner_writes_gpu_after_unload_and_model_diag(tmp_path, monkeypatch):
    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", FakeClient)
    run_dir = run_benchmark(cfg, limit=1)

    assert (run_dir / "models" / "m1_q4" / "gpu_after_unload.json").exists()
    diagnostics = json.loads((run_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["schema_version"] == 1
    assert diagnostics["models"][0]["model_label"] == "m1_q4"


def test_extract_uses_content_when_present():
    payload = {"choices": [{"message": {"content": "cat", "reasoning_content": "dog"}}]}
    out = _extract_text_from_completion(payload)
    assert out["raw_output"] == "cat"
    assert out["output_source"] == "content"
    assert out["content_empty"] is False
    assert out["reasoning_content_used"] is False


def test_extract_falls_back_to_reasoning_content():
    payload = {"choices": [{"message": {"content": "   ", "reasoning_content": "cat\ndog"}}]}
    out = _extract_text_from_completion(payload)
    assert out["raw_output"] == "cat\ndog"
    assert out["output_source"] == "reasoning_content"
    assert out["content_empty"] is True
    assert out["reasoning_content_used"] is True


def test_extract_empty_when_both_sources_are_empty():
    payload = {"choices": [{"message": {"content": "", "reasoning_content": "  "}}]}
    out = _extract_text_from_completion(payload)
    assert out["raw_output"] == ""
    assert out["output_source"] == "empty"
    assert out["content_empty"] is True
    assert out["reasoning_content_used"] is False


def test_reasoning_fallback_is_saved_in_normalized_and_diagnostics(tmp_path, monkeypatch):
    class ReasoningOnlyClient(FakeClient):
        def chat_completion(self, **kwargs):
            if kwargs.get("max_tokens") == 16:
                return {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            return {
                "choices": [
                    {
                        "message": {"content": "", "reasoning_content": "cat\ndog"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    path = build_config(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modes"] = ["en_free"]
    data["runtime"]["image_request_smoke_test"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = load_config(path)
    monkeypatch.setattr("src.runner.LMStudioClient", ReasoningOnlyClient)

    run_dir = run_benchmark(cfg, limit=1)
    normalized_path = next((run_dir / "normalized").glob("*.json"))
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert normalized["output_source"] == "reasoning_content"
    assert normalized["content_empty"] is True
    assert normalized["reasoning_content_used"] is True
    assert normalized["accepted_tags"] == ["cat", "dog"]

    diagnostics = json.loads((run_dir / "diagnostics.json").read_text(encoding="utf-8"))
    req = diagnostics["requests"][0]
    assert req["output_source"] == "reasoning_content"
    assert req["reasoning_content_used"] is True
