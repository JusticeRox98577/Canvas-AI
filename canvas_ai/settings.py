"""Persisted, in-app-editable settings.

These are loaded into the environment before Config is read, so the rest of the
app stays unchanged. Precedence (high to low):

    user settings.json  >  .env in the working dir  >  bundled .env  >  defaults

Settings live in a writable per-user folder (so the packaged exe can save them
even when its own folder is read-only).
"""

from __future__ import annotations

import json
import os
import sys

APP_DIR_NAME = "Canvas-AI"

# editable setting key -> environment variable it maps to
ENV_MAP = {
    "canvas_base_url": "CANVAS_BASE_URL",
    "llm_provider": "LLM_PROVIDER",
    "draft_provider": "DRAFT_PROVIDER",
    "claude_code_model": "CLAUDE_CODE_MODEL",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "anthropic_model": "ANTHROPIC_MODEL",
    "write_mode": "WRITE_MODE",
    "auto_submit": "AUTO_SUBMIT",
    "allow_submit": "ALLOW_SUBMIT",
    "writing_sample": "WRITING_SAMPLE",
}
BOOL_KEYS = {"auto_submit", "allow_submit"}


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def settings_file() -> str:
    return os.path.join(config_dir(), "settings.json")


def load_settings() -> dict:
    try:
        with open(settings_file(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def save_settings(values: dict) -> None:
    current = load_settings()
    current.update({k: v for k, v in values.items() if k in ENV_MAP})
    with open(settings_file(), "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2)


def _to_env_value(key: str, v) -> str:
    if key in BOOL_KEYS:
        return "true" if (v is True or str(v).lower() in {"1", "true", "yes", "on"}) else "false"
    return str(v)


def apply_env(values: dict | None = None) -> None:
    """Push settings into os.environ (overriding existing values)."""
    for k, v in (values if values is not None else load_settings()).items():
        env = ENV_MAP.get(k)
        if env and v is not None and str(v) != "":
            os.environ[env] = _to_env_value(k, v)


def bootstrap_env() -> None:
    """Run once at import: load the bundled .env (base) and apply user settings.

    The working-dir .env is loaded separately by config.py via load_dotenv().
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        envf = os.path.join(base, ".env")
        if os.path.isfile(envf):
            try:
                from dotenv import load_dotenv

                load_dotenv(envf, override=False)
            except Exception:  # noqa: BLE001
                pass
        # Frozen builds must keep login/profile in a writable absolute path.
        # The bundled .env may carry a relative CANVAS_PROFILE_DIR, so override
        # any missing or non-absolute value.
        cur = os.environ.get("CANVAS_PROFILE_DIR", "")
        if not cur or not os.path.isabs(cur):
            os.environ["CANVAS_PROFILE_DIR"] = os.path.join(config_dir(), ".canvas_profile")
    apply_env()
