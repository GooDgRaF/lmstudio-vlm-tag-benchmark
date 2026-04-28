from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.config import BenchmarkConfig, ModelConfig

SUMMARY_FIELDS = [
    "run_id",
    "request_id",
    "attempt",
    "status",
    "model_id",
    "base_model_id",
    "model_label",
    "params",
    "quant",
    "quant_bits",
    "image_id",
    "image_path",
    "image_rel_path",
    "mode",
    "prompt_version",
    "response_format_requested",
    "response_format_used",
    "accepted_tags",
    "accepted_ids",
    "rejected_tags",
    "rejected_ids",
    "tag_count",
    "pool_violations",
    "parse_ok",
    "schema_ok",
    "json_extracted",
    "line_fallback_used",
    "pool_ok",
    "latency_sec",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "requested_context_length",
    "actual_context_length",
    "context_near_limit",
    "context_overflow",
    "output_truncated",
    "gpu_memory_before_mb",
    "gpu_memory_after_mb",
    "error_type",
    "error",
    "raw_path",
    "normalized_path",
    "request_diagnostics_path",
]


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "item"


def make_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_request_id(
    *,
    model_id: str,
    model_label: str,
    image_id: str,
    mode: str,
    prompt_version: str,
    response_format_requested: str,
    pool_hash: str | None = None,
) -> str:
    source_parts = [model_id, model_label, image_id, mode, prompt_version, response_format_requested]
    if pool_hash:
        source_parts.append(pool_hash)
    source = "|".join(source_parts)
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    base = sanitize_filename(
        f"{model_label}_{image_id}_{mode}_{prompt_version}_{response_format_requested}"
    )
    if pool_hash:
        base = f"{base}_{pool_hash[:8]}"
    return f"{base}_{digest}"


class RunStorage:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw"
        self.normalized_dir = run_dir / "normalized"
        self.assets_thumbs_dir = run_dir / "assets" / "thumbs"
        self.models_dir = run_dir / "models"
        self.requests_dir = run_dir / "requests"
        self.summary_csv_path = run_dir / "summary.csv"
        self.errors_log_path = run_dir / "errors.log"
        self.manifest_path = run_dir / "run_manifest.json"
        self.state_path = run_dir / "run_state.json"
        self.complete_path = run_dir / "run_complete.json"
        self.lock_path = run_dir / "run.lock"

    def initialize(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.assets_thumbs_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.requests_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        return path

    def save_run_config(self, cfg: BenchmarkConfig) -> None:
        (self.run_dir / "run_config.yaml").write_text(
            yaml.safe_dump(cfg.to_serializable_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def save_models(self, models: list[ModelConfig]) -> None:
        serializable = [
            {
                "id": m.id,
                "base_model_id": m.base_model_id,
                "label": m.label,
                "params": m.params,
                "quant": m.quant,
                "quant_bits": m.quant_bits,
                "max_context_length": m.max_context_length,
            }
            for m in models
        ]
        (self.run_dir / "models.json").write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def ensure_model_dir(self, model_label: str) -> Path:
        model_dir = self.models_dir / sanitize_filename(model_label)
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir

    def save_model_metadata(self, model_label: str, filename: str, payload: dict[str, Any]) -> None:
        model_dir = self.ensure_model_dir(model_label)
        self._atomic_write_json(model_dir / filename, payload)

    def request_dir(self, request_id: str) -> Path:
        path = self.requests_dir / sanitize_filename(request_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def request_path(self, request_id: str, name: str) -> Path:
        return self.request_dir(request_id) / f"{name}.json"

    def save_request_descriptor(self, request_id: str, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.request_path(request_id, "request"), payload)

    def save_request_status(self, request_id: str, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.request_path(request_id, "status"), payload)

    def save_request_raw(self, request_id: str, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.request_path(request_id, "raw"), payload)

    def save_request_normalized(self, request_id: str, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.request_path(request_id, "normalized"), payload)

    def save_request_diagnostics(self, request_id: str, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.request_path(request_id, "diagnostics"), payload)

    def read_request_status(self, request_id: str) -> dict[str, Any] | None:
        path = self.request_path(request_id, "status")
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def raw_path(self, request_id: str) -> Path:
        return self.raw_dir / f"{sanitize_filename(request_id)}.json"

    def normalized_path(self, request_id: str) -> Path:
        return self.normalized_dir / f"{sanitize_filename(request_id)}.json"

    def save_raw_output(self, request_id: str, payload: dict[str, Any]) -> Path:
        path = self.raw_path(request_id)
        self._atomic_write_json(path, payload)
        return path

    def save_normalized(self, request_id: str, payload: dict[str, Any]) -> Path:
        path = self.normalized_path(request_id)
        self._atomic_write_json(path, payload)
        return path

    def save_diagnostics(self, payload: dict[str, Any]) -> Path:
        path = self.run_dir / "diagnostics.json"
        self._atomic_write_json(path, payload)
        return path

    def save_manifest(self, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.manifest_path, payload)

    def load_manifest(self) -> dict[str, Any] | None:
        if not self.manifest_path.exists():
            return None
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save_run_state(self, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.state_path, payload)

    def save_run_complete(self, payload: dict[str, Any]) -> Path:
        return self._atomic_write_json(self.complete_path, payload)

    def acquire_lock(self, *, force_lock: bool = False) -> None:
        if self.lock_path.exists() and not force_lock:
            raise RuntimeError(
                f"Run is locked: {self.lock_path}. Use --force-lock to continue with a stale lock."
            )
        if self.lock_path.exists() and force_lock:
            self.lock_path.unlink(missing_ok=True)
        self.lock_path.write_text(
            json.dumps({"created_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def release_lock(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def append_error(self, message: str) -> None:
        with self.errors_log_path.open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip("\n") + "\n")

    def init_summary_csv(self) -> None:
        if self.summary_csv_path.exists():
            return
        with self.summary_csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
            writer.writeheader()

    def append_summary_row(self, row: dict[str, Any]) -> None:
        normalized_row = {}
        for field in SUMMARY_FIELDS:
            value = row.get(field)
            if isinstance(value, (list, dict)):
                normalized_row[field] = json.dumps(value, ensure_ascii=False)
            else:
                normalized_row[field] = value
        with self.summary_csv_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
            writer.writerow(normalized_row)

    def has_summary_row(self, request_id: str) -> bool:
        if not self.summary_csv_path.exists():
            return False
        with self.summary_csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("request_id") == request_id:
                    return True
        return False


def create_run_storage(cfg: BenchmarkConfig, run_id: str | None = None) -> tuple[str, RunStorage]:
    selected_run_id = run_id or make_run_id()
    run_dir = cfg.resolve_path(cfg.output.results_dir) / selected_run_id
    storage = RunStorage(run_dir)
    storage.initialize()
    storage.save_run_config(cfg)
    storage.save_models(cfg.models)
    return selected_run_id, storage
