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
from typing import Any

from canvas_ai.config import Config
from canvas_ai.llm.base import LLMResponse


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
        convo = "\n\n".join(
            m["content"] for m in messages if m.get("role") in {"user", "assistant", "tool"}
        )

        args = [self._bin, "-p", convo]
        if system:
            args += ["--append-system-prompt", system]
        if self._model:
            args += ["--model", self._model]

        try:
            res = subprocess.run(args, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude Code timed out.")
        if res.returncode != 0:
            msg = (res.stderr or res.stdout or "").strip()[:300]
            raise RuntimeError(f"Claude Code failed: {msg or 'unknown error'}")
        return LLMResponse(text=res.stdout.strip(), tool_calls=[])
