from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from src.user_config import UserConfigError, detect_config_style, expand_user_config


class ConfigError(RuntimeError):
    """Configuration loading error."""


@dataclass(frozen=True)
class LMStudioConfig:
    host: str
    api_base_url: str
    openai_base_url: str
    api_key: str


@dataclass(frozen=True)
class ModelConfig:
    id: str
    base_model_id: str
    label: str
    params: str | None
    quant: str | None
    quant_bits: int | None
    max_context_length: int | None
    reasoning: str = "default"
    display_name: str | None = None
    architecture: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class InputConfig:
    image_dir: str
    recursive: bool
    extensions: list[str]


@dataclass(frozen=True)
class OutputConfig:
    results_dir: str


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    top_p: float
    max_tokens: int


@dataclass(frozen=True)
class LoadConfig:
    context_length: int | None
    flash_attention: bool | None
    offload_kv_cache_to_gpu: bool | None
    echo_load_config: bool | None

    def as_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None}


@dataclass(frozen=True)
class LimitsConfig:
    timeout_sec: int
    retries: int
    limit_images: int | None


@dataclass(frozen=True)
class ResponseFormatsByMode:
    primary: str
    fallback: str | None


@dataclass(frozen=True)
class ResponseFormatsConfig:
    free_modes: ResponseFormatsByMode
    plain_pool_modes: ResponseFormatsByMode
    explained_pool_modes: ResponseFormatsByMode


@dataclass(frozen=True)
class ValidationConfig:
    use_response_format: bool
    allow_json_extraction: bool
    allow_line_fallback: bool
    drop_tags_not_in_pool: bool
    save_invalid_results: bool


@dataclass(frozen=True)
class GPUDiagnosticsConfig:
    enabled: bool
    command: str
    fail_if_unavailable: bool


@dataclass(frozen=True)
class ContextDiagnosticsConfig:
    record_usage_tokens: bool
    warning_ratio: float
    error_ratio: float
    classify_context_errors: bool


@dataclass(frozen=True)
class DiagnosticsConfig:
    gpu_memory: GPUDiagnosticsConfig
    context: ContextDiagnosticsConfig


@dataclass(frozen=True)
class RuntimeConfig:
    result_mode: str
    unload_model_after_run: bool
    resume: bool
    retry_failed: bool
    sleep_after_load_sec: float
    image_request_smoke_test: bool


@dataclass(frozen=True)
class ReportConfig:
    generate_csv: bool
    generate_html: bool
    open_html_after_run: bool
    thumbnail_size: int


@dataclass(frozen=True)
class PoolsConfig:
    ru_plain: str
    en_plain: str
    ru_explained: str
    en_explained: str


@dataclass(frozen=True)
class PromptFilesConfig:
    ru_free: str
    ru_pool: str
    ru_pool_explained: str
    en_free: str
    en_pool: str
    en_pool_explained: str


@dataclass(frozen=True)
class BenchmarkConfig:
    config_path: Path
    root_dir: Path
    lmstudio: LMStudioConfig
    models: list[ModelConfig]
    input: InputConfig
    output: OutputConfig
    modes: list[str]
    pools: PoolsConfig
    prompt_files: PromptFilesConfig
    generation: GenerationConfig
    load: LoadConfig
    limits: LimitsConfig
    response_formats: ResponseFormatsConfig
    validation: ValidationConfig
    diagnostics: DiagnosticsConfig
    runtime: RuntimeConfig
    report: ReportConfig
    evaluation: dict[str, Any]
    raw: dict[str, Any]

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.root_dir / path).resolve()

    def to_serializable_dict(self) -> dict[str, Any]:
        return self.raw


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"Config section '{key}' is missing or not an object")
    return value


