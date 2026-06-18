"""Native desktop window for Canvas-AI (Windows-first).

This wraps the existing local web app in a real native window instead of a
browser tab. It:

1. starts the FastAPI backend on a background thread (a free localhost port),
2. waits for it to come up, then
3. opens a native window (WebView2 on Windows 10/11, which ships with the OS).

It is packaged into a standalone ``CanvasAI.exe`` with PyInstaller — see the
``windows/`` folder. Run it from source with ``canvas-ai app``.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time

DEFAULT_HOST = "127.0.0.1"
WINDOW_TITLE = "Canvas-AI"
APP_USER_MODEL_ID = "CanvasAI.App"


def _icon_path() -> str | None:
    base = getattr(sys, "_MEIPASS", None)
    candidates = []
    if base:
        candidates.append(os.path.join(base, "CanvasAI.ico"))
    candidates.append(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "windows", "CanvasAI.ico")
    )
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _set_app_user_model_id() -> None:
    """Give the process its own taskbar identity (Windows only)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:  # noqa: BLE001
        pass


def _apply_window_icon() -> None:
    """Set the title-bar + taskbar icon on the native window (Windows only).

    Runs after the GUI starts; polls until the window exists, then attaches the
    icon via WM_SETICON.
    """
    if sys.platform != "win32":
        return
    ico = _icon_path()
    if not ico:
        return
    try:
        import ctypes

        u = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1

        h_small = u.LoadImageW(None, ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        h_big = u.LoadImageW(None, ico, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

        for _ in range(60):  # up to ~15s for the window to appear
            hwnd = u.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                if h_small:
                    u.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
                if h_big:
                    u.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
                return
            time.sleep(0.25)
    except Exception:  # noqa: BLE001
        pass


def _free_port(host: str = DEFAULT_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def _serve(host: str, port: int) -> None:
    """Run uvicorn in this thread. Errors are swallowed so the window still
    opens (it will simply show 'offline' / the not-signed-in banner)."""
    try:
        import uvicorn

        from canvas_ai.web.app import app as fastapi_app

        uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")
    except Exception:  # noqa: BLE001
        pass


def _wait_until_up(url: str, timeout: float = 30.0) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=1.0)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    return False


def _session_valid(config) -> bool:
    """True if the saved Canvas session still works (no browser launch)."""
    from canvas_ai.canvas.cookie_client import CookieCanvasClient

    try:
        with CookieCanvasClient(config) as c:
            c.get("/users/self")
        return True
    except Exception:  # noqa: BLE001 - missing/expired session, or offline
        return False


def ensure_login() -> None:
    """Auto-login: if the saved session is missing or expired, open the sign-in
    window before launching the app. A valid saved session is used silently."""
    try:
        from canvas_ai.config import Config

        config = Config.load()
    except Exception:  # noqa: BLE001 - no/invalid config; let the app show its banner
        return
    if config.auth_mode != "browser" or _session_valid(config):
        return
    try:
        from canvas_ai.browser.session import interactive_login

        interactive_login(config)
    except Exception:  # noqa: BLE001 - if login can't run, open the app anyway
        pass


def run(host: str = DEFAULT_HOST, port: int | None = None) -> None:
    try:
        import webview  # pywebview
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit(
            'Desktop extras not installed. Run: pip install -e ".[desktop,web,browser]"'
        ) from exc

    _set_app_user_model_id()

    # Make sure we're signed in before showing the app (opens the login window
    # only if the saved session is gone/expired).
    ensure_login()

    port = port or _free_port(host)
    base = f"http://{host}:{port}"

    thread = threading.Thread(target=_serve, args=(host, port), daemon=True)
    thread.start()
    _wait_until_up(f"{base}/api/status")

    webview.create_window(
        WINDOW_TITLE,
        base,
        width=1200,
        height=820,
        min_size=(900, 600),
    )
    # _apply_window_icon runs after the GUI loop starts and sets the icon.
    webview.start(_apply_window_icon)


if __name__ == "__main__":
    run()
