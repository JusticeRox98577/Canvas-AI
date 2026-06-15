"""Provider-agnostic interface for the agent brain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]


class LLMProvider(Protocol):
    """A chat model that can request tool calls.

    Implementations take the running message history plus the available tool
    schemas and return either text, one or more tool calls, or both.
    """

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...
