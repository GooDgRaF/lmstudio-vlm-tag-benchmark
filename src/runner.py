from __future__ import annotations

import base64
import csv
import json
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from src.config import BenchmarkConfig
from src.diagnostics import (
    build_pool_diagnostics,
    classify_load_error,
    collect_gpu_memory,
    detect_git_commit,
    extract_usage_diagnostics,
    now_timestamp,
    shorten_error,
    summarize_model_requests,
)
from src.image_loader import DiscoveredImage, discover_images
from src.lmstudio_client import (
    LMStudioClient,
    LMStudioClientError,
    build_rest_input_items,
    normalize_rest_chat_response,
)
from src.prompts import PROMPT_VERSION, build_prompt
from src.report import build_diagnostics_report, build_report
from src.storage import build_request_id, create_run_storage
from src.tag_pools import TagPools, load_tag_pools
from src.validator import normalize_model_output


def _to_data_url(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".") or "jpeg"
    if suffix in {"jpg", "jpeg"}:
        encoded = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    if suffix == "png":
        encoded = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    with Image.open(p) as image:
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=95)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _pool_hash_for_mode(mode: str, pool_hashes: dict[str, str]) -> str | None:
    if mode == "ru_pool":
        return pool_hashes.get("ru_plain")
    if mode == "en_pool":
        return pool_hashes.get("en_plain")
    if mode == "ru_pool_explained":
        return pool_hashes.get("ru_explained")
    if mode == "en_pool_explained":
        return pool_hashes.get("en_explained")
    return None


def _status_decision(cfg: BenchmarkConfig, status_payload: dict[str, Any] | None) -> str:
    if cfg.runtime.result_mode == "overwrite":
        return "run"
    if cfg.runtime.result_mode == "accumulate":
        return "run"
    if not cfg.runtime.resume:
        return "run"
    if not status_payload or not isinstance(status_payload, dict):
        return "run"

    status = str(status_payload.get("status") or "").strip()
    if status == "success":
        return "skip"
    if status == "failed":
        return "run" if cfg.runtime.retry_failed else "skip"
    return "run"


def _run_smoke_test(
    client: LMStudioClient,
    runtime_model_id: str,
    reasoning_requested: str,
    max_output_tokens: int,
    image: DiscoveredImage | None,
) -> dict[str, Any]:
    if image is None:
        return {"ok": False, "error": "No images found for smoke test"}
    system_prompt = "Return one short tag for this image."
    input_items = build_rest_input_items(system_prompt, "", _to_data_url(image.image_path))
    try:
        completion = client.chat_rest(
            model_id=runtime_model_id,
            system_prompt=system_prompt,
            input_items=input_items,
            temperature=0.0,
            top_p=1.0,
            max_output_tokens=max_output_tokens,
            reasoning=reasoning_requested,
        )
        normalized = normalize_rest_chat_response(
            completion,
            reasoning_requested=reasoning_requested,
            max_output_tokens=max_output_tokens,
        )
        if normalized.get("no_final_answer"):
            return {
                "ok": False,
                "error": "REST smoke response did not contain a non-empty final message",
                "preview": "",
                "output_source": normalized["output_source"],
                "no_final_answer": True,
                "reasoning_content_present": normalized["reasoning_content_present"],
                "reasoning_content_length": normalized["reasoning_content_length"],
            }
        return {
            "ok": True,
            "preview": normalized["final_content"][:200],
            "output_source": normalized["output_source"],
            "no_final_answer": False,
            "reasoning_content_present": normalized["reasoning_content_present"],
            "reasoning_content_length": normalized["reasoning_content_length"],
        }
    except LMStudioClientError as exc:
        return {"ok": False, "error": str(exc)}


