"""Optional license-key activation for paid distribution.

Off by default (LICENSE_REQUIRED=false), so development and personal use are
unaffected. When a seller builds with LICENSE_REQUIRED=true, the app asks for a
license key on first run, activates it online, and validates on later launches.

Provider-agnostic but defaults to the LemonSqueezy License API (no secret key
needed for activate/validate). Override the endpoints with LICENSE_ACTIVATE_URL
/ LICENSE_VALIDATE_URL to use a different backend.

The key + activation instance are cached in a small license.json in the per-user
config dir (same place as settings.json).
"""

from __future__ import annotations

import json
import os
import socket

import httpx

from canvas_ai import settings as app_settings

ACTIVATE_URL = os.getenv("LICENSE_ACTIVATE_URL", "https://api.lemonsqueezy.com/v1/licenses/activate")
VALIDATE_URL = os.getenv("LICENSE_VALIDATE_URL", "https://api.lemonsqueezy.com/v1/licenses/validate")


def required() -> bool:
    return os.getenv("LICENSE_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _file() -> str:
    return os.path.join(app_settings.config_dir(), "license.json")


def _load() -> dict:
    try:
        with open(_file(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    with open(_file(), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _instance_name() -> str:
    try:
        return socket.gethostname() or "device"
    except Exception:  # noqa: BLE001
        return "device"


def activate(key: str) -> tuple[bool, str]:
    """Activate a key on this device. Returns (ok, message)."""
    key = (key or "").strip()
    if not key:
        return False, "Enter a license key."
    try:
        r = httpx.post(
            ACTIVATE_URL,
            data={"license_key": key, "instance_name": _instance_name()},
            headers={"Accept": "application/json"},
            timeout=20,
        )
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        return False, f"Couldn't reach the license server: {exc}"
    if data.get("activated") and (data.get("instance") or {}).get("id"):
        _save({"key": key, "instance_id": data["instance"]["id"]})
        return True, "Activated."
    return False, str(data.get("error") or "That license key couldn't be activated.")


def is_activated() -> bool:
    """True if not required, or if the cached key validates online (offline-tolerant)."""
    if not required():
        return True
    lic = _load()
    key = lic.get("key")
    if not key:
        return False
    try:
        r = httpx.post(
            VALIDATE_URL,
            data={"license_key": key, "instance_id": lic.get("instance_id", "")},
            headers={"Accept": "application/json"},
            timeout=12,
        )
        return bool(r.json().get("valid"))
    except Exception:  # noqa: BLE001
        # Network down: trust a previously-activated key so paying users aren't
        # locked out offline.
        return bool(lic.get("instance_id"))


def status() -> dict:
    return {"required": required(), "activated": is_activated()}
