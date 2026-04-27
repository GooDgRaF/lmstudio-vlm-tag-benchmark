from __future__ import annotations

import csv

from src.report import build_report


def test_report_created_and_escaped(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "assets" / "thumbs").mkdir(parents=True, exist_ok=True)
    image = run_dir / "img.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd9")
    summary = run_dir / "summary.csv"
    with summary.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "run_id",
                "request_id",
                "model_label",
                "image_path",
                "mode",
                "accepted_tags",
                "rejected_tags",
                "rejected_ids",
                "latency_sec",
                "parse_ok",
                "schema_ok",
                "line_fallback_used",
                "pool_violations",
                "error_type",
                "error",
                "context_near_limit",
                "gpu_memory_before_mb",
                "gpu_memory_after_mb",
            ]
        )
        writer.writerow(
            [
                "run",
                "req1",
                "model<script>",
                str(image),
                "en_free",
                '["cat"]',
                '["<bad>"]',
                "[]",
                "0.2",
                "true",
                "true",
                "false",
                "0",
                "",
                "<boom>",
                "false",
                "100",
                "200",
            ]
        )
    report = build_report(run_dir)
    html = report.read_text(encoding="utf-8")
    assert report.exists()
    assert "&lt;boom&gt;" in html
    assert "model&lt;script&gt;" in html

