from __future__ import annotations

import subprocess
from typing import Any

from src.config import BenchmarkConfig


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

