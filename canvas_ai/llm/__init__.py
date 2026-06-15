"""Pluggable LLM brain: local (Ollama) by default, cloud (Anthropic) optional."""

from __future__ import annotations

from canvas_ai.config import Config
from canvas_ai.llm.base import LLMProvider


def get_provider(config: Config) -> LLMProvider:
    if config.llm_provider == "ollama":
        from canvas_ai.llm.ollama import OllamaProvider

        return OllamaProvider(config)
    if config.llm_provider == "anthropic":
        from canvas_ai.llm.anthropic import AnthropicProvider

        return AnthropicProvider(config)
    raise ValueError(f"Unknown LLM_PROVIDER: {config.llm_provider!r}")
