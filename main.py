from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import BenchmarkConfig, ConfigError, load_config
from src.collect import collect_run, ensure_collected
from src.image_loader import discover_images
from src.lmstudio_client import LMStudioClient, LMStudioClientError
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


def cmd_list_models(args: argparse.Namespace) -> int:
    cfg = _load_validated_config(args.config)
    client = LMStudioClient.from_config(cfg)
    try:
        models = client.list_models()
    except LMStudioClientError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"LM Studio models: {len(models)}")
    for model in models:
        model_id = (
            model.get("id")
            or model.get("model_id")
            or model.get("selected_variant")
            or model.get("key")
            or "<unknown>"
        )
        print(f"- {model_id}")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    cfg = _load_validated_config(args.config)
    images = discover_images(cfg, limit=args.limit)
    print(f"Models configured: {len(cfg.models)}")
    print(f"Modes configured: {len(cfg.modes)} ({', '.join(cfg.modes)})")
    print(f"Images discovered: {len(images)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load_validated_config(args.config)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local VLM image tagger benchmark")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-config", help="Validate config file")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=cmd_validate_config)

    list_models = sub.add_parser("list-models", help="List models from LM Studio")
    list_models.add_argument("--config", required=True)
    list_models.set_defaults(func=cmd_list_models)

    dry_run = sub.add_parser("dry-run", help="Validate inputs and print run plan")
    dry_run.add_argument("--config", required=True)
    dry_run.add_argument("--limit", type=int, default=None)
    dry_run.set_defaults(func=cmd_dry_run)

    run = sub.add_parser("run", help="Execute benchmark")
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
