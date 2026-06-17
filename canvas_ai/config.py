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
    auth_mode: str
    canvas_profile_dir: str
    llm_provider: str
    draft_provider: str
    ollama_host: str
    ollama_model: str
    anthropic_api_key: str
    anthropic_model: str
    write_mode: str
    auto_submit: bool

    @classmethod
    def load(cls) -> "Config":
        write_mode = os.getenv("WRITE_MODE", "dry_run").strip().lower()
        if write_mode not in {"dry_run", "confirm", "auto"}:
            raise ConfigError(f"WRITE_MODE must be dry_run|confirm|auto, got {write_mode!r}")

        # Opt-in: let the assistant complete AND submit graded work directly,
        # without a per-submission confirmation. Off by default.
        auto_submit = os.getenv("AUTO_SUBMIT", "false").strip().lower() in {"1", "true", "yes", "on"}

        auth_mode = os.getenv("AUTH_MODE", "browser").strip().lower()
        if auth_mode not in {"token", "browser"}:
            raise ConfigError(f"AUTH_MODE must be token|browser, got {auth_mode!r}")

        # A token is only required in token mode; browser mode logs in interactively.
        token = _require("CANVAS_TOKEN") if auth_mode == "token" else os.getenv("CANVAS_TOKEN", "")

        return cls(
            canvas_base_url=_require("CANVAS_BASE_URL").rstrip("/"),
            canvas_token=token,
            auth_mode=auth_mode,
            canvas_profile_dir=os.getenv("CANVAS_PROFILE_DIR", ".canvas_profile"),
            llm_provider=os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
            draft_provider=os.getenv("DRAFT_PROVIDER", os.getenv("LLM_PROVIDER", "ollama")).strip().lower(),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"),
            write_mode=write_mode,
            auto_submit=auto_submit,
        )
