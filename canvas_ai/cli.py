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


def _build(config: Config) -> tuple[CanvasClient, Toolbox]:
    client = CanvasClient(config)
    return client, Toolbox(client, config)


def cmd_courses(config: Config) -> None:
    with CanvasClient(config) as client:
        for c in courses_api.list_courses(client):
            console.print(f"[bold]{c['id']}[/bold]  {c.get('name')}")


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

    sub.add_parser("courses", help="List your active courses (connectivity check)")

    agent = sub.add_parser("agent", help="Run the agent with a natural-language goal")
    agent.add_argument("goal", help="What you want it to do, in plain English")

    args = parser.parse_args()

    try:
        config = Config.load()
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        return 2

    if args.command == "courses":
        cmd_courses(config)
    elif args.command == "agent":
        cmd_agent(config, args.goal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
