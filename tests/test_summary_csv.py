from __future__ import annotations

import csv

from src.config import load_config
from src.storage import create_run_storage
from tests.helpers import build_config


def test_summary_header_and_rows_and_json_cells(tmp_path):
    cfg = load_config(build_config(tmp_path))
    _, storage = create_run_storage(cfg, run_id="csvrun")
    storage.init_summary_csv()
    storage.append_summary_row(
        {
            "run_id": "csvrun",
            "request_id": "r1",
            "model_id": "m1",
            "base_model_id": "m1",
            "model_label": "m1_q4",
            "image_id": "img1",
            "image_path": "x",
            "image_rel_path": "a.jpg",
            "mode": "en_free",
            "prompt_version": "v1",
            "response_format_requested": "strict_json",
            "response_format_used": "strict_json",
            "accepted_tags": ["cat"],
            "accepted_ids": [],
            "rejected_tags": [],
            "rejected_ids": [],
            "tag_count": 1,
            "pool_violations": 0,
            "parse_ok": True,
            "schema_ok": True,
            "json_extracted": False,
            "line_fallback_used": False,
            "pool_ok": True,
            "latency_sec": 0.1,
            "error_type": None,
            "error": None,
        }
    )
    text = storage.summary_csv_path.read_text(encoding="utf-8-sig")
    assert "prompt_version" in text
    assert "image_rel_path" in text
    with storage.summary_csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["accepted_tags"] == '["cat"]'


def test_utf8_bom_written(tmp_path):
    cfg = load_config(build_config(tmp_path))
    _, storage = create_run_storage(cfg, run_id="csvbom")
    storage.init_summary_csv()
    raw = storage.summary_csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

