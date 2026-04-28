from __future__ import annotations

import csv
import json

from src.report import build_diagnostics_report, build_report


def _write_summary(path, rows):
    headers = [
        "run_id",
        "request_id",
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
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_report_matrix_and_escape(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "assets" / "thumbs").mkdir(parents=True, exist_ok=True)
    image = run_dir / "img.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd9")

    (run_dir / "models.json").write_text(
        json.dumps([
            {"label": "model-b"},
            {"label": "model-a<script>"},
        ]),
        encoding="utf-8",
    )
    (run_dir / "run_config.yaml").write_text("modes:\n  - ru_free\n  - en_pool\n", encoding="utf-8")

    rows = [
        {
            "run_id": "run",
            "request_id": "r1",
            "model_id": "m",
            "base_model_id": "b",
            "model_label": "model-a<script>",
            "params": "4B",
            "quant": "Q4",
            "quant_bits": "4",
            "image_id": "image-1",
            "image_path": str(image),
            "image_rel_path": "ImgToTag/img.jpg",
            "mode": "ru_free",
            "prompt_version": "v1",
            "response_format_requested": "strict_json",
            "response_format_used": "strict_json",
            "accepted_tags": '["cat", "<raw>"]',
            "accepted_ids": "[]",
            "rejected_tags": '["bad"]',
            "rejected_ids": '["EN001"]',
            "tag_count": "2",
            "pool_violations": "1",
            "parse_ok": "true",
            "schema_ok": "true",
            "json_extracted": "false",
            "line_fallback_used": "false",
            "pool_ok": "false",
            "latency_sec": "1.0",
            "prompt_tokens": "10",
            "completion_tokens": "2",
            "total_tokens": "12",
            "requested_context_length": "16000",
            "actual_context_length": "16000",
            "context_near_limit": "false",
            "context_overflow": "false",
            "output_truncated": "false",
            "gpu_memory_before_mb": "100",
            "gpu_memory_after_mb": "200",
            "error_type": "",
            "error": "",
        },
        {
            "run_id": "run",
            "request_id": "r2",
            "model_id": "m",
            "base_model_id": "b",
            "model_label": "model-b",
            "params": "4B",
            "quant": "Q4",
            "quant_bits": "4",
            "image_id": "image-1",
            "image_path": str(image),
            "image_rel_path": "ImgToTag/img.jpg",
            "mode": "ru_free",
            "prompt_version": "v1",
            "response_format_requested": "strict_json",
            "response_format_used": "strict_json",
            "accepted_tags": "[]",
            "accepted_ids": "[]",
            "rejected_tags": "[]",
            "rejected_ids": "[]",
            "tag_count": "0",
            "pool_violations": "0",
            "parse_ok": "false",
            "schema_ok": "false",
            "json_extracted": "false",
            "line_fallback_used": "false",
            "pool_ok": "true",
            "latency_sec": "1.5",
            "prompt_tokens": "10",
            "completion_tokens": "2",
            "total_tokens": "12",
            "requested_context_length": "16000",
            "actual_context_length": "16000",
            "context_near_limit": "true",
            "context_overflow": "false",
            "output_truncated": "false",
            "gpu_memory_before_mb": "100",
            "gpu_memory_after_mb": "200",
            "error_type": "request_error",
            "error": "<boom>",
        },
    ]
    _write_summary(run_dir / "summary.csv", rows)

    # Existing diagnostics page should be linked when present.
    (run_dir / "diagnostics.html").write_text("<html></html>", encoding="utf-8")

    report = build_report(run_dir)
    html = report.read_text(encoding="utf-8")

    assert report.exists()
    assert "Answer matrix report" in html
    assert "model-a&lt;script&gt;" in html
    assert "RU free" in html
    assert "class='chip ok'" in html
    assert "class='chip warn'" in html
    assert "rejected ids" in html
    assert "request_error: &lt;boom&gt;" in html
    assert "Diagnostics report" in html
    assert "prompt_tokens" not in html
    assert "gpu_memory_before_mb" not in html


