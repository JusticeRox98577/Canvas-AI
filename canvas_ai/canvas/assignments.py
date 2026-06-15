"""Assignments and submissions.

NOTE: graded submissions are intentionally treated as high-stakes. The agent
layer forces these through the human-confirmation gate; they are never posted
automatically. See canvas_ai/agent/gates.py.
"""

from __future__ import annotations

from canvas_ai.canvas.client import CanvasClient


def list_assignments(
    client: CanvasClient, course_id: int, include: list[str] | None = None
) -> list[dict]:
    params = {"include[]": include} if include else {}
    return list(client.paginate(f"/courses/{course_id}/assignments", **params))


def get_assignment(client: CanvasClient, course_id: int, assignment_id: int) -> dict:
    return client.get(f"/courses/{course_id}/assignments/{assignment_id}")


def submit_text(
    client: CanvasClient, course_id: int, assignment_id: int, body: str
) -> dict:
    """Create a text-entry submission. MUST go through the write gate (confirm)."""
    return client.post(
        f"/courses/{course_id}/assignments/{assignment_id}/submissions",
        data={"submission[submission_type]": "online_text_entry", "submission[body]": body},
    )


def submit_file(
    client: CanvasClient, course_id: int, assignment_id: int, file_id: int
) -> dict:
    """Create a file-upload submission from an already-uploaded file_id."""
    return client.post(
        f"/courses/{course_id}/assignments/{assignment_id}/submissions",
        data={
            "submission[submission_type]": "online_upload",
            "submission[file_ids][]": file_id,
        },
    )
