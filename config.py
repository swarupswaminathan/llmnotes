"""Runtime configuration: env-backed secrets/endpoints and the model registry."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (does not override)."""
    env_path = path or Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# Non-secret defaults (overridable via env)
API_VERSION = os.getenv("API_VERSION", "2025-03-01-preview")
SERVER_ERROR_CODES = {424, 429, 500, 502, 503, 504}

REPO_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = Path(os.getenv("RESULTS_ROOT", str(REPO_ROOT / "final_results")))

DEFAULT_GRADING_XLSX = os.getenv(
    "GRADING_XLSX",
    str(REPO_ROOT / "labels" / "final_sampled_df - Gustavo.xlsx"),
)
DEFAULT_FEWSHOT_XLSX = os.getenv(
    "FEWSHOT_XLSX",
    str(REPO_ROOT / "labels" / "notes_fewshot_final_complete.xlsx"),
)

SUPPORTED_CVARS = (
    "top_meds_staged",
    "top_meds_change_staged",
    "oral_meds_staged",
    "oral_meds_change_staged",
)


@dataclass(frozen=True)
class ModelSpec:
    """One entry in the model registry (alias → provider wiring)."""

    alias: str
    provider_type: str  # azure_openai | openai_compatible | anthropic
    adapter: str  # gpt | openai_compatible | qwen | anthropic
    model_name: str  # deployment / API model string
    deployment_name: str
    reasoning_effort: tuple[str, ...]
    api_key_env: str
    endpoint_env: str
    # OpenAI-compatible response_format style
    response_format_style: str = "json_schema"  # json_schema | json_object
    pass_reasoning_effort: bool = False
    # Token-limit kwarg name used by this provider's primary API path
    token_param: str = "max_completion_tokens"


def _env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val is not None and val.strip() != "":
        return val
    return default


def _build_model_registry() -> dict[str, ModelSpec]:
    """Lift of notebook Cell 3 model_config; keys/endpoints from env."""
    specs = [
        ModelSpec(
            alias="gpt",
            provider_type="azure_openai",
            adapter="gpt",
            model_name="gpt-5.2",
            deployment_name="gpt-5.2",
            reasoning_effort=("none", "low", "medium", "high", "xhigh"),
            api_key_env="AZURE_API_KEY",
            endpoint_env="AZURE_OPENAI_ENDPOINT",
            response_format_style="json_schema",
            pass_reasoning_effort=True,
            token_param="max_output_tokens",
        ),
        ModelSpec(
            alias="claude",
            provider_type="anthropic",
            adapter="anthropic",
            model_name="claude-opus-4-6",
            deployment_name="claude-opus-4-6",
            reasoning_effort=("low", "medium", "high", "max"),
            api_key_env="AZURE_API_KEY",
            endpoint_env="AZURE_ANTHROPIC_ENDPOINT",
            response_format_style="json_schema",
            pass_reasoning_effort=True,
            token_param="max_tokens",
        ),
        ModelSpec(
            alias="deepseek",
            provider_type="openai_compatible",
            adapter="openai_compatible",
            model_name="DeepSeek-V3.2",
            deployment_name="DeepSeek-V3.2",
            reasoning_effort=("minimal", "low", "medium", "high"),
            api_key_env="AZURE_API_KEY",
            endpoint_env="AZURE_COMPAT_ENDPOINT",
            response_format_style="json_object",
            pass_reasoning_effort=True,
            token_param="max_completion_tokens",
        ),
        ModelSpec(
            alias="grok_n",
            provider_type="openai_compatible",
            adapter="openai_compatible",
            model_name="grok-4-1-fast-non-reasoning",
            deployment_name="grok-4-1-fast-non-reasoning",
            reasoning_effort=("none",),
            api_key_env="AZURE_API_KEY",
            endpoint_env="AZURE_COMPAT_ENDPOINT",
            response_format_style="json_schema",
            pass_reasoning_effort=False,
            token_param="max_completion_tokens",
        ),
        ModelSpec(
            alias="qwen",
            provider_type="openai_compatible",
            adapter="qwen",
            model_name="Qwen/Qwen3.6-35B-A3B",
            deployment_name="Qwen/Qwen3.6-35B-A3B",
            reasoning_effort=("none", "low", "medium", "high"),
            api_key_env="QWEN_API_KEY",
            endpoint_env="QWEN_ENDPOINT",
            response_format_style="json_object",
            pass_reasoning_effort=False,
            token_param="max_completion_tokens",
        ),
    ]
    return {s.alias: s for s in specs}


MODEL_REGISTRY: dict[str, ModelSpec] = _build_model_registry()


def resolve_api_key(spec: ModelSpec) -> str:
    key = _env(spec.api_key_env)
    if not key:
        raise ValueError(
            f"Missing API key for model '{spec.alias}'. "
            f"Set environment variable {spec.api_key_env}."
        )
    return key


def resolve_endpoint(spec: ModelSpec) -> str:
    endpoint = _env(spec.endpoint_env)
    if not endpoint:
        raise ValueError(
            f"Missing endpoint for model '{spec.alias}'. "
            f"Set environment variable {spec.endpoint_env} in .env."
        )
    return endpoint


def get_model_spec(alias: str) -> ModelSpec:
    if alias not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model '{alias}'. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[alias]


@dataclass
class RunContext:
    """Shared mutable state for a single CLI run (logs, counters, knobs)."""

    results_dir: Path
    logger_path: Path
    model_alias: str
    model_name: str  # deployment string used in API calls / paths
    reasoning_effort: str
    tok_num: int
    cvar: str
    global_max_count: int = 0
    params_logged: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class ServerFailureError(Exception):
    """Raised when the provider returns a retriable server-side error."""
