"""Pluggable LLM brain: local (Ollama) by default, cloud (Anthropic) optional."""

from __future__ import annotations

from canvas_ai.config import Config
from canvas_ai.llm.base import LLMProvider


def get_provider(config: Config, provider: str | None = None) -> LLMProvider:
    """Build an LLM provider. Defaults to config.llm_provider; pass `provider`
    (e.g. config.draft_provider) to override per purpose."""
    name = (provider or config.llm_provider).strip().lower()
    if name == "ollama":
        from canvas_ai.llm.ollama import OllamaProvider

        return OllamaProvider(config)
    if name == "anthropic":
        from canvas_ai.llm.anthropic import AnthropicProvider

        return AnthropicProvider(config)
    if name in {"claude_code", "claude-code", "claudecode", "subscription"}:
        from canvas_ai.llm.claude_code import ClaudeCodeProvider

        return ClaudeCodeProvider(config)
    raise ValueError(f"Unknown provider: {name!r}")
