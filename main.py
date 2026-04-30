from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import BenchmarkConfig, ConfigError, load_config
from src.collect import collect_run, ensure_collected
from src.image_loader import discover_images
from src.init_config import InitConfigError, render_user_config, write_user_config
from src.lmstudio_client import LMStudioClient, LMStudioClientError
from src.model_registry import ModelRegistryError, list_registry_labels, load_registry, refresh_registry
from src.report import build_diagnostics_report, build_report
from src.runner import run_benchmark
from src.validator import ValidationError, validate_config


def _load_validated_config(config_path: str) -> BenchmarkConfig:
    try:
        cfg = load_config(config_path)
        validate_config(cfg)
        return cfg
    except (ConfigError, ValidationError) as exc:
        raise SystemExit(str(exc)) from exc


def cmd_validate_config(args: argparse.Namespace) -> int:
    _load_validated_config(args.config)
    print(f"Config loaded: {args.config}")
    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
    try:
        registry = refresh_registry()
    except LMStudioClientError:
        raise SystemExit(
            "Failed to connect to LM Studio at http://localhost:1234/api/v1.\n"
            "Start LM Studio server and run `python main.py init-config` again."
        )

    output_path = Path(args.output)
    try:
        content = render_user_config(registry, images_folder=args.images_folder)
        write_user_config(output_path, content, force=args.force)
    except InitConfigError as exc:
        raise SystemExit(str(exc)) from exc

    print("Model registry written: models.registry.yaml")
    print(f"Config written: {output_path}")
    print("Edit models/modes by commenting or uncommenting list items, then run:")
    print(f"  python main.py dry-run --config {output_path}")
    print(f"  python main.py run --config {output_path}")
    return 0


def cmd_list_models(args: argparse.Namespace) -> int:
    try:
        registry = load_registry()
    except ModelRegistryError:
        print("models.registry.yaml not found. Run `python main.py init-config` or `python main.py refresh-models` first.")
        return 0

    labels = list_registry_labels(registry)
    print("Available model labels:")
    for label in labels:
        print(f"- {label}")
    if args.verbose:
        print("")
        print("Details:")
        for item in registry.models:
            label = item.get("label")
            model_id = item.get("id")
            reasoning = item.get("reasoning")
            params = item.get("params")
            quant = item.get("quant")
            max_ctx = item.get("max_context_length")
            print(f"- {label}: id={model_id}, reasoning={reasoning}, params={params}, quant={quant}, max_ctx={max_ctx}")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    cfg = _load_validated_config(args.config)
    images = discover_images(cfg, limit=args.limit)
    print("Mode: dry-run (validation and planning only; no LM Studio inference requests)")
    print(f"Config: {args.config}")
    print(f"Images discovered: {len(images)}")
    print(f"Models selected: {len(cfg.models)}")
    print(f"Modes selected: {len(cfg.modes)}")
    print(f"Total requests: {len(images) * len(cfg.models) * len(cfg.modes)}")
    print("")
    print("Models:")
    for model in cfg.models:
        print(f"- {model.label}")
    print("")
    print("Modes:")
    for mode in cfg.modes:
        print(f"- {mode}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load_validated_config(args.config)
    print("Mode: run (executes LM Studio requests and writes benchmark artifacts)")
    run_dir = run_benchmark(cfg, limit=args.limit, run_id=args.run_id, force_lock=args.force_lock)
    print(f"Run completed: {run_dir}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    ensure_collected(run_dir, strict=False)
    report_path = build_report(run_dir)
    diagnostics_path = build_diagnostics_report(run_dir)
    print(f"Report generated: {report_path}")
    if diagnostics_path is not None:
        print(f"Diagnostics report generated: {diagnostics_path}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    result = collect_run(run_dir, write_reports=args.write_reports, strict=args.strict)
    print(f"Summary rebuilt: {result['summary_path']}")
    print(f"Diagnostics rebuilt: {result['diagnostics_path']}")
    if args.write_reports:
        print(f"Reports rebuilt in: {run_dir}")
    return 0


def cmd_refresh_models(args: argparse.Namespace) -> int:
    try:
        registry = refresh_registry()
    except LMStudioClientError:
        raise SystemExit(
            "Failed to connect to LM Studio at http://localhost:1234/api/v1.\n"
            "Start LM Studio server and run `python main.py refresh-models` again."
        )
    print("Model registry written: models.registry.yaml")
    print(f"Registry entries: {len(registry.models)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local VLM image tagger benchmark")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-config", help="Validate config file")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=cmd_validate_config)

    init_config = sub.add_parser("init-config", help="Generate human-friendly config.yaml")
    init_config.add_argument("--output", default="config.yaml")
    init_config.add_argument("--force", action="store_true")
    init_config.add_argument("--images-folder", default="ImgToTag")
    init_config.set_defaults(func=cmd_init_config)

    refresh_models = sub.add_parser("refresh-models", help="Refresh generated model registry from LM Studio")
    refresh_models.set_defaults(func=cmd_refresh_models)

    list_models = sub.add_parser("list-models", help="List model labels from models.registry.yaml")
    list_models.add_argument("--verbose", action="store_true")
    list_models.set_defaults(func=cmd_list_models)

    dry_run = sub.add_parser(
        "dry-run",
        help="Validate config/inputs and print planned request count (no model inference)",
    )
    dry_run.add_argument("--config", required=True)
    dry_run.add_argument("--limit", type=int, default=None)
    dry_run.set_defaults(func=cmd_dry_run)

    run = sub.add_parser("run", help="Execute benchmark with real LM Studio model requests")
    run.add_argument("--config", required=True)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--run-id", default=None)
    run.add_argument("--force-lock", action="store_true")
    run.set_defaults(func=cmd_run)

    report = sub.add_parser("report", help="Build HTML report for an existing run")
    report.add_argument("--run", required=True)
    report.set_defaults(func=cmd_report)

    collect = sub.add_parser("collect", help="Rebuild summary and diagnostics from request artifacts")
    collect.add_argument("--run", required=True)
    collect.add_argument("--write-reports", action="store_true")
    collect.add_argument("--strict", action="store_true")
    collect.set_defaults(func=cmd_collect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
