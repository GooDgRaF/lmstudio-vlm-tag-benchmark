from __future__ import annotations

import json
from pathlib import Path

from src.collect import collect_run, ensure_collected


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "results" / "r1"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": 1,
            "run_id": "r1",
            "config_path": "cfg.yaml",
            "request_count": 1,
            "requests": [
                {
                    "request_id": "req1",
                    "model_label": "m1",
                    "model_id": "m1@q4",
                    "base_model_id": "m1",
                    "image_id": "img1",
                    "image_rel_path": "img1.jpg",
                    "mode": "en_free",
                    "prompt_version": "v2",
                    "response_format_requested": "line_tags",
                }
            ],
        },
    )
    _write_json(run_dir / "models.json", [{"label": "m1", "params": "4B", "quant": "Q4", "quant_bits": 4, "base_model_id": "m1"}])
    _write_json(run_dir / "requests" / "req1" / "status.json", {"status": "success", "attempt": 1})
    _write_json(
        run_dir / "requests" / "req1" / "normalized.json",
        {
            "response_format_used": "line_tags",
            "accepted_tags": ["cat"],
            "accepted_ids": [],
            "rejected_tags": [],
            "rejected_ids": [],
            "pool_violations": 0,
            "parse_ok": True,
            "schema_ok": True,
            "json_extracted": False,
            "line_fallback_used": False,
            "pool_ok": True,
            "latency_sec": 0.12,
            "error_type": None,
            "error": None,
        },
    )
    _write_json(
        run_dir / "requests" / "req1" / "diagnostics.json",
        {
            "request_id": "req1",
            "model_label": "m1",
            "model_id": "m1@q4",
            "image_id": "img1",
            "image_rel_path": "img1.jpg",
            "mode": "en_free",
            "latency_sec": 0.12,
            "response_format_requested": "line_tags",
            "response_format_used": "line_tags",
            "parse_ok": True,
            "schema_ok": True,
            "pool_ok": True,
            "pool_violations": 0,
            "accepted_tag_count": 1,
            "rejected_tag_count": 0,
            "rejected_id_count": 0,
            "raw_path": "requests/req1/raw.json",
            "normalized_path": "requests/req1/normalized.json",
        },
    )
    _write_json(
        run_dir / "diagnostics.json",
        {"schema_version": 1, "run": {"run_id": "r1", "model_count": 1, "image_count": 1, "mode_count": 1}, "pools": {}, "models": [], "requests": [], "warnings": []},
    )
    return run_dir


def test_collect_rebuilds_summary_and_diagnostics(tmp_path):
    run_dir = _prepare_run(tmp_path)
    result = collect_run(run_dir)
    assert result["summary_path"].exists()
    assert result["diagnostics_path"].exists()
    text = result["summary_path"].read_text(encoding="utf-8-sig")
    assert "req1" in text
    diagnostics = json.loads(result["diagnostics_path"].read_text(encoding="utf-8"))
    assert diagnostics["run"]["is_partial"] is True
    assert diagnostics["run"]["completed_request_count"] == 1


def test_collect_treats_skipped_status_as_existing_result(tmp_path):
    run_dir = _prepare_run(tmp_path)
    _write_json(run_dir / "requests" / "req1" / "status.json", {"status": "skipped", "attempt": 1})

    result = collect_run(run_dir)

    import csv

    rows = list(csv.DictReader(result["summary_path"].open(encoding="utf-8-sig", newline="")))
    assert rows[0]["status"] == "success"
    diagnostics = json.loads(result["diagnostics_path"].read_text(encoding="utf-8"))
    assert diagnostics["run"]["successful_attempt_count"] == 1


def test_collect_marks_incomplete_request(tmp_path):
    run_dir = _prepare_run(tmp_path)
    (run_dir / "requests" / "req1" / "status.json").unlink()
    result = collect_run(run_dir)
    diagnostics = json.loads(result["diagnostics_path"].read_text(encoding="utf-8"))
    warning_types = [item.get("type") for item in diagnostics["warnings"]]
    assert "incomplete_request" in warning_types


def test_ensure_collected_rebuilds_when_missing(tmp_path):
    run_dir = _prepare_run(tmp_path)
    (run_dir / "summary.csv").unlink(missing_ok=True)
    (run_dir / "diagnostics.json").unlink(missing_ok=True)
    ensure_collected(run_dir)
    assert (run_dir / "summary.csv").exists()
    assert (run_dir / "diagnostics.json").exists()


def test_collect_accumulate_includes_multiple_attempts(tmp_path):
    run_dir = _prepare_run(tmp_path)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["result_mode"] = "accumulate"
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    req_dir = run_dir / "requests" / "req1"
    (req_dir / "status.json").unlink(missing_ok=True)
    (req_dir / "normalized.json").unlink(missing_ok=True)
    (req_dir / "diagnostics.json").unlink(missing_ok=True)
    a1 = req_dir / "attempts" / "001"
    a2 = req_dir / "attempts" / "002"
    _write_json(a1 / "status.json", {"status": "failed", "attempt": 1, "error_type": "request_error"})
    _write_json(a1 / "normalized.json", {"accepted_tags": [], "rejected_tags": [], "rejected_ids": [], "accepted_ids": [], "pool_ok": True, "pool_violations": 0, "parse_ok": False, "schema_ok": False, "json_extracted": False, "line_fallback_used": False, "error_type": "request_error"})
    _write_json(a2 / "status.json", {"status": "success", "attempt": 2})
    _write_json(a2 / "normalized.json", {"accepted_tags": ["cat"], "rejected_tags": [], "rejected_ids": [], "accepted_ids": [], "pool_ok": True, "pool_violations": 0, "parse_ok": True, "schema_ok": True, "json_extracted": False, "line_fallback_used": False, "error_type": None})
    result = collect_run(run_dir)
    summary = result["summary_path"].read_text(encoding="utf-8-sig")
    assert summary.count("req1") >= 2
    diagnostics = json.loads(result["diagnostics_path"].read_text(encoding="utf-8"))
    assert diagnostics["run"]["attempt_count"] == 2
    assert diagnostics["run"]["successful_attempt_count"] == 1


