from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from src.diagnostics import detect_git_commit, now_timestamp
from src.report import build_diagnostics_report, build_report
from src.storage import SUMMARY_FIELDS
from src.tag_pools import ExplainedTagEntry, TagPools
from src.validator import normalize_model_output


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_run_config(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run_config.yaml"
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_project_path(value: str, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _load_plain_pool(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _load_explained_pool(path: Path) -> list[ExplainedTagEntry]:
    if not path.exists():
        return []
    entries: list[ExplainedTagEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        item_id, tag, explanation = (part.strip() for part in parts)
        if item_id and tag:
            entries.append(ExplainedTagEntry(id=item_id, tag=tag, explanation=explanation))
    return entries


def _load_pools_for_reparse(run_dir: Path, manifest: dict[str, Any], run_config: dict[str, Any]) -> TagPools | None:
    pools_raw = run_config.get("pools")
    if not isinstance(pools_raw, dict):
        return None
    config_path = Path(str(manifest.get("config_path") or ""))
    root = config_path.parent if config_path.is_absolute() and config_path.exists() else _project_root()
    pools = TagPools(
        ru_plain=_load_plain_pool(_resolve_project_path(str(pools_raw.get("ru_plain") or ""), root)),
        en_plain=_load_plain_pool(_resolve_project_path(str(pools_raw.get("en_plain") or ""), root)),
        ru_explained=_load_explained_pool(_resolve_project_path(str(pools_raw.get("ru_explained") or ""), root)),
        en_explained=_load_explained_pool(_resolve_project_path(str(pools_raw.get("en_explained") or ""), root)),
    )
    if not any([pools.ru_plain, pools.en_plain, pools.ru_explained, pools.en_explained]):
        return None
    return pools


def _reparse_normalized_from_raw(
    *,
    raw: dict[str, Any] | None,
    normalized: dict[str, Any] | None,
    req: dict[str, Any],
    pools: TagPools | None,
    run_config: dict[str, Any],
) -> dict[str, Any] | None:
    if raw is None or normalized is None or pools is None:
        return normalized
    raw_output = str(raw.get("final_content") or "")
    if not raw_output:
        return normalized

    validation = run_config.get("validation") if isinstance(run_config.get("validation"), dict) else {}
    reparsed = normalize_model_output(
        raw_output=raw_output,
        mode=str(normalized.get("mode") or raw.get("mode") or req.get("mode") or ""),
        requested_response_format=str(
            normalized.get("response_format_requested")
            or raw.get("response_format_used")
            or raw.get("response_format_requested")
            or req.get("response_format_requested")
            or "line_tags"
        ),
        pools=pools,
        allow_json_extraction=bool(validation.get("allow_json_extraction", True)),
        allow_line_fallback=bool(validation.get("allow_line_fallback", True)),
        drop_tags_not_in_pool=bool(validation.get("drop_tags_not_in_pool", True)),
        prompt_version=str(normalized.get("prompt_version") or req.get("prompt_version") or raw.get("prompt_version") or "v2"),
    )
    return {**normalized, **reparsed}


def _is_stale(run_dir: Path) -> bool:
    summary = run_dir / "summary.csv"
    diagnostics = run_dir / "diagnostics.json"
    if not summary.exists() or not diagnostics.exists():
        return True
    base_mtime = min(summary.stat().st_mtime, diagnostics.stat().st_mtime)
    for path in (run_dir / "requests").rglob("*.json"):
        if path.stat().st_mtime > base_mtime:
            return True
    return False


def _read_errors_log(run_dir: Path) -> str:
    path = run_dir / "errors.log"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _effective_status(status: dict[str, Any], normalized: dict[str, Any] | None) -> str:
    status_name = str(status.get("status") or "")
    if status_name in {"success", "failed", "skipped"} and normalized is not None:
        return "failed" if normalized.get("error_type") else "success"
    return status_name


def collect_run(run_dir: Path, *, write_reports: bool = False, strict: bool = False) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing run_manifest.json in {run_dir}")
    manifest = _load_json(manifest_path)
    if manifest is None:
        raise RuntimeError(f"Invalid run_manifest.json in {run_dir}")
    run_config_yaml = _load_run_config(run_dir)
    reparse_pools = _load_pools_for_reparse(run_dir, manifest, run_config_yaml)

    lock_path = run_dir / "run.lock"
    warnings: list[dict[str, Any]] = []
    if lock_path.exists():
        if strict:
            raise RuntimeError(f"run.lock exists: {lock_path}")
        warnings.append({"type": "run_lock_present", "path": str(lock_path)})

    requests = manifest.get("requests")
    if not isinstance(requests, list):
        raise RuntimeError("Invalid run_manifest.json: requests must be a list")

    run_config = _load_json(run_dir / "diagnostics.json") or {}
    prior_run = run_config.get("run") if isinstance(run_config, dict) else {}
    if not isinstance(prior_run, dict):
        prior_run = {}
    model_meta = _load_json(run_dir / "models.json") or []
    model_map: dict[str, dict[str, Any]] = {}
    if isinstance(model_meta, list):
        for row in model_meta:
            if isinstance(row, dict):
                model_map[str(row.get("label") or "")] = row

    summary_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    expected = len(requests)
    completed = 0
    failed = 0
    incomplete = 0
    attempt_count = 0
    successful_attempt_count = 0
    failed_attempt_count = 0
    running_or_incomplete_attempt_count = 0
    result_mode = str(manifest.get("result_mode") or "deterministic")

    for req in requests:
        if not isinstance(req, dict):
            if strict:
                raise RuntimeError("Invalid request item in manifest")
            warnings.append({"type": "invalid_manifest_request", "request": str(req)})
            continue
        request_id = str(req.get("request_id") or "")
        request_dir = run_dir / "requests" / request_id
        request_descriptor = _load_json(request_dir / "request.json") or {}
        if not isinstance(request_descriptor, dict):
            request_descriptor = {}
        model_label = str(req.get("model_label") or "")
        model_info = model_map.get(model_label, {})

        def append_attempt(
            *,
            attempt_no: int,
            status: dict[str, Any],
            normalized: dict[str, Any] | None,
            req_diag: dict[str, Any] | None,
            base_prefix: str,
        ) -> None:
            nonlocal attempt_count, successful_attempt_count, failed_attempt_count
            raw_payload = _load_json(run_dir / base_prefix / "raw.json")
            normalized = _reparse_normalized_from_raw(
                raw=raw_payload,
                normalized=normalized,
                req={**req, **request_descriptor},
                pools=reparse_pools,
                run_config=run_config_yaml,
            )
            if normalized is not None:
                normalized_path = run_dir / base_prefix / "normalized.json"
                normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
            attempt_count += 1
            status_name = _effective_status(status, normalized)
            if status_name == "success":
                successful_attempt_count += 1
            elif status_name == "failed":
                failed_attempt_count += 1
            row_base = {
                "run_id": manifest.get("run_id"),
                "request_id": request_id,
                "attempt": attempt_no,
                "status": status_name or "unknown",
                "model_id": req.get("model_id"),
                "base_model_id": req.get("base_model_id") or model_info.get("base_model_id"),
                "model_label": model_label,
                "params": model_info.get("params"),
                "quant": model_info.get("quant"),
                "quant_bits": model_info.get("quant_bits"),
                "image_id": req.get("image_id"),
                "image_path": req.get("image_path") or request_descriptor.get("image_path"),
                "image_rel_path": req.get("image_rel_path") or request_descriptor.get("image_rel_path"),
                "mode": req.get("mode"),
                "prompt_version": req.get("prompt_version"),
                "response_format_requested": req.get("response_format_requested"),
                "transport": req.get("transport") or (normalized.get("transport") if normalized else "openai_legacy"),
                "reasoning_requested": req.get("reasoning_requested") or (normalized.get("reasoning_requested") if normalized else ""),
            }
            if normalized is None:
                normalized = {
                    "response_format_used": req.get("response_format_requested"),
                    "accepted_tags": [],
                    "accepted_ids": [],
                    "rejected_tags": [],
                    "rejected_ids": [],
                    "pool_violations": 0,
                    "parse_ok": False,
                    "schema_ok": False,
                    "json_extracted": False,
                    "line_fallback_used": False,
                    "pool_ok": False if str(req.get("mode") or "").endswith("_pool") else True,
                    "latency_sec": status.get("duration_sec"),
                    "error_type": status.get("error_type"),
                    "error": status.get("error"),
                    "transport": req.get("transport") or "openai_legacy",
                    "reasoning_requested": req.get("reasoning_requested") or "",
                }
                if strict:
                    raise RuntimeError(f"Missing normalized.json for {request_id}")
            final_content_empty = normalized.get("final_content_empty")
            if final_content_empty is None:
                final_content_empty = bool(normalized.get("content_empty"))
            final_content_length = normalized.get("final_content_length")
            if final_content_length is None:
                final_content_length = normalized.get("content_length")
            reasoning_content_length = normalized.get("reasoning_content_length")
            reasoning_content_present = normalized.get("reasoning_content_present")
            if reasoning_content_present is None:
                reasoning_content_present = bool(_to_int(reasoning_content_length, 0) > 0)
            no_final_answer = normalized.get("no_final_answer")
            if no_final_answer is None:
                no_final_answer = bool(final_content_empty and reasoning_content_present)

            summary_rows.append(
                {
                    **row_base,
                    "response_format_used": normalized.get("response_format_used"),
                    "accepted_tags": normalized.get("accepted_tags") or [],
                    "accepted_ids": normalized.get("accepted_ids") or [],
                    "rejected_tags": normalized.get("rejected_tags") or [],
                    "rejected_ids": normalized.get("rejected_ids") or [],
                    "tag_count": len(normalized.get("accepted_tags") or []),
                    "pool_violations": normalized.get("pool_violations") or 0,
                    "parse_ok": bool(normalized.get("parse_ok")),
                    "schema_ok": bool(normalized.get("schema_ok")),
                    "json_extracted": bool(normalized.get("json_extracted")),
                    "line_fallback_used": bool(normalized.get("line_fallback_used")),
                    "pool_ok": bool(normalized.get("pool_ok")),
                    "latency_sec": normalized.get("latency_sec"),
                    "prompt_tokens": normalized.get("prompt_tokens"),
                    "completion_tokens": normalized.get("completion_tokens"),
                    "total_tokens": normalized.get("total_tokens"),
                    "requested_context_length": normalized.get("requested_context_length"),
                    "actual_context_length": normalized.get("actual_context_length"),
                    "context_near_limit": normalized.get("context_near_limit"),
                    "context_overflow": normalized.get("context_overflow"),
                    "output_truncated": normalized.get("output_truncated"),
                    "final_content_empty": final_content_empty,
                    "final_content_length": final_content_length,
                    "reasoning_content_present": reasoning_content_present,
                    "reasoning_content_length": reasoning_content_length,
                    "reasoning_tokens": normalized.get("reasoning_tokens"),
                    "reasoning_leak_detected": bool(normalized.get("reasoning_leak_detected")),
                    "reasoning_leak_recovered": bool(normalized.get("reasoning_leak_recovered")),
                    "no_final_answer": no_final_answer,
                    "normalization_error_type": normalized.get("normalization_error_type"),
                    "tokens_per_second": normalized.get("tokens_per_second"),
                    "time_to_first_token_seconds": normalized.get("time_to_first_token_seconds"),
                    "content_empty": normalized.get("content_empty", final_content_empty),
                    "content_length": normalized.get("content_length", final_content_length),
                    "reasoning_content_used": normalized.get("reasoning_content_used", False),
                    "gpu_memory_before_mb": None,
                    "gpu_memory_after_mb": None,
                    "error_type": normalized.get("error_type") or status.get("error_type"),
                    "error": normalized.get("error") or status.get("error"),
                    "raw_path": f"{base_prefix}/raw.json",
                    "normalized_path": f"{base_prefix}/normalized.json",
                    "request_diagnostics_path": f"{base_prefix}/diagnostics.json",
                }
            )
            if req_diag is None:
                req_diag = {
                    "request_id": request_id,
                    "attempt": attempt_no,
                    "status": status_name or "unknown",
                    "model_label": model_label,
                    "model_id": req.get("model_id"),
                    "image_id": req.get("image_id"),
                    "image_rel_path": req.get("image_rel_path"),
                    "mode": req.get("mode"),
                    "latency_sec": normalized.get("latency_sec"),
                    "response_format_requested": req.get("response_format_requested"),
                    "response_format_used": normalized.get("response_format_used"),
                    "transport": row_base["transport"],
                    "reasoning_requested": row_base["reasoning_requested"],
                    "parse_ok": bool(normalized.get("parse_ok")),
                    "schema_ok": bool(normalized.get("schema_ok")),
                    "pool_ok": bool(normalized.get("pool_ok")),
                    "pool_violations": int(normalized.get("pool_violations") or 0),
                    "error_type": normalized.get("error_type"),
                    "error": normalized.get("error"),
                    "final_content_empty": final_content_empty,
                    "reasoning_content_present": reasoning_content_present,
                    "no_final_answer": no_final_answer,
                    "normalization_error_type": normalized.get("normalization_error_type"),
                    "reasoning_tokens": normalized.get("reasoning_tokens"),
                    "reasoning_content_length": reasoning_content_length,
                    "final_content_length": final_content_length,
                    "reasoning_leak_detected": bool(normalized.get("reasoning_leak_detected")),
                    "reasoning_leak_recovered": bool(normalized.get("reasoning_leak_recovered")),
                    "tokens_per_second": normalized.get("tokens_per_second"),
                    "time_to_first_token_seconds": normalized.get("time_to_first_token_seconds"),
                    "accepted_tag_count": len(normalized.get("accepted_tags") or []),
                    "rejected_tag_count": len(normalized.get("rejected_tags") or []),
                    "rejected_id_count": len(normalized.get("rejected_ids") or []),
                    "raw_path": f"{base_prefix}/raw.json",
                    "normalized_path": f"{base_prefix}/normalized.json",
                }
            else:
                req_diag.update(
                    {
                        "status": status_name or "unknown",
                        "response_format_used": normalized.get("response_format_used"),
                        "parse_ok": bool(normalized.get("parse_ok")),
                        "schema_ok": bool(normalized.get("schema_ok")),
                        "pool_ok": bool(normalized.get("pool_ok")),
                        "pool_violations": int(normalized.get("pool_violations") or 0),
                        "error_type": normalized.get("error_type"),
                        "error": normalized.get("error"),
                        "accepted_tag_count": len(normalized.get("accepted_tags") or []),
                        "rejected_tag_count": len(normalized.get("rejected_tags") or []),
                        "rejected_id_count": len(normalized.get("rejected_ids") or []),
                        "reasoning_leak_detected": bool(normalized.get("reasoning_leak_detected")),
                        "reasoning_leak_recovered": bool(normalized.get("reasoning_leak_recovered")),
                    }
                )
                (run_dir / base_prefix / "diagnostics.json").write_text(
                    json.dumps(req_diag, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            request_rows.append(req_diag)

        if result_mode == "accumulate":
            attempts_root = request_dir / "attempts"
            attempt_dirs = sorted(
                [p for p in attempts_root.iterdir() if p.is_dir()],
                key=lambda p: int(p.name) if p.name.isdigit() else 999999,
            ) if attempts_root.exists() else []
            if not attempt_dirs:
                incomplete += 1
                warnings.append({"type": "incomplete_request", "request_id": request_id, "model_label": req.get("model_label"), "image_id": req.get("image_id"), "mode": req.get("mode")})
                continue
            req_has_terminal = False
            for adir in attempt_dirs:
                attempt_no = int(adir.name) if adir.name.isdigit() else 0
                status = _load_json(adir / "status.json")
                normalized = _load_json(adir / "normalized.json")
                req_diag = _load_json(adir / "diagnostics.json")
                if status is None:
                    running_or_incomplete_attempt_count += 1
                    warnings.append({"type": "incomplete_attempt", "request_id": request_id, "attempt": attempt_no})
                    if strict:
                        raise RuntimeError(f"Missing attempt status for {request_id}/{attempt_no}")
                    continue
                status_name = str(status.get("status") or "")
                if status_name == "running":
                    running_or_incomplete_attempt_count += 1
                    warnings.append({"type": "incomplete_attempt", "request_id": request_id, "attempt": attempt_no})
                    if strict:
                        raise RuntimeError(f"Attempt still running: {request_id}/{attempt_no}")
                    continue
                req_has_terminal = True
                append_attempt(
                    attempt_no=attempt_no or int(status.get("attempt") or 1),
                    status=status,
                    normalized=normalized,
                    req_diag=req_diag,
                    base_prefix=f"requests/{request_id}/attempts/{attempt_no:03d}",
                )
            if req_has_terminal:
                completed += 1
            else:
                incomplete += 1
            continue

        status = _load_json(request_dir / "status.json")
        normalized = _load_json(request_dir / "normalized.json")
        req_diag = _load_json(request_dir / "diagnostics.json")
        if status is None:
            incomplete += 1
            warnings.append({"type": "incomplete_request", "request_id": request_id, "model_label": req.get("model_label"), "image_id": req.get("image_id"), "mode": req.get("mode")})
            if strict:
                raise RuntimeError(f"Missing status artifact for {request_id}")
            continue
        normalized_for_status = _reparse_normalized_from_raw(
            raw=_load_json(request_dir / "raw.json"),
            normalized=normalized,
            req={**req, **request_descriptor},
            pools=reparse_pools,
            run_config=run_config_yaml,
        )
        status_name = _effective_status(status, normalized_for_status)
        if status_name == "running":
            incomplete += 1
            running_or_incomplete_attempt_count += 1
            warnings.append({"type": "incomplete_request", "request_id": request_id, "model_label": req.get("model_label"), "image_id": req.get("image_id"), "mode": req.get("mode")})
            if strict:
                raise RuntimeError(f"Request still running: {request_id}")
            continue
        completed += 1
        if status_name == "failed":
            failed += 1
            if strict:
                raise RuntimeError(f"Request failed in strict mode: {request_id}")
        append_attempt(
            attempt_no=int(status.get("attempt") or 1),
            status=status,
            normalized=normalized_for_status,
            req_diag=req_diag,
            base_prefix=f"requests/{request_id}",
        )

    summary_path = run_dir / "summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in summary_rows:
            normalized_row = {}
            for field in SUMMARY_FIELDS:
                value = row.get(field)
                if isinstance(value, (list, dict)):
                    normalized_row[field] = json.dumps(value, ensure_ascii=False)
                else:
                    normalized_row[field] = value
            writer.writerow(normalized_row)

    run_complete = (run_dir / "run_complete.json").exists()
    diagnostics_payload = {
        "schema_version": 1,
        "run": {
            "run_id": manifest.get("run_id"),
            "started_at": prior_run.get("started_at"),
            "finished_at": prior_run.get("finished_at") if run_complete else now_timestamp(),
            "duration_sec": prior_run.get("duration_sec"),
            "config_path": manifest.get("config_path"),
            "results_dir": str(run_dir),
            "image_dir": prior_run.get("image_dir"),
            "recursive": prior_run.get("recursive"),
            "limit_images": prior_run.get("limit_images"),
            "extensions": prior_run.get("extensions") or [],
            "model_count": prior_run.get("model_count"),
            "image_count": prior_run.get("image_count"),
            "mode_count": prior_run.get("mode_count"),
            "request_count": len(request_rows),
            "success_count": len([r for r in request_rows if not r.get("error_type")]),
            "error_count": len([r for r in request_rows if r.get("error_type")]),
            "pool_violation_count": sum(int(r.get("pool_violations") or 0) for r in request_rows),
            "python_version": prior_run.get("python_version"),
            "git_commit": detect_git_commit(),
            "result_mode": result_mode,
            "is_partial": not run_complete,
            "expected_request_count": expected,
            "completed_request_count": completed,
            "failed_request_count": failed,
            "running_or_incomplete_request_count": incomplete,
            "attempt_count": attempt_count,
            "successful_attempt_count": successful_attempt_count,
            "failed_attempt_count": failed_attempt_count,
            "running_or_incomplete_attempt_count": running_or_incomplete_attempt_count,
        },
        "pools": run_config.get("pools") if isinstance(run_config, dict) else {},
        "models": run_config.get("models") if isinstance(run_config, dict) else [],
        "requests": request_rows,
        "rest_summary": {
            "transport_counts": {},
            "reasoning_requested_counts": {},
            "no_final_answer_count": 0,
            "reasoning_content_present_count": 0,
            "reasoning_tokens_total": 0,
        },
        "warnings": warnings,
        "errors_log_excerpt": _read_errors_log(run_dir)[:8000],
    }
    rest_summary = diagnostics_payload["rest_summary"]
    for row in request_rows:
        if not isinstance(row, dict):
            continue
        transport = str(row.get("transport") or "")
        if transport:
            rest_summary["transport_counts"][transport] = rest_summary["transport_counts"].get(transport, 0) + 1
        reasoning_requested = str(row.get("reasoning_requested") or "")
        if reasoning_requested:
            rest_summary["reasoning_requested_counts"][reasoning_requested] = (
                rest_summary["reasoning_requested_counts"].get(reasoning_requested, 0) + 1
            )
        if bool(row.get("no_final_answer")):
            rest_summary["no_final_answer_count"] += 1
        if bool(row.get("reasoning_content_present")):
            rest_summary["reasoning_content_present_count"] += 1
        try:
            tokens = int(row.get("reasoning_tokens")) if row.get("reasoning_tokens") is not None else None
        except (TypeError, ValueError):
            tokens = None
        if isinstance(tokens, int):
            rest_summary["reasoning_tokens_total"] += tokens
    diagnostics_path = run_dir / "diagnostics.json"
    diagnostics_path.write_text(json.dumps(diagnostics_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if write_reports:
        build_report(run_dir)
        build_diagnostics_report(run_dir)

    return {"summary_path": summary_path, "diagnostics_path": diagnostics_path}


def ensure_collected(run_dir: Path, *, strict: bool = False) -> None:
    if _is_stale(run_dir):
        collect_run(run_dir, write_reports=False, strict=strict)
