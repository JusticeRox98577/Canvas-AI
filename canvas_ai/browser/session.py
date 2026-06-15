"""A Canvas client that authenticates via a logged-in browser session.

Key idea: the Canvas REST API accepts your normal *session cookies*, not only
bearer tokens. So we keep a persistent Playwright browser profile where you've
logged in, and issue the same /api/v1 requests through that context. Reads work
with cookies alone; writes additionally need Canvas's CSRF token, which we read
from the `_csrf_token` cookie and send as the `X-CSRF-Token` header.

This client is duck-type compatible with canvas_ai.canvas.client.CanvasClient
(get / post / put / paginate), so all resource helpers and the agent work
unchanged regardless of auth mode.
"""

from __future__ import annotations

import time
from typing import Any, Iterator
from urllib.parse import unquote

from canvas_ai.config import Config


class BrowserAuthError(RuntimeError):
    """Raised when no logged-in session is available."""


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise BrowserAuthError(
            "Browser auth needs Playwright. Run:\n"
            "  pip install -e .[browser]\n"
            "  playwright install chromium"
        ) from exc
    return sync_playwright


class BrowserCanvasClient:
    """Canvas REST client backed by a persistent, logged-in browser profile."""

    def __init__(self, config: Config, *, headless: bool = True):
        self._base = f"{config.canvas_base_url}/api/v1"
        self._root = config.canvas_base_url
        self._profile_dir = config.canvas_profile_dir
        self._headless = headless
        sync_playwright = _require_playwright()
        self._pw = sync_playwright().start()
        self._ctx = self._launch(headless)
        # context.request shares cookies with the browser context automatically.
        self._req = self._ctx.request

    def _launch(self, headless: bool):
        """Launch the persistent context, tuned to survive Microsoft 365 SSO.

        Microsoft's sign-in often rejects Playwright's bundled Chromium and
        flags the automation banner, so we prefer real installed Chrome and
        disable the AutomationControlled feature. Falls back to plain Chromium
        if Chrome isn't installed.
        """
        opts = dict(
            user_data_dir=self._profile_dir,
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        try:
            return self._pw.chromium.launch_persistent_context(channel="chrome", **opts)
        except Exception:
            # Chrome not installed -> use the bundled Chromium.
            return self._pw.chromium.launch_persistent_context(**opts)

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        try:
            self._ctx.close()
        finally:
            self._pw.stop()

    def __enter__(self) -> "BrowserCanvasClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- auth helpers ----------------------------------------------------
    def is_authenticated(self) -> bool:
        resp = self._req.get(f"{self._base}/users/self")
        return resp.status == 200

    def _csrf_header(self) -> dict[str, str]:
        for cookie in self._ctx.cookies():
            if cookie.get("name") == "_csrf_token":
                return {"X-CSRF-Token": unquote(cookie.get("value", ""))}
        return {}

    def _check(self, resp, method: str, url: str):
        if resp.status >= 400:
            body = resp.text()[:500]
            if resp.status in (401, 403):
                raise BrowserAuthError(
                    f"Not authenticated ({resp.status}). Run `canvas-ai login` first."
                )
            raise RuntimeError(f"{method} {url} -> {resp.status}: {body}")
        return resp

    @staticmethod
    def _respect_rate_limit(resp) -> None:
        remaining = resp.headers.get("x-rate-limit-remaining")
        if remaining is not None:
            try:
                if float(remaining) < 50:
                    time.sleep(1.0)
            except ValueError:
                pass

    # -- public verbs (mirror CanvasClient) ------------------------------
    def get(self, path: str, **params: Any) -> Any:
        url = path if path.startswith("http") else f"{self._base}{path}"
        resp = self._req.get(url, params=params or None)
        self._respect_rate_limit(resp)
        return self._check(resp, "GET", url).json()

    def post(self, path: str, *, data: dict | None = None, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{self._base}{path}"
        resp = self._req.post(url, form=data or {}, headers=self._csrf_header())
        self._respect_rate_limit(resp)
        return self._check(resp, "POST", url).json()

    def put(self, path: str, *, data: dict | None = None, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{self._base}{path}"
        resp = self._req.put(url, form=data or {}, headers=self._csrf_header())
        self._respect_rate_limit(resp)
        return self._check(resp, "PUT", url).json()

    def paginate(self, path: str, **params: Any) -> Iterator[dict]:
        params.setdefault("per_page", 100)
        url: str | None = path if path.startswith("http") else f"{self._base}{path}"
        first = True
        while url:
            resp = self._req.get(url, params=params if first else None)
            first = False
            self._respect_rate_limit(resp)
            self._check(resp, "GET", url)
            data = resp.json()
            if isinstance(data, list):
                yield from data
            else:
                yield data
            url = self._next_link(resp)

    @staticmethod
    def _next_link(resp) -> str | None:
        link = resp.headers.get("link", "")
        for part in link.split(","):
            section = part.split(";")
            if len(section) >= 2 and 'rel="next"' in section[1]:
                return section[0].strip().strip("<>")
        return None


def interactive_login(config: Config, *, timeout_s: int = 600) -> None:
    """Open a visible browser so the user can log in; persist the session.

    Polls until Canvas reports an authenticated user, then closes. After this,
    normal headless commands reuse the saved profile.
    """
    from rich.console import Console

    console = Console()
    client = BrowserCanvasClient(config, headless=False)
    try:
        page = client._ctx.pages[0] if client._ctx.pages else client._ctx.new_page()
        page.goto(config.canvas_base_url)
        console.print(
            "[bold]A browser window opened.[/bold] Sign in there:\n"
            "  1. Canvas will redirect you to your district's Microsoft 365 login.\n"
            "  2. Enter your school email + password and complete MFA.\n"
            "  3. If Microsoft asks [italic]\"Stay signed in?\"[/italic], choose [bold]Yes[/bold] "
            "so you don't have to repeat this often.\n"
            "I'll detect automatically when you land back in Canvas."
        )
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if client.is_authenticated():
                console.print("[green]Logged in. Session saved.[/green]")
                return
            time.sleep(2.0)
        raise BrowserAuthError("Timed out waiting for login.")
    finally:
        client.close()
