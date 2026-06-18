"""Drafting via the Claude Code CLI, using your Claude Pro/Max *subscription*.

Unlike the Anthropic API (which bills pay-as-you-go API credits), the Claude
Code CLI authenticates with your Claude.ai subscription, so usage counts against
your chat plan instead of API credits. This provider shells out to `claude -p`.

Requires Claude Code installed and logged in once:
  curl -fsSL https://claude.ai/install.sh | bash    # or: npm i -g @anthropic-ai/claude-code
  claude            # then choose subscription login
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Any

from canvas_ai.config import Config
from canvas_ai.llm.base import LLMResponse


def _no_window_kwargs() -> dict:
    """On Windows, run the subprocess hidden so the GUI/exe doesn't flash a
    console window for every call."""
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": startupinfo}


# Claude has no structured tool channel over `claude -p`, so we describe the
# tools in the prompt and ask it to emit a JSON call. The agent loop recovers
# these with extract_text_tool_calls().
def _tool_instructions(tools: list[dict[str, Any]]) -> str:
    lines = [
        "You can call tools to fetch real data before answering. Available tools:",
    ]
    for t in tools:
        fn = t.get("function", t)
        params = fn.get("parameters", {}).get("properties", {})
        sig = ", ".join(params.keys())
        lines.append(f"- {fn.get('name')}({sig}): {fn.get('description', '')}")
    lines += [
        "",
        "To CALL a tool, reply with ONLY a JSON object and nothing else:",
        '  {"name": "<tool>", "parameters": {<args>}}',
        "You will then be given the tool result and can call another tool.",
        "When you have everything you need, reply with your final answer as plain",
        "text (no JSON). Never invent data you did not get from a tool.",
    ]
    return "\n".join(lines)


def _format_convo(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            if content:
                parts.append(f"Assistant: {content}")
        elif role == "tool":
            parts.append(f"Tool result ({m.get('name', '')}): {content}")
    return "\n\n".join(parts)


def _find_claude() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    home = os.path.expanduser("~")
    candidates = [
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
        f"{home}/.local/bin/claude",
        f"{home}/.claude/local/claude",
        f"{home}/.npm-global/bin/claude",
        f"{home}/.bun/bin/claude",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


class ClaudeCodeProvider:
    def __init__(self, config: Config):
        self._bin = _find_claude()
        # Optional model override; empty means use the CLI/subscription default.
        self._model = os.getenv("CLAUDE_CODE_MODEL", "").strip()

    def chat(self, messages: list[dict[str, Any]], tools: list | None = None) -> LLMResponse:
        if not self._bin:
            raise RuntimeError(
                "Claude Code CLI not found. Install it and run `claude` once to log in:\n"
                "  curl -fsSL https://claude.ai/install.sh | bash\n"
                "  claude"
            )
        system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
        if tools:
            system = (system + "\n\n" + _tool_instructions(tools)).strip()
        convo = _format_convo(messages)

        # Send the prompt over stdin, not as an argv string: Windows caps the
        # command line at ~32k chars and course context blows past that.
        prompt = (system + "\n\n----\n\n" + convo).strip() if system else convo

        args = [self._bin, "-p"]
        if self._model:
            args += ["--model", self._model]

        try:
            res = subprocess.run(
                args,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                **_no_window_kwargs(),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude Code timed out.")
        if res.returncode != 0:
            msg = (res.stderr or res.stdout or "").strip()[:300]
            raise RuntimeError(f"Claude Code failed: {msg or 'unknown error'}")
        return LLMResponse(text=res.stdout.strip(), tool_calls=[])
