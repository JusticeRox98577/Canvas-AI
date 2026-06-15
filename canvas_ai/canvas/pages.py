"""Wiki pages (the HTML page bodies that hold embedded content)."""

from __future__ import annotations

from canvas_ai.canvas.client import CanvasClient


def read_page(client: CanvasClient, course_id: int, page_url: str) -> dict:
    """Return a page including its ``body`` (HTML)."""
    return client.get(f"/courses/{course_id}/pages/{page_url}")


def list_pages(client: CanvasClient, course_id: int) -> list[dict]:
    return list(client.paginate(f"/courses/{course_id}/pages"))
