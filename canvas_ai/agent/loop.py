"""The agent loop: give the brain a goal, let it call tools until done."""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from rich.console import Console

from canvas_ai.agent.tools import Toolbox, tool_schemas
from canvas_ai.llm.base import LLMProvider, ToolCall

console = Console()


def extract_text_tool_calls(text: str) -> list[ToolCall]:
    """Recover tool calls that small models emit as plain text/JSON in content.

    Local models (e.g. llama3.1:8b) often print
    ``{"name": "read_discussion", "parameters": {...}}`` instead of using the
    structured tool-call channel. We parse those so the loop can execute them
    rather than showing raw JSON to the user.
    """
    if not text:
        return []
    s = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    blob = s[start : end + 1]
    data = None
    for parse in (json.loads, ast.literal_eval):  # ast handles True/False/None, quotes
        try:
            data = parse(blob)
            break
        except Exception:  # noqa: BLE001
            continue
    if data is None:
        return []

    out: list[ToolCall] = []
    for d in data if isinstance(data, list) else [data]:
        if not isinstance(d, dict):
            continue
        fn = d.get("function") if isinstance(d.get("function"), dict) else {}
        name = d.get("name") or d.get("tool") or fn.get("name")
        args = d.get("parameters") or d.get("arguments") or fn.get("arguments") or {}
        if name and isinstance(args, dict):
            out.append(ToolCall(name=name, arguments=args))
    return out

SYSTEM_PROMPT = """You are Canvas-AI, an assistant that helps a student work with
their own Canvas LMS account. You can read courses, modules, pages, embedded
content, and discussions, and you can draft and post discussion replies.

CRITICAL RULES:
- NEVER invent or guess course content, module names, page titles, assignments,
  or due dates. Only state facts that came from a tool result or from grounding
  context provided to you.
- If you have not actually retrieved the information with a tool, do not pretend
  you did. Say what you don't have and which tool/course id you would need.
- Do not narrate calling a tool ("I'll call X"); either actually call it or
  answer from data you already have.

Principles:
- Gather context with read tools before acting.
- For any writing, draft clearly and let the human confirm.
- Submitting graded work always requires explicit human confirmation.
When the task is complete, reply with a concise, grounded answer.
"""


def run(
    brain: LLMProvider,
    toolbox: Toolbox,
    goal: str,
    *,
    max_steps: int = 12,
    include_writes: bool = True,
    history: list[dict[str, Any]] | None = None,
) -> str:
    messages: list[dict[str, Any]] = history or [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": goal})
    schemas = tool_schemas(include_writes=include_writes)

    for step in range(max_steps):
        resp = brain.chat(messages, tools=schemas)

        # Use structured tool calls, or recover ones the model printed as text.
        tool_calls = resp.tool_calls or extract_text_tool_calls(resp.text)
        if not tool_calls:
            return resp.text or "(no response)"

        # Record the assistant's intent, then execute each requested tool.
        messages.append({"role": "assistant", "content": resp.text or ""})
        for call in tool_calls:
            console.log(f"[cyan]tool[/cyan] {call.name}({call.arguments})")
            try:
                result = toolbox.call(call.name, call.arguments)
            except Exception as exc:  # noqa: BLE001 - surface tool errors to the model
                result = {"error": str(exc)}
            messages.append(
                {"role": "tool", "name": call.name, "content": json.dumps(result, default=str)[:8000]}
            )

    return "(stopped: reached max steps)"
