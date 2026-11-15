"""S11 Canvas connector: pure mapping rules (no HTTP)."""

import pytest

from app.connectors.canvas.mapping import (
    html_to_text,
    is_exam_title,
    item_type,
    normalize_course_code,
    supported_file,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPSCI 311 SEC 01", "COMPSCI 311"),
        ("  MATH  235   SEC 02 ", "MATH 235"),
        ("compsci 311 sec 1", "COMPSCI 311"),
        ("COMPSCI 320 Section 4", "COMPSCI 320"),
        ("CICS 110 LEC 01", "CICS 110"),
        ("STATS 515", "STATS 515"),
        ("", None),
        (None, None),
    ],
)
def test_s11_t03_course_code_normalization(raw: str | None, expected: str | None) -> None:
    assert normalize_course_code(raw) == expected


@pytest.mark.parametrize(
    ("assignment", "expected"),
    [
        ({"name": "Quiz 3: Greedy", "is_quiz_assignment": True}, "quiz"),
        ({"name": "Weekly check-in", "is_quiz_lti_assignment": True}, "quiz"),
        ({"name": "Midterm 1", "is_quiz_assignment": False}, "exam"),
        ({"name": "Final Exam"}, "exam"),
        ({"name": "FINAL"}, "exam"),
        ({"name": "Lab 4 - Dynamic Programming"}, "lab"),
        ({"name": "Final Project Proposal"}, "project"),
        ({"name": "Project 2"}, "project"),
        ({"name": "Homework 5"}, "assignment"),
        ({"name": "Examples of proofs"}, "assignment"),
        ({"name": "Collaboration policy"}, "assignment"),
    ],
)
def test_s11_t04_item_type_mapping(assignment: dict, expected: str) -> None:
    assert item_type(assignment) == expected


def test_s11_t05_exam_title_pattern() -> None:
    assert is_exam_title("Midterm 2")
    assert is_exam_title("final exam review session") is True
    assert not is_exam_title("Office hours")


def test_s11_t06_announcement_html_to_clean_text_keeps_links() -> None:
    html = (
        "<p>Hi all,</p><p>Midterm 1 is now in <strong>Hasbrouck 20</strong>. See the "
        '<a href="https://example.instructure.com/courses/12345/files/501">review sheet</a>.</p>'
        "<ul><li>Bring a pencil</li><li>No&nbsp;calculators &amp; no notes</li></ul>"
        '<p><a href="https://example.com/x">https://example.com/x</a></p>'
        "<script>alert(1)</script>"
    )
    assert html_to_text(html) == (
        "Hi all,\n"
        "Midterm 1 is now in Hasbrouck 20. See the review sheet "
        "(https://example.instructure.com/courses/12345/files/501).\n"
        "- Bring a pencil\n"
        "- No calculators & no notes\n"
        "https://example.com/x"
    )
    assert html_to_text(None) == ""
    assert html_to_text("plain text") == "plain text"


@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("Lecture 7.pdf", True),
        ("slides.PPTX", True),
        ("notes.docx", True),
        ("readme.txt", True),
        ("notes.md", True),
        ("page.html", True),
        ("graph.png", False),
        ("code.zip", False),
        ("old.ppt", False),
        ("noextension", False),
    ],
)
def test_s11_t08_supported_file_types(name: str, ok: bool) -> None:
    assert supported_file({"display_name": name, "filename": name}) is ok
