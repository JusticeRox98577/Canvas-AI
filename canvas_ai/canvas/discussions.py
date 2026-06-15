"""Discussion topics: reading threads and (gated) writing replies/reactions."""

from __future__ import annotations

from canvas_ai.canvas.client import CanvasClient


def list_discussions(client: CanvasClient, course_id: int) -> list[dict]:
    return list(client.paginate(f"/courses/{course_id}/discussion_topics"))


def read_discussion(client: CanvasClient, course_id: int, topic_id: int) -> dict:
    """Topic metadata plus the full reply tree."""
    topic = client.get(f"/courses/{course_id}/discussion_topics/{topic_id}")
    view = client.get(f"/courses/{course_id}/discussion_topics/{topic_id}/view")
    topic["entries"] = view.get("view", [])
    return topic


def post_reply(client: CanvasClient, course_id: int, topic_id: int, message: str) -> dict:
    """Post a top-level reply. Callers should route through the write gate first."""
    return client.post(
        f"/courses/{course_id}/discussion_topics/{topic_id}/entries",
        data={"message": message},
    )


def reply_to_entry(
    client: CanvasClient, course_id: int, topic_id: int, entry_id: int, message: str
) -> dict:
    """Reply to a specific existing entry (i.e. 'react to' another post)."""
    return client.post(
        f"/courses/{course_id}/discussion_topics/{topic_id}/entries/{entry_id}/replies",
        data={"message": message},
    )
