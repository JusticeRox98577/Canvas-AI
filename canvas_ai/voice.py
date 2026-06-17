"""Make generated text sound like a real person — ideally like *you*.

Two levers:
1. ANTI_AI_RULES: instructions that strip the usual AI tells.
2. A personal writing sample so the model imitates your actual voice. Put a
   paragraph or two of your own writing in a file named ``voice.txt`` in the
   project folder (it's git-ignored), or set WRITING_SAMPLE in your .env.
"""

from __future__ import annotations

import os

ANTI_AI_RULES = """Write like a real student typing this themselves — NOT like an AI.
- First person, natural, a little informal. Use contractions (I'm, don't, it's).
- Plain everyday words. Don't sound polished, corporate, or "essay-like".
- Vary sentence length. A few short sentences are good. It's fine to start a
  sentence with "And" or "But", and to be slightly imperfect.
- NEVER use em dashes (—). Use commas, periods, or parentheses instead.
- Avoid AI-tell phrases: "Honestly,", "It's important to note", "In today's
  world", "plays a crucial role", "delve", "navigate", "tapestry", "moreover",
  "furthermore", "in conclusion".
- Don't force three-item lists or perfectly parallel structure. Only use bullet
  points if the prompt explicitly asks for a list.
- No headings, no preamble, no sign-off. Just the answer itself.
- Make your point and move on; don't over-explain or repeat yourself."""


def voice_sample() -> str:
    """Return the user's writing sample, if they've provided one."""
    env = os.getenv("WRITING_SAMPLE", "").strip()
    if env:
        return env
    candidates = [
        os.path.join(os.getcwd(), "voice.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice.txt"),
    ]
    for path in candidates:
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    text = fh.read().strip()
                if text:
                    return text
        except OSError:
            pass
    return ""


def style_system(base: str) -> str:
    """Combine a base instruction with the anti-AI rules and any voice sample."""
    parts = [base, ANTI_AI_RULES]
    sample = voice_sample()
    if sample:
        parts.append(
            "Match the voice, vocabulary, and rhythm of THIS writing sample from "
            "the student. Imitate how they actually write (their word choices, "
            "sentence length, and tone):\n\n\"\"\"\n" + sample[:4000] + "\n\"\"\""
        )
    return "\n\n".join(parts)