def _required_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"Config section '{key}' is missing or not a list")
    return value


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def load_config(config_path: str | Path) -> BenchmarkConfig:
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")

    try:
        loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML config: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ConfigError("Config root must be a YAML mapping")

    try:
        style = detect_config_style(loaded)
        if style == "simple":
            loaded = expand_user_config(loaded, root_dir=cfg_path.resolve().parent)
    except UserConfigError as exc:
        raise ConfigError(str(exc)) from exc

    lmstudio_raw = _required_dict(loaded, "lmstudio")
    models_raw = _required_list(loaded, "models")
    input_raw = _required_dict(loaded, "input")
    output_raw = _required_dict(loaded, "output")
    pools_raw = _required_dict(loaded, "pools")
    prompt_files_raw = _required_dict(loaded, "prompt_files")
    generation_raw = _required_dict(loaded, "generation")
    load_raw = _required_dict(loaded, "load")
    limits_raw = _required_dict(loaded, "limits")
    response_formats_raw = _required_dict(loaded, "response_formats")
    validation_raw = _required_dict(loaded, "validation")
    diagnostics_raw = _required_dict(loaded, "diagnostics")
    runtime_raw = _required_dict(loaded, "runtime")
    report_raw = _required_dict(loaded, "report")

    models: list[ModelConfig] = []
    for entry in models_raw:
        if not isinstance(entry, dict):
            raise ConfigError("Each model entry must be an object")
        models.append(
            ModelConfig(
                id=str(entry.get("id", "")),
                base_model_id=str(entry.get("base_model_id", "")),
                label=str(entry.get("label", "")),
                reasoning=str(entry.get("reasoning", "default")),
                params=entry.get("params"),
                quant=entry.get("quant"),
                quant_bits=_coerce_int(entry.get("quant_bits")),
                max_context_length=_coerce_int(entry.get("max_context_length")),
                display_name=entry.get("display_name"),
                architecture=entry.get("architecture"),
                size_bytes=_coerce_int(entry.get("size_bytes")),
            )
        )

    response_formats = ResponseFormatsConfig(
        free_modes=ResponseFormatsByMode(
            primary=str(_required_dict(response_formats_raw, "free_modes").get("primary")),
            fallback=_required_dict(response_formats_raw, "free_modes").get("fallback"),
        ),
        plain_pool_modes=ResponseFormatsByMode(
            primary=str(_required_dict(response_formats_raw, "plain_pool_modes").get("primary")),
            fallback=_required_dict(response_formats_raw, "plain_pool_modes").get("fallback"),
        ),
        explained_pool_modes=ResponseFormatsByMode(
            primary=str(_required_dict(response_formats_raw, "explained_pool_modes").get("primary")),
            fallback=_required_dict(response_formats_raw, "explained_pool_modes").get("fallback"),
        ),
    )

    gpu_raw = _required_dict(diagnostics_raw, "gpu_memory")
    context_raw = _required_dict(diagnostics_raw, "context")

    cfg = BenchmarkConfig(
        config_path=cfg_path.resolve(),
        root_dir=cfg_path.resolve().parent,
        lmstudio=LMStudioConfig(
            host=str(lmstudio_raw.get("host", "")),
            api_base_url=str(lmstudio_raw.get("api_base_url", "")),
            openai_base_url=str(lmstudio_raw.get("openai_base_url", "")),
            api_key=str(lmstudio_raw.get("api_key", "")),
        ),
        models=models,
        input=InputConfig(
            image_dir=str(input_raw.get("image_dir", "")),
            recursive=bool(input_raw.get("recursive", False)),
            extensions=[str(ext).lower() for ext in input_raw.get("extensions", [])],
        ),
        output=OutputConfig(results_dir=str(output_raw.get("results_dir", "results"))),
        modes=[str(mode) for mode in loaded.get("modes", [])],
        pools=PoolsConfig(
            ru_plain=str(pools_raw.get("ru_plain", "")),
            en_plain=str(pools_raw.get("en_plain", "")),
            ru_explained=str(pools_raw.get("ru_explained", "")),
            en_explained=str(pools_raw.get("en_explained", "")),
        ),
        prompt_files=PromptFilesConfig(
            ru_free=str(prompt_files_raw.get("ru_free", "")),
            ru_pool=str(prompt_files_raw.get("ru_pool", "")),
            ru_pool_explained=str(prompt_files_raw.get("ru_pool_explained", "")),
            en_free=str(prompt_files_raw.get("en_free", "")),
            en_pool=str(prompt_files_raw.get("en_pool", "")),
            en_pool_explained=str(prompt_files_raw.get("en_pool_explained", "")),
        ),
        generation=GenerationConfig(
            temperature=float(generation_raw.get("temperature", 0.0)),
            top_p=float(generation_raw.get("top_p", 1.0)),
            max_tokens=int(generation_raw.get("max_tokens", 4096)),
        ),
        load=LoadConfig(
            context_length=_coerce_int(load_raw.get("context_length")),
            flash_attention=load_raw.get("flash_attention"),
            offload_kv_cache_to_gpu=load_raw.get("offload_kv_cache_to_gpu"),
            echo_load_config=load_raw.get("echo_load_config"),
        ),
        limits=LimitsConfig(
            timeout_sec=int(limits_raw.get("timeout_sec", 180)),
            retries=int(limits_raw.get("retries", 1)),
            limit_images=_coerce_int(limits_raw.get("limit_images")),
        ),
        response_formats=response_formats,
        validation=ValidationConfig(
            use_response_format=bool(validation_raw.get("use_response_format", True)),
            allow_json_extraction=bool(validation_raw.get("allow_json_extraction", True)),
            allow_line_fallback=bool(validation_raw.get("allow_line_fallback", True)),
            drop_tags_not_in_pool=bool(validation_raw.get("drop_tags_not_in_pool", True)),
            save_invalid_results=bool(validation_raw.get("save_invalid_results", True)),
        ),
        diagnostics=DiagnosticsConfig(
            gpu_memory=GPUDiagnosticsConfig(
                enabled=bool(gpu_raw.get("enabled", True)),
                command=str(gpu_raw.get("command", "nvidia-smi")),
                fail_if_unavailable=bool(gpu_raw.get("fail_if_unavailable", False)),
            ),
            context=ContextDiagnosticsConfig(
                record_usage_tokens=bool(context_raw.get("record_usage_tokens", True)),
                warning_ratio=float(context_raw.get("warning_ratio", 0.85)),
                error_ratio=float(context_raw.get("error_ratio", 0.97)),
                classify_context_errors=bool(context_raw.get("classify_context_errors", True)),
            ),
        ),
        runtime=RuntimeConfig(
            result_mode=str(runtime_raw.get("result_mode", "deterministic")),
            unload_model_after_run=bool(runtime_raw.get("unload_model_after_run", True)),
            resume=bool(runtime_raw.get("resume", True)),
            retry_failed=bool(runtime_raw.get("retry_failed", True)),
            sleep_after_load_sec=float(runtime_raw.get("sleep_after_load_sec", 2)),
            image_request_smoke_test=bool(runtime_raw.get("image_request_smoke_test", True)),
        ),
        report=ReportConfig(
            generate_csv=bool(report_raw.get("generate_csv", True)),
            generate_html=bool(report_raw.get("generate_html", True)),
            open_html_after_run=bool(report_raw.get("open_html_after_run", False)),
            thumbnail_size=int(report_raw.get("thumbnail_size", 256)),
        ),
        evaluation=dict(loaded.get("evaluation", {})),
        raw=loaded,
    )
    return cfg