def test_duplicate_rows_last_wins_and_not_run(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    image = run_dir / "img.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd9")
    (run_dir / "run_config.yaml").write_text("modes:\n  - ru_free\n  - en_free\n", encoding="utf-8")

    rows = [
        {
            "run_id": "run",
            "request_id": "dup-1",
            "model_id": "m",
            "base_model_id": "b",
            "model_label": "model-a",
            "params": "4B",
            "quant": "Q4",
            "quant_bits": "4",
            "image_id": "image-1",
            "image_path": str(image),
            "image_rel_path": "ImgToTag/img.jpg",
            "mode": "ru_free",
            "prompt_version": "v1",
            "response_format_requested": "strict_json",
            "response_format_used": "strict_json",
            "accepted_tags": '["old"]',
            "accepted_ids": "[]",
            "rejected_tags": "[]",
            "rejected_ids": "[]",
            "tag_count": "1",
            "pool_violations": "0",
            "parse_ok": "true",
            "schema_ok": "true",
            "json_extracted": "false",
            "line_fallback_used": "false",
            "pool_ok": "true",
            "latency_sec": "1.0",
            "prompt_tokens": "1",
            "completion_tokens": "1",
            "total_tokens": "2",
            "requested_context_length": "16000",
            "actual_context_length": "16000",
            "context_near_limit": "false",
            "context_overflow": "false",
            "output_truncated": "false",
            "gpu_memory_before_mb": "100",
            "gpu_memory_after_mb": "200",
            "error_type": "",
            "error": "",
        },
        {
            "run_id": "run",
            "request_id": "dup-2",
            "model_id": "m",
            "base_model_id": "b",
            "model_label": "model-a",
            "params": "4B",
            "quant": "Q4",
            "quant_bits": "4",
            "image_id": "image-1",
            "image_path": str(image),
            "image_rel_path": "ImgToTag/img.jpg",
            "mode": "ru_free",
            "prompt_version": "v1",
            "response_format_requested": "strict_json",
            "response_format_used": "strict_json",
            "accepted_tags": '["new"]',
            "accepted_ids": "[]",
            "rejected_tags": "[]",
            "rejected_ids": "[]",
            "tag_count": "1",
            "pool_violations": "0",
            "parse_ok": "true",
            "schema_ok": "true",
            "json_extracted": "false",
            "line_fallback_used": "false",
            "pool_ok": "true",
            "latency_sec": "1.0",
            "prompt_tokens": "1",
            "completion_tokens": "1",
            "total_tokens": "2",
            "requested_context_length": "16000",
            "actual_context_length": "16000",
            "context_near_limit": "false",
            "context_overflow": "false",
            "output_truncated": "false",
            "gpu_memory_before_mb": "100",
            "gpu_memory_after_mb": "200",
            "error_type": "",
            "error": "",
        },
    ]
    _write_summary(run_dir / "summary.csv", rows)

    html = build_report(run_dir).read_text(encoding="utf-8")
    assert "Duplicate request rows: 1" in html
    assert "new" in html
    assert "old" not in html
    assert "not run" in html


def test_diagnostics_html_and_cross_links(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    image = run_dir / "img.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd9")
    _write_summary(
        run_dir / "summary.csv",
        [
            {
                "run_id": "run",
                "request_id": "r1",
                "model_id": "m",
                "base_model_id": "b",
                "model_label": "model-a",
                "params": "4B",
                "quant": "Q4",
                "quant_bits": "4",
                "image_id": "image-1",
                "image_path": str(image),
                "image_rel_path": "ImgToTag/img.jpg",
                "mode": "en_free",
                "prompt_version": "v1",
                "response_format_requested": "strict_json",
                "response_format_used": "strict_json",
                "accepted_tags": '["cat"]',
                "accepted_ids": "[]",
                "rejected_tags": "[]",
                "rejected_ids": "[]",
                "tag_count": "1",
                "pool_violations": "0",
                "parse_ok": "true",
                "schema_ok": "true",
                "json_extracted": "false",
                "line_fallback_used": "false",
                "pool_ok": "true",
                "latency_sec": "1.0",
                "prompt_tokens": "1",
                "completion_tokens": "1",
                "total_tokens": "2",
                "requested_context_length": "16000",
                "actual_context_length": "16000",
                "context_near_limit": "false",
                "context_overflow": "false",
                "output_truncated": "false",
                "gpu_memory_before_mb": "100",
                "gpu_memory_after_mb": "200",
                "error_type": "",
                "error": "",
            }
        ],
    )
    (run_dir / "diagnostics.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run": {"run_id": "run"},
                "pools": {},
                "models": [{"model_label": "model-a"}],
                "requests": [{"image_id": "image-1", "mode": "en_free", "model_label": "model-a"}],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    diagnostics_path = build_diagnostics_report(run_dir)
    assert diagnostics_path is not None
    diagnostics_html = diagnostics_path.read_text(encoding="utf-8")
    report_html = build_report(run_dir).read_text(encoding="utf-8")
    assert "diagnostics.html" in report_html
    assert "Back to answer matrix" in diagnostics_html
