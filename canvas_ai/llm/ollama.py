"""Local brain via Ollama's chat API (no data leaves the machine)."""

from __future__ import annotations

from typing import Any

import httpx

from canvas_ai.config import Config
from canvas_ai.llm.base import LLMProvider, LLMResponse, ToolCall


class OllamaProvider(LLMProvider):
    def __init__(self, config: Config):
        self._host = config.ollama_host
        self._model = config.ollama_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        resp = httpx.post(f"{self._host}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        msg = resp.json().get("message", {})

        tool_calls = [
            ToolCall(
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments", {}) or {},
            )
            for tc in msg.get("tool_calls", []) or []
        ]
        return LLMResponse(text=msg.get("content", ""), tool_calls=tool_calls)
