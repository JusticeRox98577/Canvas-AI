"""Human-confirmation gate for every write action.

Design rule: nothing is ever written to Canvas without passing through here.
Graded work (assignment/quiz submissions) is ALWAYS forced to 'confirm',
regardless of WRITE_MODE, so it can never be auto-submitted silently.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

console = Console()

# Actions that always require explicit human approval, even in 'auto' mode.
HIGH_STAKES = {"submit_assignment_text", "submit_assignment_file", "submit_quiz"}


class WriteBlocked(Exception):
    """Raised when a write is rejected (by dry_run or by the user)."""


def approve(action: str, summary: str, *, mode: str) -> bool:
    """Return True if the write should proceed.

    mode: dry_run | confirm | auto
    """
    effective = "confirm" if action in HIGH_STAKES else mode

    console.print(Panel(summary, title=f"WRITE: {action}  (mode={effective})", expand=False))

    if effective == "dry_run":
        console.print("[yellow]dry_run: nothing was written.[/yellow]")
        return False
    if effective == "auto":
        console.print("[green]auto: proceeding.[/green]")
        return True

    answer = console.input("[bold]Proceed? [y/N] [/bold]").strip().lower()
    return answer in {"y", "yes"}
