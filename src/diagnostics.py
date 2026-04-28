from __future__ import annotations

import subprocess
from datetime import datetime
import hashlib
import statistics
from pathlib import Path
from typing import Any

from src.config import BenchmarkConfig
from src.tag_pools import TagPools


def collect_gpu_memory(cfg: BenchmarkConfig) -> dict[str, Any]:
    settings = cfg.diagnostics.gpu_memory
    if not settings.enabled:
        return {"gpu_diagnostics_available": False}

    command = [
        "nvidia-smi",
        "--query-gpu=memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]
    if settings.command and settings.command.strip() != "nvidia-smi":
        command = settings.command.split()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return {"gpu_diagnostics_available": False}

    if proc.returncode != 0:
        return {"gpu_diagnostics_available": False}

    line = ""
    for raw in proc.stdout.splitlines():
        if raw.strip():
            line = raw.strip()
            break
    if not line:
        return {"gpu_diagnostics_available": False}

    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return {"gpu_diagnostics_available": False}
    try:
        total, used, free = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return {"gpu_diagnostics_available": False}
    return {
        "gpu_diagnostics_available": True,
        "memory_total_mb": total,
        "memory_used_mb": used,
        "memory_free_mb": free,
    }


def classify_load_error(error_message: str) -> str:
    text = error_message.lower()
    memory_words = ["out of memory", "cuda", "vram", "oom", "memory allocation"]
    if any(word in text for word in memory_words):
        return "load_failed_oom"
    return "load_failed"


def extract_usage_diagnostics(
    completion_payload: dict[str, Any],
    *,
    actual_context_length: int | None,
    warning_ratio: float,
    error_ratio: float,
) -> dict[str, Any]:
    usage = completion_payload.get("usage") if isinstance(completion_payload, dict) else None
    choices = completion_payload.get("choices") if isinstance(completion_payload, dict) else None
    finish_reason = None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")

    prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None

    context_near_limit = False
    context_overflow = False
    if isinstance(actual_context_length, int) and isinstance(total_tokens, int):
        ratio = total_tokens / float(actual_context_length)
        if ratio >= error_ratio:
            context_overflow = True
        elif ratio >= warning_ratio:
            context_near_limit = True

    output_truncated = finish_reason == "length"
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "finish_reason": finish_reason,
        "context_near_limit": context_near_limit,
        "context_overflow": context_overflow,
        "output_truncated": output_truncated,
    }


def now_timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def shorten_error(error: str | None, max_len: int = 240) -> str | None:
    if error is None:
        return None
    text = str(error).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def detect_git_commit() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    value = (proc.stdout or "").strip()
    return value or None


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _id_prefixes(ids: list[str]) -> list[str]:
    prefixes: list[str] = []
    for item in ids:
        prefix = "".join(ch for ch in item if ch.isalpha())
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def build_pool_diagnostics(cfg: BenchmarkConfig, pools: TagPools) -> dict[str, dict[str, Any]]:
    ru_plain_path = cfg.resolve_path(cfg.pools.ru_plain)
    en_plain_path = cfg.resolve_path(cfg.pools.en_plain)
    ru_explained_path = cfg.resolve_path(cfg.pools.ru_explained)
    en_explained_path = cfg.resolve_path(cfg.pools.en_explained)
    return {
        "ru_plain": {
            "path": cfg.pools.ru_plain,
            "type": "plain",
            "tag_count": len(pools.ru_plain),
            "entry_count": len(pools.ru_plain),
            "sha256": file_sha256(ru_plain_path),
        },
        "en_plain": {
            "path": cfg.pools.en_plain,
            "type": "plain",
            "tag_count": len(pools.en_plain),
            "entry_count": len(pools.en_plain),
            "sha256": file_sha256(en_plain_path),
        },
        "ru_explained": {
            "path": cfg.pools.ru_explained,
            "type": "explained",
            "tag_count": len(pools.ru_explained_tag_set),
            "entry_count": len(pools.ru_explained),
            "id_prefixes": _id_prefixes([item.id for item in pools.ru_explained]),
            "sha256": file_sha256(ru_explained_path),
        },
        "en_explained": {
            "path": cfg.pools.en_explained,
            "type": "explained",
            "tag_count": len(pools.en_explained_tag_set),
            "entry_count": len(pools.en_explained),
            "id_prefixes": _id_prefixes([item.id for item in pools.en_explained]),
            "sha256": file_sha256(en_explained_path),
        },
    }


def summarize_model_requests(requests: list[dict[str, Any]]) -> dict[str, Any]:
    if not requests:
        return {
            "request_count": 0,
            "success_count": 0,
            "error_count": 0,
            "pool_violation_count": 0,
            "avg_latency_sec": None,
            "median_latency_sec": None,
            "min_latency_sec": None,
            "max_latency_sec": None,
            "parse_ok_rate": None,
            "schema_ok_rate": None,
            "pool_ok_rate": None,
        }
    latencies = [float(item["latency_sec"]) for item in requests if item.get("latency_sec") is not None]
    count = len(requests)
    success = sum(1 for item in requests if not item.get("error_type"))
    parse_ok = sum(1 for item in requests if bool(item.get("parse_ok")))
    schema_ok = sum(1 for item in requests if bool(item.get("schema_ok")))
    pool_ok = sum(1 for item in requests if bool(item.get("pool_ok")))
    pool_violations = sum(int(item.get("pool_violations") or 0) for item in requests)
    return {
        "request_count": count,
        "success_count": success,
        "error_count": count - success,
        "pool_violation_count": pool_violations,
        "avg_latency_sec": round(sum(latencies) / len(latencies), 4) if latencies else None,
        "median_latency_sec": round(float(statistics.median(latencies)), 4) if latencies else None,
        "min_latency_sec": round(min(latencies), 4) if latencies else None,
        "max_latency_sec": round(max(latencies), 4) if latencies else None,
        "parse_ok_rate": round(parse_ok / count, 4),
        "schema_ok_rate": round(schema_ok / count, 4),
        "pool_ok_rate": round(pool_ok / count, 4),
    }