def test_collect_preserves_rest_reasoning_fields(tmp_path):
    run_dir = _prepare_run(tmp_path)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["requests"][0]["transport"] = "rest"
    manifest["requests"][0]["reasoning_requested"] = "on"
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_json(
        run_dir / "requests" / "req1" / "normalized.json",
        {
            "response_format_used": "line_tags",
            "accepted_tags": ["cat"],
            "accepted_ids": [],
            "rejected_tags": [],
            "rejected_ids": [],
            "pool_violations": 0,
            "parse_ok": True,
            "schema_ok": True,
            "json_extracted": False,
            "line_fallback_used": False,
            "pool_ok": True,
            "latency_sec": 0.12,
            "transport": "rest",
            "reasoning_requested": "on",
            "final_content_empty": False,
            "final_content_length": 3,
            "reasoning_content_present": True,
            "reasoning_content_length": 100,
            "reasoning_tokens": 25,
            "no_final_answer": False,
            "output_truncated": True,
            "error_type": None,
            "error": None,
        },
    )
    result = collect_run(run_dir)
    import csv

    row = next(csv.DictReader(result["summary_path"].open(encoding="utf-8-sig", newline="")))
    assert row["transport"] == "rest"
    assert row["reasoning_requested"] == "on"
    assert row["reasoning_tokens"] == "25"
    assert row["output_truncated"].lower() == "true"


def test_collect_fills_image_path_from_request_descriptor(tmp_path):
    run_dir = _prepare_run(tmp_path)
    _write_json(
        run_dir / "requests" / "req1" / "request.json",
        {
            "request_id": "req1",
            "image_path": "C:/tmp/image.jpg",
            "image_rel_path": "img1.jpg",
        },
    )
    result = collect_run(run_dir)
    import csv

    row = next(csv.DictReader(result["summary_path"].open(encoding="utf-8-sig", newline="")))
    assert row["image_path"] == "C:/tmp/image.jpg"


def test_collect_reparses_raw_with_current_parser(tmp_path):
    run_dir = _prepare_run(tmp_path)
    pools = tmp_path / "pools"
    pools.mkdir()
    (pools / "en_plain.txt").write_text("cat\ndog\n", encoding="utf-8")
    (pools / "ru_plain.txt").write_text("кот\n", encoding="utf-8")
    (pools / "en_explained_ids.tsv").write_text("EN001\tGeneral\tSafe\n", encoding="utf-8")
    (pools / "ru_explained_ids.tsv").write_text("RU001\tОбщий\tБезопасно\n", encoding="utf-8")
    (run_dir / "run_config.yaml").write_text(
        "\n".join(
            [
                "pools:",
                f"  ru_plain: {pools / 'ru_plain.txt'}",
                f"  en_plain: {pools / 'en_plain.txt'}",
                f"  ru_explained: {pools / 'ru_explained_ids.tsv'}",
                f"  en_explained: {pools / 'en_explained_ids.tsv'}",
                "limits:",
                "  max_tags: 10",
                "validation:",
                "  allow_json_extraction: true",
                "  allow_line_fallback: true",
                "  drop_tags_not_in_pool: true",
            ]
        ),
        encoding="utf-8",
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["requests"][0]["mode"] = "en_pool"
    manifest["requests"][0]["response_format_requested"] = "line_tags"
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_json(
        run_dir / "requests" / "req1" / "status.json",
        {"status": "failed", "attempt": 1, "error_type": "pool_validation_failed"},
    )
    _write_json(
        run_dir / "requests" / "req1" / "raw.json",
        {
            "final_content": (
                "The user wants me to generate image tags.\n"
                "1. **Analyze the image:** cat and dog are visible.\n"
                "Tags selected: cat, invented\n"
                "\n"
                "Final selection based on rules:\n"
                "cat\n"
                "dog"
            ),
            "mode": "en_pool",
            "response_format_used": "line_tags",
        },
    )
    _write_json(
        run_dir / "requests" / "req1" / "normalized.json",
        {
            "response_format_requested": "line_tags",
            "response_format_used": "line_tags",
            "accepted_tags": ["cat"],
            "accepted_ids": [],
            "rejected_tags": ["invented"],
            "rejected_ids": [],
            "pool_violations": 1,
            "parse_ok": True,
            "schema_ok": True,
            "json_extracted": False,
            "line_fallback_used": False,
            "pool_ok": False,
            "error_type": "pool_validation_failed",
            "error": "old",
        },
    )

    result = collect_run(run_dir)

    import csv

    row = next(csv.DictReader(result["summary_path"].open(encoding="utf-8-sig", newline="")))
    assert row["status"] == "success"
    assert row["accepted_tags"] == '["cat", "dog"]'
    assert row["rejected_tags"] == "[]"
    assert row["reasoning_leak_detected"].lower() == "true"
    assert row["reasoning_leak_recovered"].lower() == "true"
