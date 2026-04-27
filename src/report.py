from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {"1", "true", "yes"}


def _parse_json_cell(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except ValueError:
        pass
    return []


def _thumb_path(run_dir: Path, request_id: str) -> Path:
    return run_dir / "assets" / "thumbs" / f"{request_id}.jpg"


def _ensure_thumbnail(image_path: str, output_path: Path, size: int = 256) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(image_path) as image:
            image.thumbnail((size, size))
            image.convert("RGB").save(output_path, "JPEG")
        return True
    except Exception:
        return False


def _build_model_summary(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("model_label", "<unknown>")].append(row)

    summary: list[dict[str, Any]] = []
    for model_label, items in grouped.items():
        count = len(items)
        if count == 0:
            continue
        avg_latency = sum(_to_float(item.get("latency_sec")) for item in items) / count
        parse_rate = sum(_to_bool(item.get("parse_ok")) for item in items) / count
        schema_rate = sum(_to_bool(item.get("schema_ok")) for item in items) / count
        fallback_rate = sum(_to_bool(item.get("line_fallback_used")) for item in items) / count
        pool_violations = sum(int(item.get("pool_violations") or 0) for item in items)
        errors = sum(1 for item in items if item.get("error_type"))
        context_warnings = sum(_to_bool(item.get("context_near_limit")) for item in items)

        gpu_before_vals = [item.get("gpu_memory_before_mb") for item in items if item.get("gpu_memory_before_mb")]
        gpu_after_vals = [item.get("gpu_memory_after_mb") for item in items if item.get("gpu_memory_after_mb")]
        summary.append(
            {
                "model_label": model_label,
                "request_count": count,
                "avg_latency": avg_latency,
                "parse_rate": parse_rate,
                "schema_rate": schema_rate,
                "fallback_rate": fallback_rate,
                "pool_violations": pool_violations,
                "errors": errors,
                "context_warnings": context_warnings,
                "gpu_before_mb": gpu_before_vals[0] if gpu_before_vals else None,
                "gpu_after_mb": gpu_after_vals[0] if gpu_after_vals else None,
            }
        )
    summary.sort(key=lambda item: item["model_label"])
    return summary


def build_report(run_dir: Path) -> Path:
    summary_path = run_dir / "summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.csv not found in {run_dir}")
    run_config_path = run_dir / "run_config.yaml"
    thumbnail_size = 256
    if run_config_path.exists():
        import yaml

        config = yaml.safe_load(run_config_path.read_text(encoding="utf-8")) or {}
        thumbnail_size = int((config.get("report") or {}).get("thumbnail_size", 256))

    with summary_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    model_summary = _build_model_summary(rows)
    gallery_rows = []
    for row in rows:
        request_id = row.get("request_id", "")
        image_path = row.get("image_path", "")
        thumb = _thumb_path(run_dir, request_id)
        thumb_ok = _ensure_thumbnail(image_path, thumb, size=thumbnail_size) if image_path else False
        image_ref = thumb.relative_to(run_dir).as_posix() if thumb_ok else image_path
        gallery_rows.append(
            {
                "image_ref": image_ref,
                "model_label": row.get("model_label", ""),
                "mode": row.get("mode", ""),
                "accepted_tags": _parse_json_cell(row.get("accepted_tags")),
                "rejected_tags": _parse_json_cell(row.get("rejected_tags")),
                "rejected_ids": _parse_json_cell(row.get("rejected_ids")),
                "error": row.get("error", ""),
            }
        )

    summary_html = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(item['model_label'])}</td>"
            f"<td>{item['request_count']}</td>"
            f"<td>{item['avg_latency']:.3f}</td>"
            f"<td>{item['parse_rate']:.2%}</td>"
            f"<td>{item['schema_rate']:.2%}</td>"
            f"<td>{item['fallback_rate']:.2%}</td>"
            f"<td>{item['pool_violations']}</td>"
            f"<td>{item['errors']}</td>"
            f"<td>{item['context_warnings']}</td>"
            f"<td>{item['gpu_before_mb'] if item['gpu_before_mb'] is not None else ''}</td>"
            f"<td>{item['gpu_after_mb'] if item['gpu_after_mb'] is not None else ''}</td>"
            "</tr>"
        )
        for item in model_summary
    )

    gallery_html = "\n".join(
        (
            "<div class='card'>"
            f"<img src='{html.escape(item['image_ref'])}' alt='image' />"
            f"<div><strong>{html.escape(item['model_label'])}</strong> / {html.escape(item['mode'])}</div>"
            f"<div>Accepted: {html.escape(', '.join(item['accepted_tags']))}</div>"
            f"<div>Rejected tags: {html.escape(', '.join(item['rejected_tags']))}</div>"
            f"<div>Rejected IDs: {html.escape(', '.join(item['rejected_ids']))}</div>"
            f"<div class='error'>{html.escape(item['error'] or '')}</div>"
            "</div>"
        )
        for item in gallery_rows
    )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Local VLM Benchmark Report</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 16px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px; font-size: 13px; }}
    .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #ddd; padding: 8px; border-radius: 6px; }}
    img {{ max-width: 100%; max-height: 220px; object-fit: contain; display: block; margin-bottom: 8px; }}
    .error {{ color: #b00020; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Local VLM Benchmark Report</h1>
  <h2>Model summary</h2>
  <table>
    <thead>
      <tr>
        <th>Model</th><th>Requests</th><th>Avg latency</th><th>Parse OK</th><th>Schema OK</th>
        <th>Fallback rate</th><th>Pool violations</th><th>Errors</th><th>Context warnings</th>
        <th>GPU before MB</th><th>GPU after MB</th>
      </tr>
    </thead>
    <tbody>{summary_html}</tbody>
  </table>
  <h2>Gallery</h2>
  <div class="gallery">{gallery_html}</div>
</body>
</html>
"""
    report_path = run_dir / "report.html"
    report_path.write_text(html_text, encoding="utf-8")
    return report_path

