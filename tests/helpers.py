from __future__ import annotations

from pathlib import Path

import yaml


def write_minimal_pools(base: Path) -> None:
    pools = base / "pools"
    pools.mkdir(parents=True, exist_ok=True)
    (pools / "ru_plain.txt").write_text("кот\n#comment\nсобака\n", encoding="utf-8")
    (pools / "en_plain.txt").write_text("cat\ndog\n", encoding="utf-8")
    (pools / "ru_explained_ids.tsv").write_text(
        "RU001\tОбщий\tБезопасно\nRU002\tАниме\tЯпонский стиль\n",
        encoding="utf-8",
    )
    (pools / "en_explained_ids.tsv").write_text(
        "EN001\tGeneral\tSafe\nEN002\tAnime\tJapanese style\n",
        encoding="utf-8",
    )


def write_minimal_images(base: Path) -> None:
    img_dir = base / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    # Minimal JPEG header bytes to exist as files; image opening is mocked in tests where needed.
    (img_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (img_dir / "B.PNG").write_bytes(b"\x89PNG\r\n\x1a\n")
    nested = img_dir / "nested"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "c.webp").write_bytes(b"RIFFxxxxWEBP")


def build_config(base: Path) -> Path:
    write_minimal_pools(base)
    write_minimal_images(base)
    results = base / "results"
    results.mkdir(parents=True, exist_ok=True)
    cfg = {
        "lmstudio": {
            "host": "http://localhost:1234",
            "api_base_url": "http://localhost:1234/api/v1",
            "openai_base_url": "http://localhost:1234/v1",
            "api_key": "lm-studio",
        },
        "models": [
            {
                "id": "m1@q4",
                "base_model_id": "m1",
                "label": "m1_q4",
                "params": "4B",
                "quant": "Q4",
                "quant_bits": 4,
                "max_context_length": 8192,
            }
        ],
        "input": {
            "image_dir": str((base / "images").resolve()),
            "recursive": False,
            "extensions": [".jpg", ".jpeg", ".png", ".webp", ".bmp"],
        },
        "output": {"results_dir": str(results.resolve())},
        "modes": ["ru_free", "ru_pool", "ru_pool_explained", "en_free", "en_pool", "en_pool_explained"],
        "pools": {
            "ru_plain": "pools/ru_plain.txt",
            "en_plain": "pools/en_plain.txt",
            "ru_explained": "pools/ru_explained_ids.tsv",
            "en_explained": "pools/en_explained_ids.tsv",
        },
        "generation": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 64},
        "load": {
            "context_length": 4096,
            "flash_attention": True,
            "offload_kv_cache_to_gpu": True,
            "echo_load_config": True,
        },
        "limits": {"max_tags": 10, "timeout_sec": 30, "retries": 1, "limit_images": None},
        "response_formats": {
            "free_modes": {"primary": "strict_json", "fallback": "line_tags"},
            "plain_pool_modes": {"primary": "strict_json", "fallback": "line_tags"},
            "explained_pool_modes": {"primary": "line_ids", "fallback": None},
        },
        "validation": {
            "use_response_format": True,
            "allow_json_extraction": True,
            "allow_line_fallback": True,
            "drop_tags_not_in_pool": True,
            "save_invalid_results": True,
        },
        "diagnostics": {
            "gpu_memory": {"enabled": True, "command": "nvidia-smi", "fail_if_unavailable": False},
            "context": {
                "record_usage_tokens": True,
                "warning_ratio": 0.85,
                "error_ratio": 0.97,
                "classify_context_errors": True,
            },
        },
        "runtime": {
            "unload_model_after_run": True,
            "resume": True,
            "skip_existing_success": True,
            "retry_existing_errors": True,
            "sleep_after_load_sec": 0,
            "image_request_smoke_test": True,
        },
        "report": {"generate_csv": True, "generate_html": True, "open_html_after_run": False, "thumbnail_size": 64},
        "evaluation": {
            "track_quality_for_manual_review": True,
            "track_speed": True,
            "track_json_stability": True,
            "track_pool_compliance": True,
            "track_hallucinated_tags": True,
        },
    }
    path = base / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path