def _build_manifest_requests(
    cfg: BenchmarkConfig,
    pools: TagPools,
    images: list[DiscoveredImage],
    pool_hashes: dict[str, str],
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for model in cfg.models:
        for image in images:
            for mode in cfg.modes:
                prompt = build_prompt(cfg, mode, pools)
                pool_hash = _pool_hash_for_mode(mode, pool_hashes)
                request_id = build_request_id(
                    model_id=model.id,
                    model_label=model.label,
                    image_id=image.image_id,
                    mode=mode,
                    prompt_version=prompt.prompt_version,
                    response_format_requested=prompt.response_format_requested,
                    transport="rest",
                    reasoning_requested=model.reasoning,
                    pool_hash=pool_hash,
                )
                requests.append(
                    {
                        "request_id": request_id,
                        "model_label": model.label,
                        "model_id": model.id,
                        "base_model_id": model.base_model_id,
                        "image_id": image.image_id,
                        "image_path": image.image_path,
                        "image_rel_path": image.image_rel_path,
                        "mode": mode,
                        "prompt_version": prompt.prompt_version,
                        "response_format_requested": prompt.response_format_requested,
                        "transport": "rest",
                        "reasoning_requested": model.reasoning,
                        "pool_hash": pool_hash,
                    }
                )
    return requests


def _manifest_for_run(cfg: BenchmarkConfig, run_id: str, pool_hashes: dict[str, str], requests: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now_timestamp(),
        "config_path": str(cfg.config_path),
        "result_mode": cfg.runtime.result_mode,
        "request_count": len(requests),
        "pool_hashes": pool_hashes,
        "requests": [
            {
                "request_id": item["request_id"],
                "model_label": item["model_label"],
                "model_id": item["model_id"],
                "image_id": item["image_id"],
                "image_rel_path": item["image_rel_path"],
                "mode": item["mode"],
                "prompt_version": item["prompt_version"],
                "response_format_requested": item["response_format_requested"],
                "transport": item.get("transport", "rest"),
                "reasoning_requested": item.get("reasoning_requested", "default"),
            }
            for item in requests
        ],
    }


def _request_status_payload(
    *,
    request: dict[str, Any],
    status: str,
    started_at: str,
    finished_at: str | None,
    duration_sec: float | None,
    error_type: str | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "request_id": request["request_id"],
        "status": status,
        "attempt": 1,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": duration_sec,
        "model_label": request["model_label"],
        "image_id": request["image_id"],
        "mode": request["mode"],
        "error_type": error_type,
        "error": error,
    }


def run_benchmark(
    cfg: BenchmarkConfig,
    limit: int | None = None,
    *,
    run_id: str | None = None,
    force_lock: bool = False,
) -> Path:
    is_accumulate = cfg.runtime.result_mode == "accumulate"
    pools = load_tag_pools(cfg)
    images = discover_images(cfg, limit=limit)
    run_id, storage = create_run_storage(cfg, run_id=run_id)
    storage.acquire_lock(force_lock=force_lock)
    storage.init_summary_csv()

    started_at = datetime.now()
    started_at_str = now_timestamp()
    requests_diag: list[dict[str, Any]] = []
    models_diag: list[dict[str, Any]] = []

    try:
        pool_diag = build_pool_diagnostics(cfg, pools)
        pool_hashes = {k: str((v or {}).get("sha256") or "") for k, v in pool_diag.items()}

        expected_requests = _build_manifest_requests(cfg, pools, images, pool_hashes)
        existing_manifest = storage.load_manifest()
        if existing_manifest is None:
            manifest = _manifest_for_run(cfg, run_id, pool_hashes, expected_requests)
            storage.save_manifest(manifest)
        else:
            manifest = existing_manifest
            if not isinstance(manifest.get("requests"), list):
                raise RuntimeError("Invalid run_manifest.json: missing requests list")

        manifest_requests = manifest.get("requests") or []
        request_count = len(manifest_requests)
        completed_count = 0
        failed_count = 0
        skipped_count = 0

        def save_state(status: str, current: dict[str, Any] | None = None) -> None:
            state_payload = {
                "schema_version": 1,
                "run_id": run_id,
                "status": status,
                "expected": request_count,
                "completed": completed_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "remaining": max(request_count - completed_count - skipped_count, 0),
                "current_model": current.get("model_label") if current else None,
                "current_image": current.get("image_id") if current else None,
                "current_mode": current.get("mode") if current else None,
                "updated_at": now_timestamp(),
            }
            storage.save_run_state(state_payload)

        save_state("running")

        req_map: dict[str, dict[str, Any]] = {item["request_id"]: item for item in expected_requests}
        for req in expected_requests:
            storage.save_request_descriptor(req["request_id"], req)

        client = LMStudioClient.from_config(cfg)
        try:
            client.list_models()
        except LMStudioClientError as exc:
            raise RuntimeError(f"LM Studio availability check failed: {exc}") from exc

        model_to_requests: dict[str, list[dict[str, Any]]] = {}
        for item in manifest_requests:
            request_id = item.get("request_id")
            if not isinstance(request_id, str):
                continue
            req = req_map.get(request_id)
            if req is None:
                continue
            model_to_requests.setdefault(req["model_label"], []).append(req)

        model_by_label = {m.label: m for m in cfg.models}
        for model_label in [m.label for m in cfg.models]:
            model = model_by_label[model_label]
            model_requests = model_to_requests.get(model_label, [])
            if not model_requests:
                continue

            model_diag: dict[str, Any] = {
                "model_label": model.label,
                "model_id": model.id,
                "base_model_id": model.base_model_id,
                "params": model.params,
                "quant": model.quant,
                "quant_bits": model.quant_bits,
                "load_started_at": now_timestamp(),
                "load_finished_at": None,
                "load_duration_sec": None,
                "load_ok": False,
                "load_error_type": None,
                "load_error": None,
                "instance_id": None,
                "requested_context_length": cfg.load.context_length,
                "actual_context_length": None,
                "smoke_test_ok": None,
                "smoke_test_error": None,
                "gpu_before_load": {},
                "gpu_after_load": {},
                "gpu_after_unload": {},
                "unload_ok": None,
                "unload_error": None,
            }

            unloaded = client.unload_all_loaded_models()
            if unloaded:
                storage.append_error(f"{model.label}: pre_load_unload: removed {len(unloaded)} loaded instance(s)")

            gpu_before = collect_gpu_memory(cfg)
            storage.save_model_metadata(model.label, "gpu_before_load.json", gpu_before)
            model_diag["gpu_before_load"] = gpu_before

            loaded = None
            load_started_perf = time.perf_counter()
            try:
                loaded = client.load_model(model, cfg.load.as_payload())
                model_diag["load_ok"] = True
                model_diag["instance_id"] = loaded.instance_id
                model_diag["actual_context_length"] = loaded.actual_context_length
                model_diag["requested_context_length"] = loaded.requested_context_length
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
                model_diag["load_error_type"] = error_type
                model_diag["load_error"] = shorten_error(str(exc))
                storage.save_model_metadata(model.label, "load.json", {"ok": False, "error_type": error_type, "error": str(exc)})

                for req in model_requests:
                    decision = _status_decision(cfg, storage.read_request_status(req["request_id"]))
                    if decision == "skip":
                        skipped_count += 1
                        continue
                    attempt_no = storage.next_attempt_number(req["request_id"]) if is_accumulate else 1
                    req_started = now_timestamp()
                    fail_status = _request_status_payload(
                        request=req,
                        status="failed",
                        started_at=req_started,
                        finished_at=now_timestamp(),
                        duration_sec=0.0,
                        error_type=error_type,
                        error=str(exc),
                    )
                    fail_status["attempt"] = attempt_no
                    if is_accumulate:
                        storage.save_attempt_status(req["request_id"], attempt_no, fail_status)
                        storage.save_attempt_raw(req["request_id"], attempt_no, {"request_id": req["request_id"], "error": str(exc), "payload": None})
                    else:
                        storage.save_request_status(req["request_id"], fail_status)
                        storage.save_request_raw(req["request_id"], {"request_id": req["request_id"], "error": str(exc), "payload": None})

                    normalized_payload = (
                        req["request_id"],
                        {
                            "prompt_version": req["prompt_version"],
                            "raw_output": "",
                            "response_format_requested": req["response_format_requested"],
                            "response_format_used": req["response_format_requested"],
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
                            "pool_ok": False if req["mode"].endswith("_pool") else True,
                            "pool_violations": 0,
                            "error_type": error_type,
                            "error": str(exc),
                            "request_id": req["request_id"],
                            "run_id": run_id,
                            "model_id": model.id,
                            "base_model_id": model.base_model_id,
                            "model_label": model.label,
                            "image_id": req["image_id"],
                            "image_path": req["image_path"],
                            "image_rel_path": req["image_rel_path"],
                            "mode": req["mode"],
                            "latency_sec": 0.0,
                        },
                    )
                    if is_accumulate:
                        storage.save_attempt_normalized(req["request_id"], attempt_no, normalized_payload[1])
                        storage.save_attempt_diagnostics(
                            req["request_id"],
                            attempt_no,
                            {"request_id": req["request_id"], "status": "failed", "error_type": error_type, "error": str(exc)},
                        )
                    else:
                        storage.save_request_normalized(*normalized_payload)
                        storage.save_request_diagnostics(
                            req["request_id"],
                            {"request_id": req["request_id"], "status": "failed", "error_type": error_type, "error": str(exc)},
                        )
                    failed_count += 1
                    completed_count += 1
                    save_state("running", req)

                model_diag["load_finished_at"] = now_timestamp()
                model_diag["load_duration_sec"] = round(time.perf_counter() - load_started_perf, 4)
                model_diag.update(summarize_model_requests([]))
                models_diag.append(model_diag)
                continue

            model_diag["load_finished_at"] = now_timestamp()
            model_diag["load_duration_sec"] = round(time.perf_counter() - load_started_perf, 4)
            gpu_after = collect_gpu_memory(cfg)
            storage.save_model_metadata(model.label, "gpu_after_load.json", gpu_after)
            model_diag["gpu_after_load"] = gpu_after

            if cfg.runtime.image_request_smoke_test:
                smoke = _run_smoke_test(
                    client,
                    loaded.instance_id,
                    model.reasoning,
                    max(64, cfg.generation.max_tokens),
                    images[0] if images else None,
                )
                storage.save_model_metadata(model.label, "smoke_test.json", smoke)
                model_diag["smoke_test_ok"] = bool(smoke.get("ok"))
                model_diag["smoke_test_error"] = shorten_error(smoke.get("error"))
                if not smoke.get("ok"):
                    model_diag.update(summarize_model_requests([]))
                    models_diag.append(model_diag)
                    continue

            for req in model_requests:
                save_state("running", req)
                decision = _status_decision(cfg, storage.read_request_status(req["request_id"]))
                if decision == "skip":
                    if is_accumulate:
                        skip_status = _request_status_payload(
                            request=req,
                            status="skipped",
                            started_at=now_timestamp(),
                            finished_at=now_timestamp(),
                            duration_sec=0.0,
                            error_type=None,
                            error=None,
                        )
                        attempt_no = storage.next_attempt_number(req["request_id"])
                        skip_status["attempt"] = attempt_no
                        storage.save_attempt_status(req["request_id"], attempt_no, skip_status)
                    skipped_count += 1
                    continue

                mode = req["mode"]
                image_path = req["image_path"]
                prompt = build_prompt(cfg, mode, pools)
                attempt_no = storage.next_attempt_number(req["request_id"]) if is_accumulate else 1

                req_start_ts = now_timestamp()
                running_status = _request_status_payload(
                    request=req,
                    status="running",
                    started_at=req_start_ts,
                    finished_at=None,
                    duration_sec=None,
                    error_type=None,
                    error=None,
                )
                running_status["attempt"] = attempt_no
                if is_accumulate:
                    storage.save_attempt_status(req["request_id"], attempt_no, running_status)
                else:
                    storage.save_request_status(req["request_id"], running_status)

                start = time.perf_counter()
                response_format_used = prompt.response_format_requested
                completion_payload: dict[str, Any]

                try:
                    completion_payload = client.chat_rest(
                        model_id=loaded.instance_id,
                        system_prompt=prompt.system_prompt,
                        input_items=build_rest_input_items(
                            prompt.system_prompt,
                            prompt.user_prompt,
                            _to_data_url(image_path),
                        ),
                        temperature=cfg.generation.temperature,
                        top_p=cfg.generation.top_p,
                        max_output_tokens=cfg.generation.max_tokens,
                        reasoning=model.reasoning,
                    )
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
                        "transport": "rest",
                        "reasoning_requested": model.reasoning,
                        "final_content": "",
                        "reasoning_content": "",
                        "output_source": "empty",
                        "final_content_empty": True,
                        "final_content_length": 0,
                        "reasoning_content_present": False,
                        "reasoning_content_length": 0,
                        "reasoning_content_used": False,
                        "content_empty": True,
                        "content_length": 0,
                        "no_final_answer": False,
                        "normalization_error_type": None,
                        "reasoning_tokens": None,
                        "tokens_per_second": None,
                        "time_to_first_token_seconds": None,
                        "error_type": "request_error",
                        "error": str(exc),
                        "request_id": req["request_id"],
                        "run_id": run_id,
                        "model_id": model.id,
                        "base_model_id": model.base_model_id,
                        "model_label": model.label,
                        "image_id": req["image_id"],
                        "image_path": req["image_path"],
                        "image_rel_path": req["image_rel_path"],
                        "mode": mode,
                        "latency_sec": latency,
                    }
                    raw_fail_payload = {
                        "request_id": req["request_id"],
                        "transport": "rest",
                        "reasoning_requested": model.reasoning,
                        "error": str(exc),
                        "response": None,
                        "final_content": "",
                        "reasoning_content": "",
                    }
                    if is_accumulate:
                        storage.save_attempt_raw(req["request_id"], attempt_no, raw_fail_payload)
                        storage.save_attempt_normalized(req["request_id"], attempt_no, normalized)
                        storage.save_attempt_diagnostics(
                            req["request_id"],
                            attempt_no,
                            {
                                "request_id": req["request_id"],
                                "status": "failed",
                                "transport": "rest",
                                "reasoning_requested": model.reasoning,
                                "error_type": "request_error",
                                "error": str(exc),
                            },
                        )
                    else:
                        storage.save_request_raw(req["request_id"], raw_fail_payload)
                        storage.save_request_normalized(req["request_id"], normalized)
                        storage.save_request_diagnostics(
                            req["request_id"],
                            {
                                "request_id": req["request_id"],
                                "status": "failed",
                                "transport": "rest",
                                "reasoning_requested": model.reasoning,
                                "error_type": "request_error",
                                "error": str(exc),
                            },
                        )
                        storage.save_raw_output(req["request_id"], raw_fail_payload)
                        storage.save_normalized(req["request_id"], normalized)

                    failed_status = _request_status_payload(
                        request=req,
                        status="failed",
                        started_at=req_start_ts,
                        finished_at=now_timestamp(),
                        duration_sec=latency,
                        error_type="request_error",
                        error=str(exc),
                    )
                    failed_status["attempt"] = attempt_no
                    if is_accumulate:
                        storage.save_attempt_status(req["request_id"], attempt_no, failed_status)
                    else:
                        storage.save_request_status(req["request_id"], failed_status)
                    failed_count += 1
                    completed_count += 1
                    continue

                latency = round(time.perf_counter() - start, 4)
                rest_meta = normalize_rest_chat_response(
                    completion_payload,
                    reasoning_requested=model.reasoning,
                    max_output_tokens=cfg.generation.max_tokens,
                )
                raw_text = str(rest_meta["final_content"])

                normalized = normalize_model_output(
                    raw_output=raw_text,
                    mode=mode,
                    requested_response_format=response_format_used,
                    pools=pools,
                    allow_json_extraction=cfg.validation.allow_json_extraction,
                    allow_line_fallback=cfg.validation.allow_line_fallback,
                    drop_tags_not_in_pool=cfg.validation.drop_tags_not_in_pool,
                    prompt_version=PROMPT_VERSION,
                )
                if rest_meta.get("no_final_answer"):
                    normalized["parse_ok"] = False
                    normalized["schema_ok"] = False
                    normalized["accepted_tags"] = []
                    normalized["accepted_ids"] = []
                    normalized["rejected_tags"] = []
                    normalized["rejected_ids"] = []
                    normalized["pool_violations"] = 0
                    normalized["pool_ok"] = False if mode.endswith("_pool") else True
                    if rest_meta.get("normalization_error_type") == "bad_rest_response":
                        normalized["error_type"] = "bad_rest_response"
                        normalized["error"] = "REST response output field is missing or malformed"
                    elif rest_meta.get("normalization_error_type") == "empty_rest_output":
                        normalized["error_type"] = "empty_rest_output"
                        normalized["error"] = "REST response output list is empty"
                    else:
                        normalized["error_type"] = "no_final_answer"
                        normalized["error"] = "REST response did not contain a non-empty final message"

                usage_diag = extract_usage_diagnostics(
                    completion_payload,
                    actual_context_length=loaded.actual_context_length or cfg.load.context_length,
                    warning_ratio=cfg.diagnostics.context.warning_ratio,
                    error_ratio=cfg.diagnostics.context.error_ratio,
                )

                normalized.update(
                    {
                        "request_id": req["request_id"],
                        "run_id": run_id,
                        "model_id": model.id,
                        "base_model_id": model.base_model_id,
                        "model_label": model.label,
                        "image_id": req["image_id"],
                        "image_path": req["image_path"],
                        "image_rel_path": req["image_rel_path"],
                        "mode": mode,
                        "latency_sec": latency,
                        "transport": "rest",
                        "reasoning_requested": model.reasoning,
                        **usage_diag,
                        **rest_meta,
                        "requested_context_length": cfg.load.context_length,
                        "actual_context_length": loaded.actual_context_length,
                    }
                )

                request_diag = {
                    "request_id": req["request_id"],
                    "model_label": model.label,
                    "model_id": model.id,
                    "image_id": req["image_id"],
                    "image_rel_path": req["image_rel_path"],
                    "mode": mode,
                    "transport": "rest",
                    "reasoning_requested": model.reasoning,
                    "prompt_version": normalized["prompt_version"],
                    "response_format_requested": normalized["response_format_requested"],
                    "response_format_used": normalized["response_format_used"],
                    "latency_sec": latency,
                    "retry_count": 0,
                    "retried_without_response_format": False,
                    "parse_ok": bool(normalized["parse_ok"]),
                    "schema_ok": bool(normalized["schema_ok"]),
                    "pool_ok": bool(normalized["pool_ok"]),
                    "pool_violations": int(normalized["pool_violations"]),
                    "error_type": normalized["error_type"],
                    "error": shorten_error(normalized["error"]),
                    "finish_reason": normalized.get("finish_reason"),
                    "prompt_tokens": normalized.get("prompt_tokens"),
                    "completion_tokens": normalized.get("completion_tokens"),
                    "total_tokens": normalized.get("total_tokens"),
                    "requested_context_length": cfg.load.context_length,
                    "actual_context_length": loaded.actual_context_length,
                    "context_near_limit": bool(normalized.get("context_near_limit")),
                    "context_overflow": bool(normalized.get("context_overflow")),
                    "output_truncated": bool(normalized.get("output_truncated")),
                    "accepted_tag_count": len(normalized.get("accepted_tags") or []),
                    "rejected_tag_count": len(normalized.get("rejected_tags") or []),
                    "rejected_id_count": len(normalized.get("rejected_ids") or []),
                    "json_extracted": bool(normalized.get("json_extracted")),
                    "line_fallback_used": bool(normalized.get("line_fallback_used")),
                    "empty_output": bool(normalized.get("final_content_empty")),
                    "raw_output_length": len(raw_text or ""),
                    "output_source": normalized.get("output_source"),
                    "content_empty": bool(normalized.get("content_empty")),
                    "reasoning_content_used": bool(normalized.get("reasoning_content_used")),
                    "content_length": int(normalized.get("content_length") or 0),
                    "reasoning_content_length": int(normalized.get("reasoning_content_length") or 0),
                    "reasoning_leak_detected": bool(normalized.get("reasoning_leak_detected")),
                    "reasoning_leak_recovered": bool(normalized.get("reasoning_leak_recovered")),
                    "reasoning_tokens": normalized.get("reasoning_tokens"),
                    "tokens_per_second": normalized.get("tokens_per_second"),
                    "time_to_first_token_seconds": normalized.get("time_to_first_token_seconds"),
                    "no_final_answer": bool(normalized.get("no_final_answer")),
                    "normalization_error_type": normalized.get("normalization_error_type"),
                    "raw_path": storage.raw_path(req["request_id"]).relative_to(storage.run_dir).as_posix(),
                    "normalized_path": storage.normalized_path(req["request_id"]).relative_to(storage.run_dir).as_posix(),
                }

                raw_payload = {
                    "request_id": req["request_id"],
                    "transport": "rest",
                    "reasoning_requested": model.reasoning,
                    "model_id": model.id,
                    "model_label": model.label,
                    "image_id": req["image_id"],
                    "mode": mode,
                    "prompt_version": normalized["prompt_version"],
                    "response_format_requested": normalized["response_format_requested"],
                    "response_format_used": normalized["response_format_used"],
                    "final_content": rest_meta["final_content"],
                    "reasoning_content": rest_meta["reasoning_content"],
                    "response": completion_payload,
                }
                if is_accumulate:
                    storage.save_attempt_raw(req["request_id"], attempt_no, raw_payload)
                    storage.save_attempt_normalized(req["request_id"], attempt_no, normalized)
                    storage.save_attempt_diagnostics(req["request_id"], attempt_no, request_diag)
                else:
                    storage.save_request_raw(req["request_id"], raw_payload)
                    storage.save_request_normalized(req["request_id"], normalized)
                    storage.save_request_diagnostics(req["request_id"], request_diag)
                    storage.save_raw_output(req["request_id"], raw_payload)
                    storage.save_normalized(req["request_id"], normalized)

                storage.append_summary_row(
                    {
                        "run_id": run_id,
                        "request_id": req["request_id"],
                        "attempt": attempt_no,
                        "status": "success" if not normalized.get("error_type") else "failed",
                        "model_id": model.id,
                        "base_model_id": model.base_model_id,
                        "model_label": model.label,
                        "params": model.params,
                        "quant": model.quant,
                        "quant_bits": model.quant_bits,
                        "image_id": req["image_id"],
                        "image_path": req["image_path"],
                        "image_rel_path": req["image_rel_path"],
                        "mode": mode,
                        "prompt_version": normalized["prompt_version"],
                        "response_format_requested": normalized["response_format_requested"],
                        "response_format_used": normalized["response_format_used"],
                        "transport": "rest",
                        "reasoning_requested": model.reasoning,
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
                        "final_content_empty": normalized.get("final_content_empty"),
                        "final_content_length": normalized.get("final_content_length"),
                        "reasoning_content_present": normalized.get("reasoning_content_present"),
                        "reasoning_content_length": normalized.get("reasoning_content_length"),
                        "reasoning_tokens": normalized.get("reasoning_tokens"),
                        "reasoning_leak_detected": normalized.get("reasoning_leak_detected"),
                        "reasoning_leak_recovered": normalized.get("reasoning_leak_recovered"),
                        "no_final_answer": normalized.get("no_final_answer"),
                        "normalization_error_type": normalized.get("normalization_error_type"),
                        "tokens_per_second": normalized.get("tokens_per_second"),
                        "time_to_first_token_seconds": normalized.get("time_to_first_token_seconds"),
                        "gpu_memory_before_mb": gpu_before.get("memory_used_mb"),
                        "gpu_memory_after_mb": gpu_after.get("memory_used_mb"),
                        "error_type": normalized["error_type"],
                        "error": normalized["error"],
                        "raw_path": (
                            storage.attempt_path(req["request_id"], attempt_no, "raw").relative_to(storage.run_dir).as_posix()
                            if is_accumulate
                            else storage.request_path(req["request_id"], "raw").relative_to(storage.run_dir).as_posix()
                        ),
                        "normalized_path": (
                            storage.attempt_path(req["request_id"], attempt_no, "normalized").relative_to(storage.run_dir).as_posix()
                            if is_accumulate
                            else storage.request_path(req["request_id"], "normalized").relative_to(storage.run_dir).as_posix()
                        ),
                        "request_diagnostics_path": (
                            storage.attempt_path(req["request_id"], attempt_no, "diagnostics").relative_to(storage.run_dir).as_posix()
                            if is_accumulate
                            else storage.request_path(req["request_id"], "diagnostics").relative_to(storage.run_dir).as_posix()
                        ),
                    }
                )

                final_status = "failed" if normalized.get("error_type") else "success"
                final_status_payload = _request_status_payload(
                    request=req,
                    status=final_status,
                    started_at=req_start_ts,
                    finished_at=now_timestamp(),
                    duration_sec=latency,
                    error_type=normalized.get("error_type"),
                    error=normalized.get("error"),
                )
                final_status_payload["attempt"] = attempt_no
                if is_accumulate:
                    storage.save_attempt_status(req["request_id"], attempt_no, final_status_payload)
                else:
                    storage.save_request_status(req["request_id"], final_status_payload)
                if final_status == "failed":
                    failed_count += 1
                completed_count += 1
                requests_diag.append(request_diag)

            if cfg.runtime.unload_model_after_run:
                try:
                    unloaded_after = client.unload_all_loaded_models()
                    if unloaded_after:
                        storage.append_error(f"{model.label}: post_run_unload: removed {len(unloaded_after)} loaded instance(s)")
                    model_diag["unload_ok"] = True
                except LMStudioClientError as exc:
                    storage.append_error(f"{model.label}: unload_failed: {exc}")
                    model_diag["unload_ok"] = False
                    model_diag["unload_error"] = shorten_error(str(exc))

            gpu_after_unload = collect_gpu_memory(cfg)
            storage.save_model_metadata(model.label, "gpu_after_unload.json", gpu_after_unload)
            model_diag["gpu_after_unload"] = gpu_after_unload
            model_req_diag = [item for item in requests_diag if item.get("model_label") == model.label]
            model_diag.update(summarize_model_requests(model_req_diag))
            models_diag.append(model_diag)

        warning_items: list[dict[str, Any]] = []
        summary_rows: list[dict[str, str]] = []
        if storage.summary_csv_path.exists():
            with storage.summary_csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                summary_rows = list(csv.DictReader(fh))
        duplicate_index: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for row in summary_rows:
            key = (row.get("image_id", ""), row.get("mode", ""), row.get("model_label", ""))
            duplicate_index.setdefault(key, []).append(row)
        for (image_id, mode, model_label), items in duplicate_index.items():
            if len(items) > 1:
                warning_items.append(
                    {
                        "type": "duplicate_summary_rows",
                        "key": {"image_id": image_id, "mode": mode, "model_label": model_label},
                        "count": len(items),
                        "used_request_id": items[-1].get("request_id"),
                    }
                )

        run_error_count = sum(1 for item in requests_diag if item.get("error_type"))
        run_success_count = len(requests_diag) - run_error_count
        pool_violation_count = sum(int(item.get("pool_violations") or 0) for item in requests_diag)
        finished_at = datetime.now()
        diagnostics_payload = {
            "schema_version": 1,
            "run": {
                "run_id": run_id,
                "started_at": started_at_str,
                "finished_at": now_timestamp(),
                "duration_sec": round((finished_at - started_at).total_seconds(), 4),
                "config_path": str(cfg.config_path),
                "results_dir": str(storage.run_dir),
                "image_dir": str(cfg.input.image_dir),
                "recursive": bool(cfg.input.recursive),
                "limit_images": limit if limit is not None else cfg.limits.limit_images,
                "extensions": list(cfg.input.extensions),
                "model_count": len(cfg.models),
                "image_count": len(images),
                "mode_count": len(cfg.modes),
                "request_count": len(requests_diag),
                "success_count": run_success_count,
                "error_count": run_error_count,
                "pool_violation_count": pool_violation_count,
                "python_version": sys.version.split()[0],
                "git_commit": detect_git_commit(),
            },
            "pools": pool_diag,
            "models": models_diag,
            "requests": requests_diag,
            "warnings": warning_items,
        }
        storage.save_diagnostics(diagnostics_payload)
        save_state("complete")
        storage.save_run_complete({"schema_version": 1, "run_id": run_id, "completed_at": now_timestamp()})

        if cfg.report.generate_html:
            build_report(storage.run_dir)
            build_diagnostics_report(storage.run_dir)
        return storage.run_dir
    finally:
        storage.release_lock()
