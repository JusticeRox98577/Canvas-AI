"""Command-line entry point for Canvas-AI."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from canvas_ai.agent.loop import run
from canvas_ai.agent.tools import Toolbox
from canvas_ai.canvas.client import CanvasClient
from canvas_ai.canvas import courses as courses_api
from canvas_ai.config import Config, ConfigError
from canvas_ai.llm import get_provider

console = Console()


def make_client(config: Config):
    """Pick the auth backend: browser session (default) or bearer token."""
    if config.auth_mode == "browser":
        from canvas_ai.browser.session import BrowserCanvasClient

        return BrowserCanvasClient(config)
    return CanvasClient(config)


def _build(config: Config):
    client = make_client(config)
    return client, Toolbox(client, config)


def cmd_login(config: Config) -> None:
    if config.auth_mode != "browser":
        console.print("[yellow]AUTH_MODE is not 'browser'; login is only for browser mode.[/yellow]")
        return
    from canvas_ai.browser.session import interactive_login

    interactive_login(config)


def cmd_courses(config: Config) -> None:
    with make_client(config) as client:
        for c in courses_api.list_courses(client):
            console.print(f"[bold]{c['id']}[/bold]  {c.get('name')}")


def cmd_web(config: Config, host: str, port: int) -> None:
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Web extras not installed.[/red] Run: pip install -e \".[web]\"")
        return
    url = f"http://{host}:{port}"
    console.print(f"[green]Canvas-AI web app:[/green] {url}  (Ctrl-C to stop)")
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    uvicorn.run("canvas_ai.web.app:app", host=host, port=port, log_level="warning")


def cmd_app(config: Config) -> None:
    """Launch the native desktop window (Windows)."""
    from canvas_ai import desktop

    console.print("[green]Launching Canvas-AI…[/green]")
    desktop.run()


def cmd_agent(config: Config, goal: str) -> None:
    brain = get_provider(config)
    client, toolbox = _build(config)
    with client:
        answer = run(brain, toolbox, goal)
    console.print()
    console.print(answer)


def main() -> int:
    parser = argparse.ArgumentParser(prog="canvas-ai", description="Local-first Canvas LMS assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Open a browser to log into Canvas (browser auth mode)")
    sub.add_parser("courses", help="List your active courses (connectivity check)")

    web = sub.add_parser("web", help="Launch the local web app (GUI)")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--host", default="127.0.0.1")

    sub.add_parser("app", help="Launch the native desktop app (Windows window)")

    agent = sub.add_parser("agent", help="Run the agent with a natural-language goal")
    agent.add_argument("goal", help="What you want it to do, in plain English")

    args = parser.parse_args()

    try:
        config = Config.load()
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        return 2

    if args.command == "login":
        cmd_login(config)
    elif args.command == "courses":
        cmd_courses(config)
    elif args.command == "web":
        cmd_web(config, args.host, args.port)
    elif args.command == "app":
        cmd_app(config)
    elif args.command == "agent":
        cmd_agent(config, args.goal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
