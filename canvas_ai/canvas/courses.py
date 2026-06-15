"""Courses, modules, and module items."""

from __future__ import annotations

from canvas_ai.canvas.client import CanvasClient


def list_courses(client: CanvasClient, only_active: bool = True) -> list[dict]:
    params: dict = {"enrollment_state": "active"} if only_active else {}
    return list(client.paginate("/courses", **params))


def list_modules(client: CanvasClient, course_id: int) -> list[dict]:
    return list(client.paginate(f"/courses/{course_id}/modules"))


def list_module_items(client: CanvasClient, course_id: int, module_id: int) -> list[dict]:
    """Items inside a module: pages, files, quizzes, external/embedded tools, etc."""
    return list(
        client.paginate(
            f"/courses/{course_id}/modules/{module_id}/items",
            include=["content_details"],
        )
    )
