"""Change summaries are plain language (Today view / agent)."""

from app.core.change_text import change_summary


def test_change_summary_fields_and_status() -> None:
    assert change_summary("COMPSCI 311", "Midterm 1", "due_at", "x") == (
        "COMPSCI 311 Midterm 1: due date changed"
    )
    assert change_summary("COMPSCI 311", "Midterm coverage", "status", "removed") == (
        "COMPSCI 311 Midterm coverage was removed"
    )
    assert change_summary("MATH 235", "Quiz 7", "status", "active") == "MATH 235 Quiz 7 is back"
    assert change_summary(None, None, "points", 5) == "A course item: points changed"
