"""Fast Canvas client that reuses the browser-login session via saved cookies.

After `canvas-ai login`, the session is snapshotted to
``.canvas_profile/storage_state.json``. This client loads those cookies and
talks to the Canvas REST API with plain httpx -- no browser launch per call,
which is what makes the web UI responsive. It is duck-type compatible with
CanvasClient / BrowserCanvasClient (get / post / put / paginate).

When the Canvas session eventually expires, calls return 401 and the user
simply re-runs `canvas-ai login`.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Iterator
from urllib.parse import unquote

import httpx

from canvas_ai.config import Config


class SessionExpired(RuntimeError):
    """Raised when the saved cookies are missing or no longer valid."""


class CookieCanvasClient:
    def __init__(self, config: Config, *, timeout: float = 30.0):
        self._base = f"{config.canvas_base_url}/api/v1"
        self._root = config.canvas_base_url
        state_file = os.path.join(config.canvas_profile_dir, "storage_state.json")
        if not os.path.exists(state_file):
            raise SessionExpired("No saved session. Run `canvas-ai login` first.")

        with open(state_file) as fh:
            state = json.load(fh)

        jar = httpx.Cookies()
        csrf = ""
        for c in state.get("cookies", []):
            jar.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
            if c["name"] == "_csrf_token":
                csrf = unquote(c["value"])
        self._csrf = csrf
        self._csrf_primed = False
        self._client = httpx.Client(cookies=jar, timeout=timeout, follow_redirects=True)

    def _ensure_csrf(self) -> None:
        """Get a CSRF token that matches the *current* session before writing.

        The saved _csrf_token can be stale (from an earlier session) even when
        the session cookie still reads fine — which makes reads work but writes
        401. So we drop the old token and hit the Canvas root once; Canvas then
        issues a fresh _csrf_token paired with this session, which we read back.
        """
        if self._csrf_primed:
            return
        self._csrf_primed = True
        try:
            self._client.cookies.delete("_csrf_token")
        except Exception:  # noqa: BLE001
            pass
        try:
            self._client.get(self._root)
        except Exception:  # noqa: BLE001
            pass
        for cookie in self._client.cookies.jar:
            if cookie.name == "_csrf_token" and cookie.value:
                self._csrf = unquote(cookie.value)
                return

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CookieCanvasClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- core ------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = path if path.startswith("http") else f"{self._base}{path}"
        if method in ("POST", "PUT", "DELETE"):
            self._ensure_csrf()
            kwargs.setdefault("headers", {})["X-CSRF-Token"] = self._csrf
        resp = self._client.request(method, url, **kwargs)
        self._respect_rate_limit(resp)
        if resp.status_code in (401, 403):
            raise SessionExpired(
                f"Canvas session expired or invalid ({resp.status_code}). "
                "Re-run `canvas-ai login`."
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"{method} {url} -> {resp.status_code}: {resp.text[:400]}")
        return resp

    @staticmethod
    def _respect_rate_limit(resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-Rate-Limit-Remaining")
        if remaining is not None:
            try:
                if float(remaining) < 50:
                    time.sleep(1.0)
            except ValueError:
                pass

    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params or None).json()

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs).json()

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs).json()

    def paginate(self, path: str, **params: Any) -> Iterator[dict]:
        params.setdefault("per_page", 100)
        url: str | None = path
        first = True
        while url:
            resp = self._request("GET", url, params=params if first else None)
            first = False
            data = resp.json()
            if isinstance(data, list):
                yield from data
            else:
                yield data
            url = self._next_link(resp)

    @staticmethod
    def _next_link(resp: httpx.Response) -> str | None:
        link = resp.headers.get("Link", "")
        for part in link.split(","):
            section = part.split(";")
            if len(section) >= 2 and 'rel="next"' in section[1]:
                return section[0].strip().strip("<>")
        return None
