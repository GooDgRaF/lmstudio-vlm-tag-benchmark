from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

from src.config import BenchmarkConfig, ModelConfig
from src.diagnostics import classify_load_error, collect_gpu_memory, extract_usage_diagnostics
from src.image_loader import DiscoveredImage, discover_images
from src.lmstudio_client import (
    LMStudioClient,
    LMStudioClientError,
    ResponseFormatUnsupportedError,
)
from src.prompts import PROMPT_VERSION, build_prompt, strict_json_response_format
from src.storage import build_request_id, create_run_storage
from src.tag_pools import TagPools, load_tag_pools
from src.validator import normalize_model_output


def _to_data_url(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix == "jpg" else suffix
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


def _build_messages(prompt: str, image_path: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _to_data_url(image_path)}},
            ],
        }
    ]


def _extract_text_from_completion(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return str(content) if content is not None else ""


def _resume_decision(cfg: BenchmarkConfig, normalized_path: Path, mode: str) -> str:
    # Returns one of: "run", "skip", "retry".
    if not cfg.runtime.resume:
        return "run"
    if not normalized_path.exists():
        return "run"
    try:
        existing = json.loads(normalized_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "run"

    is_success = (
        existing.get("error_type") is None
        and bool(existing.get("parse_ok"))
        and (not mode.endswith("_pool") and not mode.endswith("_pool_explained") or bool(existing.get("pool_ok")))
    )
    if is_success and cfg.runtime.skip_existing_success:
        return "skip"
    if (not is_success) and cfg.runtime.retry_existing_errors:
        return "retry"
    if not is_success and not cfg.runtime.retry_existing_errors:
        return "skip"
    return "run"


def _response_format_payload(name: str, max_tags: int) -> dict[str, Any] | None:
    if name == "strict_json":
        return strict_json_response_format(max_tags)
    return None


def _run_smoke_test(
    client: LMStudioClient,
    cfg: BenchmarkConfig,
    model: ModelConfig,
    image: DiscoveredImage | None,
) -> dict[str, Any]:
    if image is None:
        return {"ok": False, "error": "No images found for smoke test"}
    prompt = "Return one short tag for this image."
    messages = _build_messages(prompt, image.image_path)
    try:
        completion = client.chat_completion(
            model_id=model.id,
            messages=messages,
            temperature=0.0,
            top_p=1.0,
            max_tokens=16,
            response_format=None,
        )
        text = _extract_text_from_completion(completion)
        return {"ok": True, "preview": text[:200]}
    except LMStudioClientError as exc:
        return {"ok": False, "error": str(exc)}


def run_benchmark(cfg: BenchmarkConfig, limit: int | None = None) -> Path:
    pools: TagPools = load_tag_pools(cfg)
    images = discover_images(cfg, limit=limit)
    run_id, storage = create_run_storage(cfg)
    storage.init_summary_csv()
    client = LMStudioClient.from_config(cfg)

    try:
        client.list_models()
    except LMStudioClientError as exc:
        raise RuntimeError(f"LM Studio availability check failed: {exc}") from exc

    for model in cfg.models:
        gpu_before = collect_gpu_memory(cfg)
        storage.save_model_metadata(model.label, "gpu_before_load.json", gpu_before)
        loaded = None
        try:
            loaded = client.load_model(model, cfg.load.as_payload())
            storage.save_model_metadata(
                model.label,
                "load.json",
                {
                    "id": loaded.id,
                    "instance_id": loaded.instance_id,
                    "requested_context_length": loaded.requested_context_length,
                    "actual_context_length": loaded.actual_context_length,
                    "load_config": loaded.load_config,
                },
            )
        except LMStudioClientError as exc:
            error_type = classify_load_error(str(exc))
            storage.append_error(f"{model.label}: {error_type}: {exc}")
            storage.save_model_metadata(
                model.label,
                "load.json",
                {"ok": False, "error_type": error_type, "error": str(exc)},
            )
            continue

        gpu_after = collect_gpu_memory(cfg)
        storage.save_model_metadata(model.label, "gpu_after_load.json", gpu_after)

        if cfg.runtime.image_request_smoke_test:
            smoke = _run_smoke_test(client, cfg, model, images[0] if images else None)
            storage.save_model_metadata(model.label, "smoke_test.json", smoke)
            if not smoke.get("ok"):
                if cfg.runtime.unload_model_after_run:
                    try:
                        client.unload_model(loaded.instance_id, model.id)
                    except LMStudioClientError:
                        pass
                continue

        for image in images:
            for mode in cfg.modes:
                prompt = build_prompt(cfg, mode, pools)
                request_id = build_request_id(
                    model_label=model.label,
                    image_id=image.image_id,
                    mode=mode,
                    prompt_version=prompt.prompt_version,
                    response_format_requested=prompt.response_format_requested,
                )
                normalized_path = storage.normalized_path(request_id)
                decision = _resume_decision(cfg, normalized_path, mode)
                if decision == "skip":
                    storage.append_error(f"SKIP {request_id}: resume")
                    continue

                response_format_payload = None
                if cfg.validation.use_response_format:
                    response_format_payload = _response_format_payload(
                        prompt.response_format_requested, cfg.limits.max_tags
                    )

                start = time.perf_counter()
                completion_payload: dict[str, Any]
                response_format_used = prompt.response_format_requested
                retried_without_response_format = False
                try:
                    completion_payload = client.chat_completion(
                        model_id=model.id,
                        messages=_build_messages(prompt.prompt, image.image_path),
                        temperature=cfg.generation.temperature,
                        top_p=cfg.generation.top_p,
                        max_tokens=cfg.generation.max_tokens,
                        response_format=response_format_payload,
                    )
                except ResponseFormatUnsupportedError:
                    if cfg.validation.allow_line_fallback:
                        retried_without_response_format = True
                        response_format_used = "line_tags" if not mode.endswith("_pool_explained") else "line_ids"
                        completion_payload = client.chat_completion(
                            model_id=model.id,
                            messages=_build_messages(prompt.prompt, image.image_path),
                            temperature=cfg.generation.temperature,
                            top_p=cfg.generation.top_p,
                            max_tokens=cfg.generation.max_tokens,
                            response_format=None,
                        )
                    else:
                        raise
                except LMStudioClientError as exc:
                    latency = round(time.perf_counter() - start, 4)
                    normalized = {
                        "prompt_version": prompt.prompt_version,
                        "raw_output": "",
                        "response_format_requested": prompt.response_format_requested,
                        "response_format_used": response_format_used,
                        "raw_tags": [],
                        "raw_ids": [],
                        "accepted_tags": [],
                        "accepted_ids": [],
                        "rejected_tags": [],
                        "rejected_ids": [],
                        "parse_ok": False,
                        "schema_ok": False,
                        "json_extracted": False,
                        "line_fallback_used": False,
                        "pool_ok": False if mode.endswith("_pool") else True,
                        "pool_violations": 0,
                        "error_type": "request_error",
                        "error": str(exc),
                        "request_id": request_id,
                        "run_id": run_id,
                        "model_id": model.id,
                        "base_model_id": model.base_model_id,
                        "model_label": model.label,
                        "image_id": image.image_id,
                        "image_path": image.image_path,
                        "image_rel_path": image.image_rel_path,
                        "mode": mode,
                        "latency_sec": latency,
                    }
                    storage.save_normalized(request_id, normalized)
                    storage.save_raw_output(
                        request_id,
                        {"request_id": request_id, "error": str(exc), "payload": None},
                    )
                    storage.append_summary_row(
                        {
                            **normalized,
                            "params": model.params,
                            "quant": model.quant,
                            "quant_bits": model.quant_bits,
                            "tag_count": 0,
                            "prompt_tokens": None,
                            "completion_tokens": None,
                            "total_tokens": None,
                            "requested_context_length": cfg.load.context_length,
                            "actual_context_length": loaded.actual_context_length,
                            "context_near_limit": False,
                            "context_overflow": False,
                            "output_truncated": False,
                            "gpu_memory_before_mb": gpu_before.get("memory_used_mb"),
                            "gpu_memory_after_mb": gpu_after.get("memory_used_mb"),
                        }
                    )
                    continue

                latency = round(time.perf_counter() - start, 4)
                raw_text = _extract_text_from_completion(completion_payload)
                normalized = normalize_model_output(
                    raw_output=raw_text,
                    mode=mode,
                    requested_response_format=response_format_used,
                    pools=pools,
                    max_tags=cfg.limits.max_tags,
                    allow_json_extraction=cfg.validation.allow_json_extraction,
                    allow_line_fallback=cfg.validation.allow_line_fallback,
                    drop_tags_not_in_pool=cfg.validation.drop_tags_not_in_pool,
                    prompt_version=PROMPT_VERSION,
                )
                if retried_without_response_format:
                    normalized["line_fallback_used"] = True

                usage_diag = extract_usage_diagnostics(
                    completion_payload,
                    actual_context_length=loaded.actual_context_length or cfg.load.context_length,
                    warning_ratio=cfg.diagnostics.context.warning_ratio,
                    error_ratio=cfg.diagnostics.context.error_ratio,
                )

                normalized.update(
                    {
                        "request_id": request_id,
                        "run_id": run_id,
                        "model_id": model.id,
                        "base_model_id": model.base_model_id,
                        "model_label": model.label,
                        "image_id": image.image_id,
                        "image_path": image.image_path,
                        "image_rel_path": image.image_rel_path,
                        "mode": mode,
                        "latency_sec": latency,
                        **usage_diag,
                        "requested_context_length": cfg.load.context_length,
                        "actual_context_length": loaded.actual_context_length,
                    }
                )

                storage.save_raw_output(
                    request_id,
                    {
                        "request_id": request_id,
                        "response": completion_payload,
                        "raw_output": raw_text,
                    },
                )
                storage.save_normalized(request_id, normalized)

                if not storage.has_summary_row(request_id):
                    storage.append_summary_row(
                        {
                            "run_id": run_id,
                            "request_id": request_id,
                            "model_id": model.id,
                            "base_model_id": model.base_model_id,
                            "model_label": model.label,
                            "params": model.params,
                            "quant": model.quant,
                            "quant_bits": model.quant_bits,
                            "image_id": image.image_id,
                            "image_path": image.image_path,
                            "image_rel_path": image.image_rel_path,
                            "mode": mode,
                            "prompt_version": normalized["prompt_version"],
                            "response_format_requested": normalized["response_format_requested"],
                            "response_format_used": normalized["response_format_used"],
                            "accepted_tags": normalized["accepted_tags"],
                            "accepted_ids": normalized["accepted_ids"],
                            "rejected_tags": normalized["rejected_tags"],
                            "rejected_ids": normalized["rejected_ids"],
                            "tag_count": len(normalized["accepted_tags"]),
                            "pool_violations": normalized["pool_violations"],
                            "parse_ok": normalized["parse_ok"],
                            "schema_ok": normalized["schema_ok"],
                            "json_extracted": normalized["json_extracted"],
                            "line_fallback_used": normalized["line_fallback_used"],
                            "pool_ok": normalized["pool_ok"],
                            "latency_sec": latency,
                            "prompt_tokens": normalized.get("prompt_tokens"),
                            "completion_tokens": normalized.get("completion_tokens"),
                            "total_tokens": normalized.get("total_tokens"),
                            "requested_context_length": cfg.load.context_length,
                            "actual_context_length": loaded.actual_context_length,
                            "context_near_limit": normalized.get("context_near_limit"),
                            "context_overflow": normalized.get("context_overflow"),
                            "output_truncated": normalized.get("output_truncated"),
                            "gpu_memory_before_mb": gpu_before.get("memory_used_mb"),
                            "gpu_memory_after_mb": gpu_after.get("memory_used_mb"),
                            "error_type": normalized["error_type"],
                            "error": normalized["error"],
                        }
                    )

        if cfg.runtime.unload_model_after_run:
            try:
                client.unload_model(loaded.instance_id, model.id)
            except LMStudioClientError as exc:
                storage.append_error(f"{model.label}: unload_failed: {exc}")

    return storage.run_dir

