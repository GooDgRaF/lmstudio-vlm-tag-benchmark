from __future__ import annotations

from pathlib import Path

from src.model_registry import ModelRegistry, list_registry_labels

ALLOWED_MODES = [
    "ru_free",
    "ru_pool",
    "ru_pool_explained",
    "en_free",
    "en_pool",
    "en_pool_explained",
]


class InitConfigError(RuntimeError):
    """Init-config generation error."""


def _pick_default_model(labels: list[str]) -> str | None:
    if not labels:
        return None
    for label in labels:
        lower = label.lower()
        if "qwen3-vl-4b" in lower and "q4_k_m" in lower:
            return label
    return labels[0]


def render_user_config(registry: ModelRegistry, images_folder: str = "ImgToTag") -> str:
    labels = list_registry_labels(registry)
    default_model = _pick_default_model(labels)

    lines: list[str] = [
        "# Human-friendly config for Local VLM Image Tagger Benchmark.",
        "# Edit this file, then run:",
        "#   python main.py dry-run --config config.yaml   # validate config and show request plan only",
        "#   python main.py run --config config.yaml       # execute benchmark and write results/",
        "#",
        "# dry-run does not call model inference.",
        "# run performs real LM Studio requests and generates report artifacts.",
        "",
        "# Input image folder (relative or absolute path).",
        "# Example custom path: images_folder: \"D:/datasets/my_cards\"",
        f"images_folder: \"{images_folder}\"",
        "",
        "# 1 = quick smoke test",
        "# null = all images",
        "limit_images: 1",
        "",
        "models:",
    ]

    if default_model is None:
        lines.extend(
            [
                "  # No LM Studio models were found.",
                "  # Start the LM Studio server and run:",
                "  #   python main.py init-config --force",
            ]
        )
    else:
        for label in labels:
            quoted = f'\"{label}\"'
            if label == default_model:
                lines.append(f"  - {quoted}")
            else:
                lines.append(f"  # - {quoted}")

    lines.extend(["", "modes:"])
    for mode in ALLOWED_MODES:
        quoted = f'\"{mode}\"'
        if mode == "ru_free":
            lines.append(f"  - {quoted}")
        else:
            lines.append(f"  # - {quoted}")

    lines.extend(
        [
            "",
            "# Optional tag pool files (relative or absolute paths).",
            "# ru/en = plain pools, ru_plus/en_plus = ID-based pools (pool+ modes).",
            "# tag_files:",
            "#   ru: \"prompts/pools/ru_plain.txt\"",
            "#   ru_plus: \"prompts/pools/ru_explained_ids.tsv\"",
            "#   en: \"prompts/pools/en_plain.txt\"",
            "#   en_plus: \"prompts/pools/en_explained_ids.tsv\"",
            "",
            "# Optional per-mode prompt header files (relative or absolute paths).",
            "# mode_prompt_files:",
            "#   ru_free: \"prompts/ru_free.txt\"",
            "#   ru_pool: \"prompts/ru_pool.txt\"",
            "#   ru_pool_explained: \"prompts/ru_pool_explained.txt\"",
            "#   en_free: \"prompts/en_free.txt\"",
            "#   en_pool: \"prompts/en_pool.txt\"",
            "#   en_pool_explained: \"prompts/en_pool_explained.txt\"",
            "",
            "output_folder: \"results\"",
            "",
            "# Optional settings. Defaults are usually fine.",
            "# context_length: 8192",
            "# max_output_tokens: 4096",
            "# temperature: 0.0",
            "# recursive: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_user_config(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise InitConfigError(
            f"{path} already exists. Use --force to overwrite or --output <path> to write another file."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

