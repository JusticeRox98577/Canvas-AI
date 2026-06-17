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

import socket
import threading
import time

DEFAULT_HOST = "127.0.0.1"


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


def run(host: str = DEFAULT_HOST, port: int | None = None) -> None:
    try:
        import webview  # pywebview
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit(
            'Desktop extras not installed. Run: pip install -e ".[desktop,web,browser]"'
        ) from exc

    port = port or _free_port(host)
    base = f"http://{host}:{port}"

    thread = threading.Thread(target=_serve, args=(host, port), daemon=True)
    thread.start()
    _wait_until_up(f"{base}/api/status")

    webview.create_window(
        "Canvas-AI",
        base,
        width=1200,
        height=820,
        min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    run()
