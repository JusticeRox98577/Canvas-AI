"""Taking Classic Quizzes via the Canvas Quiz Submissions API.

Only "Classic" quizzes are reachable over REST. "New Quizzes" (the LTI-based
engine) are not exposed by the API and cannot be automated here.

Like assignment submissions, finishing a quiz is high-stakes: callers start the
attempt and save answers, but the final `complete()` is gated the same way as
graded submissions (confirm unless AUTO_SUBMIT is on).
"""

from __future__ import annotations

from typing import Any

from canvas_ai.canvas.client import CanvasClient

CHOICE_TYPES = {"multiple_choice_question", "true_false_question"}
MULTI_TYPES = {"multiple_answers_question"}
TEXT_TYPES = {"short_answer_question", "essay_question"}
NUMERIC_TYPES = {"numerical_question"}
SUPPORTED = CHOICE_TYPES | MULTI_TYPES | TEXT_TYPES | NUMERIC_TYPES


def _submissions(data: dict) -> list[dict]:
    return data.get("quiz_submissions") or ([data["quiz_submission"]] if data.get("quiz_submission") else [])


def start_submission(client: CanvasClient, course_id: int, quiz_id: int) -> dict:
    """Begin (or resume) an attempt and return the active quiz submission."""
    try:
        data = client.post(f"/courses/{course_id}/quizzes/{quiz_id}/submissions")
        subs = _submissions(data)
        if subs:
            return subs[0]
    except Exception:  # noqa: BLE001 - an in-progress attempt makes POST fail; resume it.
        pass
    return current_submission(client, course_id, quiz_id)


def current_submission(client: CanvasClient, course_id: int, quiz_id: int) -> dict:
    data = client.get(f"/courses/{course_id}/quizzes/{quiz_id}/submission")
    subs = _submissions(data)
    if not subs:
        raise RuntimeError("No quiz submission found. Start the quiz first.")
    return subs[0]


def get_questions(client: CanvasClient, submission_id: int) -> list[dict]:
    data = client.get(f"/quiz_submissions/{submission_id}/questions")
    return data.get("quiz_submission_questions", [])


def save_answers(
    client: CanvasClient,
    submission_id: int,
    attempt: int,
    validation_token: str,
    quiz_questions: list[dict[str, Any]],
) -> dict:
    """Flag/record answers on an in-progress attempt (does NOT submit)."""
    body = {
        "attempt": attempt,
        "validation_token": validation_token,
        "quiz_questions": quiz_questions,
    }
    return client.post(f"/quiz_submissions/{submission_id}/questions", json=body)


def complete(
    client: CanvasClient,
    course_id: int,
    quiz_id: int,
    submission_id: int,
    attempt: int,
    validation_token: str,
) -> dict:
    """Turn in the quiz. High-stakes: callers must gate this."""
    body = {"attempt": attempt, "validation_token": validation_token}
    return client.post(
        f"/courses/{course_id}/quizzes/{quiz_id}/submissions/{submission_id}/complete",
        json=body,
    )
