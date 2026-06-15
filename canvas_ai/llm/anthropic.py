"""Optional cloud brain via the Anthropic API.

Off by default. Enable with LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY set,
plus `pip install -e .[anthropic]`. Uses claude-opus-4-8 by default.
"""

from __future__ import annotations

from typing import Any

from canvas_ai.config import Config
from canvas_ai.llm.base import LLMProvider, LLMResponse, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self, config: Config):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install cloud extras: pip install -e .[anthropic]") from exc
        if not config.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._model = config.anthropic_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        # Anthropic takes the system prompt separately from the message list.
        system = ""
        convo = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                convo.append(m)

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system or None,
            messages=convo,
            tools=tools or [],
        )

        text_parts, tool_calls = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(name=block.name, arguments=block.input))
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)
