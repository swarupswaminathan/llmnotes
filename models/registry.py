"""Client factory and adapter registry."""

from __future__ import annotations

from typing import Any

from openai import AzureOpenAI, OpenAI
from anthropic import AnthropicFoundry

from config import (
    API_VERSION,
    MODEL_REGISTRY,
    ModelSpec,
    RunContext,
    get_model_spec,
    resolve_api_key,
    resolve_endpoint,
)
from models.anthropic_client import AnthropicAdapter
from models.base import BaseAdapter
from models.gpt_client import GptAdapter
from models.openai_compatible import OpenAICompatibleAdapter, QwenAdapter

_ADAPTER_CLASSES: dict[str, type[BaseAdapter]] = {
    "gpt": GptAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "qwen": QwenAdapter,
    "anthropic": AnthropicAdapter,
}


def create_client(spec: ModelSpec, api_key: str | None = None) -> Any:
    """Create the SDK client for a model spec."""
    key = api_key or resolve_api_key(spec)
    endpoint = resolve_endpoint(spec)
    provider_type = spec.provider_type

    if provider_type == "azure_openai":
        return AzureOpenAI(
            api_version=API_VERSION,
            azure_endpoint=endpoint,
            api_key=key,
        )
    if provider_type == "openai_compatible":
        return OpenAI(base_url=endpoint, api_key=key)
    if provider_type == "anthropic":
        return AnthropicFoundry(api_key=key, base_url=endpoint)
    raise ValueError(f"Unsupported provider_type: {provider_type}")


def create_adapter(alias: str, ctx: RunContext) -> BaseAdapter:
    """Resolve alias → ModelSpec → client → adapter instance."""
    spec = get_model_spec(alias)
    if ctx.reasoning_effort not in spec.reasoning_effort:
        raise ValueError(
            f"reasoning_effort={ctx.reasoning_effort!r} not allowed for "
            f"'{spec.alias}'. Allowed: {spec.reasoning_effort}"
        )
    client = create_client(spec)
    adapter_cls = _ADAPTER_CLASSES[spec.adapter]
    return adapter_cls(client=client, ctx=ctx, spec=spec)


def list_models() -> list[str]:
    return list(MODEL_REGISTRY.keys())
