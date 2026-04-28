from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

CANONICAL_MODE_ORDER = [
    "ru_free",
    "ru_pool",
    "ru_pool_explained",
    "en_free",
    "en_pool",
    "en_pool_explained",
]

MODE_LABELS = {
    "ru_free": "RU free",
    "ru_pool": "RU pool",
    "ru_pool_explained": "RU pool+",
    "en_free": "EN free",
    "en_pool": "EN pool",
    "en_pool_explained": "EN pool+",
}


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


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_models_json(run_dir: Path) -> list[str]:
    models_path = run_dir / "models.json"
    if not models_path.exists():
        return []
    try:
        payload = json.loads(models_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    order: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if label and label not in order:
                order.append(label)
    return order


def _read_mode_order(run_dir: Path) -> list[str]:
    run_config_path = run_dir / "run_config.yaml"
    if not run_config_path.exists():
        return list(CANONICAL_MODE_ORDER)
    try:
        config = yaml.safe_load(run_config_path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, yaml.YAMLError):
        return list(CANONICAL_MODE_ORDER)

    configured_modes = config.get("modes")
    if not isinstance(configured_modes, list):
        return list(CANONICAL_MODE_ORDER)

    order: list[str] = []
    for mode in configured_modes:
        mode_name = str(mode).strip()
        if mode_name and mode_name not in order:
            order.append(mode_name)
    return order or list(CANONICAL_MODE_ORDER)


def _read_thumbnail_size(run_dir: Path) -> int:
    run_config_path = run_dir / "run_config.yaml"
    if not run_config_path.exists():
        return 256
    try:
        config = yaml.safe_load(run_config_path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, yaml.YAMLError):
        return 256
    return max(64, _to_int((config.get("report") or {}).get("thumbnail_size"), default=256))


def _thumbnail_rel_path(run_dir: Path, image_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in image_id).strip("_") or "image"
    return Path("assets") / "thumbs" / f"{safe}.jpg"


def _ensure_thumbnail(image_path: str, output_path: Path, size: int) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(image_path) as image:
            image.thumbnail((size, size))
            image.convert("RGB").save(output_path, "JPEG")
        return True
    except Exception:
        return False


def _render_chip(text: str, css_class: str) -> str:
    return f"<span class='chip {css_class}'>{html.escape(text)}</span>"


def _render_answer_cell(cell: dict[str, Any] | None, mode: str) -> str:
    if cell is None:
        return ""

    accepted = cell.get("accepted_tags") or []
    rejected_tags = cell.get("rejected_tags") or []
    rejected_ids = cell.get("rejected_ids") or []
    accepted_class = "free" if mode.endswith("_free") else "ok"
    chips: list[str] = []
    chips.extend(_render_chip(tag, accepted_class) for tag in accepted)
    chips.extend(_render_chip(tag, "warn") for tag in rejected_tags)
    chips.extend(_render_chip(tag, "warn mono") for tag in rejected_ids)
    if not chips:
        return ""
    return f"<div class='chips'>{''.join(chips)}</div>"


def build_report(run_dir: Path) -> Path:
    summary_path = run_dir / "summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.csv not found in {run_dir}")

    with summary_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    mode_order = _read_mode_order(run_dir)
    mode_rank = {mode: idx for idx, mode in enumerate(mode_order)}
    thumbnail_size = _read_thumbnail_size(run_dir)

    model_order = _read_models_json(run_dir)
    observed_models: list[str] = []
    for row in rows:
        model = (row.get("model_label") or "").strip()
        if model and model not in observed_models:
            observed_models.append(model)
    for model in observed_models:
        if model not in model_order:
            model_order.append(model)

    image_order: list[str] = []
    image_meta: dict[str, dict[str, str]] = {}
    matrix: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicates = 0

    for row in rows:
        image_id = (row.get("image_id") or "").strip() or "<unknown-image>"
        mode = (row.get("mode") or "").strip() or "<unknown-mode>"
        model = (row.get("model_label") or "").strip() or "<unknown-model>"

        if image_id not in image_order:
            image_order.append(image_id)
            image_meta[image_id] = {
                "image_path": str(row.get("image_path") or ""),
                "image_rel_path": str(row.get("image_rel_path") or ""),
            }

        key = (image_id, mode, model)
        if key in matrix:
            duplicates += 1

        matrix[key] = {
            "accepted_tags": _parse_json_cell(row.get("accepted_tags")),
            "rejected_tags": _parse_json_cell(row.get("rejected_tags")),
            "rejected_ids": _parse_json_cell(row.get("rejected_ids")),
            "error_type": row.get("error_type") or "",
            "error": row.get("error") or "",
        }

    top_mode_sequence = list(dict.fromkeys(mode_order + [r.get("mode", "") for r in rows if r.get("mode")]))

    request_count = len(rows)
    error_count = sum(1 for r in rows if (r.get("error_type") or "").strip())
    pool_violations = sum(_to_int(r.get("pool_violations"), default=0) for r in rows)

    header_cells = "".join(f"<th class='model-col'>{html.escape(model)}</th>" for model in model_order)

    body_rows: list[str] = []
    for image_id in image_order:
        image_info = image_meta.get(image_id, {})
        image_path = image_info.get("image_path", "")
        image_rel_path = image_info.get("image_rel_path", "")
        thumb_rel = _thumbnail_rel_path(run_dir, image_id)
        thumb_abs = run_dir / thumb_rel
        thumb_ok = _ensure_thumbnail(image_path, thumb_abs, size=thumbnail_size) if image_path else False
        thumb_html = (
            f"<img src='{html.escape(thumb_rel.as_posix())}' alt='{html.escape(image_id)}' class='thumb' />"
            if thumb_ok
            else "<div class='thumb missing'>no preview</div>"
        )
        image_link = (
            f"<a href='{html.escape(Path(image_path).as_uri())}' class='small'>open image</a>"
            if image_path and Path(image_path).exists()
            else ""
        )

        image_modes = [m for m in top_mode_sequence if any((image_id, m, mdl) in matrix for mdl in model_order)]
        if not image_modes:
            image_modes = mode_order

        for row_index, mode in enumerate(image_modes):
            mode_label = MODE_LABELS.get(mode, mode)
            cells = []
            for model in model_order:
                cell_html = _render_answer_cell(matrix.get((image_id, mode, model)), mode)
                cells.append(f"<td class='answer'>{cell_html}</td>")

            if row_index == 0:
                image_cell = (
                    f"<td class='image-cell' rowspan='{len(image_modes)}'>"
                    f"{thumb_html}"
                    f"{image_link}"
                    "</td>"
                )
            else:
                image_cell = ""

            body_rows.append(
                "<tr class='matrix-row'>"
                f"{image_cell}"
                f"<td class='mode-cell'>{html.escape(mode_label)}</td>"
                + "".join(cells)
                + "</tr>"
            )

    diagnostics_link = ""
    diagnostics_path = run_dir / "diagnostics.html"
    if diagnostics_path.exists():
        diagnostics_link = "<a href='diagnostics.html'>Diagnostics report</a>"

    duplicate_note = (
        f"<div class='note'>Duplicate request rows: {duplicates}</div>" if duplicates else ""
    )

    html_text = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Local VLM Benchmark Report</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 16px; color: #1f2937; background: #f8fafc; }}
    h1 {{ margin: 0 0 10px; font-size: 22px; }}
    .topline {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }}
    .badge {{ background: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 999px; padding: 3px 10px; font-size: 12px; }}
    .note {{ margin: 8px 0; font-size: 12px; color: #92400e; }}
    .legend {{ margin: 10px 0 14px; font-size: 12px; display: flex; gap: 12px; flex-wrap: wrap; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid #cbd5e1; background: #fff; }}
    table {{ border-collapse: collapse; min-width: 960px; width: 100%; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 6px; vertical-align: top; }}
    thead th {{ position: sticky; top: 0; background: #f1f5f9; z-index: 2; }}
    th.image-col, td.image-cell {{ position: sticky; left: 0; background: #fff; z-index: 1; min-width: 260px; max-width: 260px; }}
    th.mode-col, td.mode-cell {{ position: sticky; left: 260px; background: #fff; z-index: 1; min-width: 90px; }}
    thead th.image-col, thead th.mode-col {{ z-index: 3; background: #f1f5f9; }}
    .model-col {{ min-width: 220px; }}
    .thumb {{ width: 100%; height: auto; object-fit: contain; display: block; border: 1px solid #d1d5db; background: #fff; margin-bottom: 6px; }}
    .thumb.missing {{ width: 100%; aspect-ratio: 3 / 2; border: 1px dashed #cbd5e1; display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 12px; }}
    .small {{ color: #64748b; font-size: 11px; word-break: break-word; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 4px; }}
    .chip {{ display: inline-block; border-radius: 999px; padding: 2px 7px; font-size: 11px; line-height: 1.2; border: 1px solid #cbd5e1; }}
    .chip.free {{ background: #eef2ff; border-color: #c7d2fe; }}
    .chip.ok {{ background: #ecfdf3; border-color: #bbf7d0; color: #166534; }}
    .chip.warn {{ background: #fef2f2; border-color: #fecaca; color: #991b1b; }}
    .chip.mono {{ font-family: Consolas, monospace; }}
    .group {{ margin-bottom: 6px; }}
    .label {{ font-size: 11px; color: #475569; margin-bottom: 3px; text-transform: lowercase; }}
    .state {{ font-size: 12px; }}
    .state.error {{ color: #b91c1c; }}
    .state.muted {{ color: #6b7280; }}
    tr.matrix-row:nth-child(6n + 1) td {{ border-top: 2px solid #94a3b8; }}
  </style>
</head>
<body>
  <h1>Answer matrix report</h1>
  <div class='topline'>
    <span class='badge'>run: {html.escape(run_dir.name)}</span>
    <span class='badge'>images: {len(image_order)}</span>
    <span class='badge'>models: {len(model_order)}</span>
    <span class='badge'>modes: {len(top_mode_sequence)}</span>
    <span class='badge'>requests: {request_count}</span>
    <span class='badge'>errors: {error_count}</span>
    <span class='badge'>pool violations: {pool_violations}</span>
    {diagnostics_link}
  </div>
  {duplicate_note}
  <div class='legend'>
    <span>Mode labels: RU/EN free, pool, pool+ (ID-based)</span>
    <span>{_render_chip('free-mode tag', 'free')}</span>
    <span>{_render_chip('pool match', 'ok')}</span>
    <span>{_render_chip('out of pool', 'warn')}</span>
    <span>Empty cells mean no rendered tags for that request.</span>
  </div>
  <div class='table-wrap'>
    <table>
      <thead>
        <tr>
          <th class='image-col'>Image</th>
          <th class='mode-col'>Mode</th>
          {header_cells}
        </tr>
      </thead>
      <tbody>
        {''.join(body_rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
    report_path = run_dir / "report.html"
    report_path.write_text(html_text, encoding="utf-8")
    return report_path


def _yn(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "-"


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def build_diagnostics_report(run_dir: Path) -> Path | None:
    diagnostics_path = run_dir / "diagnostics.json"
    if not diagnostics_path.exists():
        return None
    try:
        data = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    run = data.get("run") or {}
    models = data.get("models") or []
    requests = data.get("requests") or []
    pools = data.get("pools") or {}
    warnings = data.get("warnings") or []

    model_rows = []
    for item in models:
        model_rows.append(
            "<tr>"
            f"<td>{_escape(item.get('model_label'))}</td>"
            f"<td>{_escape(item.get('params'))}</td>"
            f"<td>{_escape(item.get('quant'))}</td>"
            f"<td>{_yn(item.get('load_ok'))}</td>"
            f"<td>{_escape(item.get('load_duration_sec'))}</td>"
            f"<td>{_yn(item.get('smoke_test_ok'))}</td>"
            f"<td>{_escape(item.get('request_count'))}</td>"
            f"<td>{_escape(item.get('error_count'))}</td>"
            f"<td>{_escape(item.get('pool_violation_count'))}</td>"
            f"<td>{_escape(item.get('avg_latency_sec'))}</td>"
            f"<td>{_escape(item.get('median_latency_sec'))}</td>"
            f"<td>{_escape(item.get('min_latency_sec'))}</td>"
            f"<td>{_escape(item.get('max_latency_sec'))}</td>"
            f"<td>{_escape(item.get('parse_ok_rate'))}</td>"
            f"<td>{_escape(item.get('schema_ok_rate'))}</td>"
            f"<td>{_escape(item.get('pool_ok_rate'))}</td>"
            f"<td>{_escape(item.get('requested_context_length'))}</td>"
            f"<td>{_escape(item.get('actual_context_length'))}</td>"
            f"<td>{_yn(item.get('unload_ok'))}</td>"
            "</tr>"
        )

    request_rows = []
    for item in requests:
        request_rows.append(
            "<tr>"
            f"<td>{_escape(item.get('image_id'))}</td>"
            f"<td>{_escape(item.get('mode'))}</td>"
            f"<td>{_escape(item.get('model_label'))}</td>"
            f"<td>{_escape(item.get('latency_sec'))}</td>"
            f"<td>{_escape(item.get('response_format_requested'))}</td>"
            f"<td>{_escape(item.get('response_format_used'))}</td>"
            f"<td>{_yn(item.get('parse_ok'))}</td>"
            f"<td>{_yn(item.get('schema_ok'))}</td>"
            f"<td>{_yn(item.get('pool_ok'))}</td>"
            f"<td>{_escape(item.get('pool_violations'))}</td>"
            f"<td>{_escape(item.get('error_type'))}</td>"
            f"<td>{_escape(item.get('finish_reason'))}</td>"
            f"<td>{_escape(item.get('prompt_tokens'))}</td>"
            f"<td>{_escape(item.get('completion_tokens'))}</td>"
            f"<td>{_escape(item.get('total_tokens'))}</td>"
            f"<td>{_yn(item.get('context_near_limit'))}</td>"
            f"<td>{_yn(item.get('context_overflow'))}</td>"
            f"<td>{_yn(item.get('output_truncated'))}</td>"
            f"<td>{_escape(item.get('accepted_tag_count'))}</td>"
            f"<td>{_escape(item.get('rejected_tag_count'))}</td>"
            f"<td>{_escape(item.get('rejected_id_count'))}</td>"
            f"<td>{_escape(item.get('output_source'))}</td>"
            f"<td>{_yn(item.get('content_empty'))}</td>"
            f"<td>{_yn(item.get('reasoning_content_used'))}</td>"
            f"<td>{_escape(item.get('content_length'))}</td>"
            f"<td>{_escape(item.get('reasoning_content_length'))}</td>"
            f"<td><a href='{_escape(item.get('raw_path'))}'>raw</a></td>"
            f"<td><a href='{_escape(item.get('normalized_path'))}'>normalized</a></td>"
            "</tr>"
        )

    pool_rows = []
    for key, item in pools.items():
        pool_rows.append(
            "<tr>"
            f"<td>{_escape(key)}</td>"
            f"<td>{_escape(item.get('path'))}</td>"
            f"<td>{_escape(item.get('type'))}</td>"
            f"<td>{_escape(item.get('tag_count'))}</td>"
            f"<td>{_escape(item.get('entry_count'))}</td>"
            f"<td>{_escape(', '.join(item.get('id_prefixes') or []))}</td>"
            f"<td>{_escape(item.get('sha256'))}</td>"
            "</tr>"
        )

    warning_rows = []
    for item in warnings:
        key = item.get("key") or {}
        warning_rows.append(
            "<tr>"
            f"<td>{_escape(item.get('type'))}</td>"
            f"<td>{_escape(key.get('image_id'))}</td>"
            f"<td>{_escape(key.get('mode'))}</td>"
            f"<td>{_escape(key.get('model_label'))}</td>"
            f"<td>{_escape(item.get('count'))}</td>"
            f"<td>{_escape(item.get('used_request_id'))}</td>"
            "</tr>"
        )

    errors_log = ""
    errors_log_path = run_dir / "errors.log"
    if errors_log_path.exists():
        errors_log = html.escape(errors_log_path.read_text(encoding="utf-8"))

    diagnostics_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Local VLM Diagnostics Report</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 16px; background: #f8fafc; color: #1f2937; }}
    h1, h2 {{ margin: 0 0 10px; }}
    .links {{ margin: 8px 0 16px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; background: #fff; }}
    th, td {{ border: 1px solid #dbe2ea; padding: 5px; vertical-align: top; }}
    th {{ background: #eef2f7; position: sticky; top: 0; }}
    .wrap {{ overflow-x: auto; border: 1px solid #cbd5e1; margin-bottom: 14px; }}
    .summary {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
    .badge {{ border: 1px solid #cbd5e1; border-radius: 999px; padding: 2px 10px; background: #fff; font-size: 12px; }}
    pre {{ background: #fff; border: 1px solid #cbd5e1; padding: 10px; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Diagnostics report</h1>
  <div class="links"><a href="report.html">Back to answer matrix</a></div>
  <div class="summary">
    <span class="badge">run: {_escape(run.get("run_id"))}</span>
    <span class="badge">started: {_escape(run.get("started_at"))}</span>
    <span class="badge">finished: {_escape(run.get("finished_at"))}</span>
    <span class="badge">duration: {_escape(run.get("duration_sec"))}</span>
    <span class="badge">models: {_escape(run.get("model_count"))}</span>
    <span class="badge">images: {_escape(run.get("image_count"))}</span>
    <span class="badge">modes: {_escape(run.get("mode_count"))}</span>
    <span class="badge">requests: {_escape(run.get("request_count"))}</span>
    <span class="badge">errors: {_escape(run.get("error_count"))}</span>
    <span class="badge">pool violations: {_escape(run.get("pool_violation_count"))}</span>
    <span class="badge">git: {_escape(run.get("git_commit"))}</span>
  </div>

  <h2>Model diagnostics</h2>
  <div class="wrap"><table><thead><tr><th>model</th><th>params</th><th>quant</th><th>load ok</th><th>load sec</th><th>smoke</th><th>req</th><th>errors</th><th>pool viol</th><th>avg</th><th>median</th><th>min</th><th>max</th><th>parse rate</th><th>schema rate</th><th>pool rate</th><th>ctx req</th><th>ctx actual</th><th>unload ok</th></tr></thead><tbody>{''.join(model_rows)}</tbody></table></div>

  <h2>Request diagnostics</h2>
  <div class="wrap"><table><thead><tr><th>image</th><th>mode</th><th>model</th><th>latency</th><th>fmt req</th><th>fmt used</th><th>parse</th><th>schema</th><th>pool</th><th>viol</th><th>error type</th><th>finish</th><th>p tok</th><th>c tok</th><th>t tok</th><th>ctx near</th><th>ctx overflow</th><th>trunc</th><th>ok tags</th><th>rej tags</th><th>rej ids</th><th>output src</th><th>content empty</th><th>reasoning used</th><th>content len</th><th>reasoning len</th><th>raw</th><th>normalized</th></tr></thead><tbody>{''.join(request_rows)}</tbody></table></div>

  <h2>Pool diagnostics</h2>
  <div class="wrap"><table><thead><tr><th>pool</th><th>path</th><th>type</th><th>tag count</th><th>entry count</th><th>id prefixes</th><th>sha256</th></tr></thead><tbody>{''.join(pool_rows)}</tbody></table></div>

  <h2>Warnings</h2>
  <div class="wrap"><table><thead><tr><th>type</th><th>image</th><th>mode</th><th>model</th><th>count</th><th>used request id</th></tr></thead><tbody>{''.join(warning_rows)}</tbody></table></div>

  <h2>Error log</h2>
  <pre>{errors_log or 'not available'}</pre>
</body>
</html>
"""
    out_path = run_dir / "diagnostics.html"
    out_path.write_text(diagnostics_html, encoding="utf-8")
    return out_path
