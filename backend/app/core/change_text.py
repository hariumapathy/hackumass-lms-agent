"""Plain-language one-line summaries of a `changes` row (Today view, /changes, agent tools)."""

from typing import Any

_FIELDS = {"due_at": "due date", "points": "points", "body": "text", "title": "title"}


def change_summary(course_code: str | None, title: str | None, field: str, new_value: Any) -> str:
    """'COMPSCI 311 Midterm 1: due date changed'; status changes read 'was removed' / 'is back'."""
    head = " ".join(x for x in (course_code, title) if x).strip() or "A course item"
    if field == "status":
        if new_value == "removed":
            return f"{head} was removed"
        if new_value == "active":
            return f"{head} is back"
    return f"{head}: {_FIELDS.get(field, field)} changed"
