"""Central configuration, loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == "replace-me":
        raise ConfigError(
            f"Missing required env var {name!r}. Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Config:
    canvas_base_url: str
    canvas_token: str
    llm_provider: str
    ollama_host: str
    ollama_model: str
    anthropic_api_key: str
    anthropic_model: str
    write_mode: str

    @classmethod
    def load(cls) -> "Config":
        write_mode = os.getenv("WRITE_MODE", "dry_run").strip().lower()
        if write_mode not in {"dry_run", "confirm", "auto"}:
            raise ConfigError(f"WRITE_MODE must be dry_run|confirm|auto, got {write_mode!r}")

        return cls(
            canvas_base_url=_require("CANVAS_BASE_URL").rstrip("/"),
            canvas_token=_require("CANVAS_TOKEN"),
            llm_provider=os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"),
            write_mode=write_mode,
        )
