"""The agent loop: give the brain a goal, let it call tools until done."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from canvas_ai.agent.tools import Toolbox, tool_schemas
from canvas_ai.llm.base import LLMProvider

console = Console()

SYSTEM_PROMPT = """You are Canvas-AI, an assistant that helps a student work with
their own Canvas LMS account. You can read courses, modules, pages, embedded
content, and discussions, and you can draft and post discussion replies.

Principles:
- Gather context with read tools before acting.
- For any writing, draft clearly and let the human confirm; never fabricate facts
  about course content you have not read.
- Submitting graded work always requires explicit human confirmation.
Call tools as needed. When the task is complete, reply with a short summary.
"""


def run(brain: LLMProvider, toolbox: Toolbox, goal: str, *, max_steps: int = 12) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]
    schemas = tool_schemas()

    for step in range(max_steps):
        resp = brain.chat(messages, tools=schemas)

        if not resp.tool_calls:
            return resp.text or "(no response)"

        # Record the assistant's intent, then execute each requested tool.
        messages.append({"role": "assistant", "content": resp.text or ""})
        for call in resp.tool_calls:
            console.log(f"[cyan]tool[/cyan] {call.name}({call.arguments})")
            try:
                result = toolbox.call(call.name, call.arguments)
            except Exception as exc:  # noqa: BLE001 - surface tool errors to the model
                result = {"error": str(exc)}
            messages.append(
                {"role": "tool", "name": call.name, "content": json.dumps(result, default=str)[:8000]}
            )

    return "(stopped: reached max steps)"
