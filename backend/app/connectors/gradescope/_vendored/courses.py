# Vendored from https://github.com/Yuanpeng-Li/gradescope-mcp @ f8a46c8,
# src/gradescope_mcp/tools/courses.py, MIT License, (c) 2026 Yuanpeng Li
# (full text: LICENSE-gradescope-mcp in this folder).
# Modified: kept only the account-page course parser (`_parse_account_courses`, `_role_for_heading`
# and their helpers); removed the MCP tools, markdown output, roster parser and the connection /
# password-login imports; added type hints; `_role_for_heading` treats a "Your Courses"-style
# heading on a page without a Create Course button as `student` (gradescopeapi's default for a
# student-only account) instead of `other`.
# ruff: noqa: E501
"""Gradescope account-page course parser (by role)."""

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

# gradescopeapi reads the course box's assignment count with ``.text``, which
# glues the count to a child element: "1 assignmentNo Published Grades".
_GLUED_COUNT_RE = re.compile(r"^(\d+\s+assignments?)(?![a-z])\s*(\S.*)$")


def _assignment_count_text(value: Any) -> str:
    """The course box's assignment count, e.g. "1 assignment · No Published Grades"."""
    text = " ".join(str(value or "").split())
    match = _GLUED_COUNT_RE.match(text)
    if match:
        return f"{match.group(1)} · {match.group(2)}"
    return text or "N/A"


# A course box links to the course home page: "/courses/123" (optionally
# absolute or with a trailing slash). Deeper links are not course boxes.
_COURSE_HREF_RE = re.compile(r"^(?:https?://[^/]+)?/courses/(\d+)/?(?:[?#].*)?$")


def _classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value.split() if isinstance(value, str) else list(value)


def _text(tag: Any) -> str:
    return " ".join(tag.get_text(" ").split()) if tag is not None else ""


def _role_for_heading(heading: str | None, has_create_button: bool) -> str:
    """Map an account-page section heading to a role group.

    Gradescope titles its sections "Instructor Courses", "Course Staff",
    "Student Courses" and similar. Without any heading, fall back to the
    "Create Course" button (only instructors see it); a page with neither
    states no role, which is reported as "other" rather than guessed: a TA
    has no Create Course button but is not a student.
    """
    if heading is None:
        return "instructor" if has_create_button else "other"
    text = heading.lower()
    if "student" in text or "enrolled" in text:
        return "student"
    if any(word in text for word in ("instructor", "staff", "teaching", "reader", "grader")):
        return "instructor"
    # Modified: a plain "Your Courses" heading without the Create Course button is a
    # student-only account (gradescopeapi's default); with the button it stays "other".
    if "your courses" in text and not has_create_button:
        return "student"
    return "other"


def _is_course_box(tag: Tag) -> bool:
    if tag.name != "a" or not _COURSE_HREF_RE.match(str(tag.get("href") or "").strip()):
        return False
    return "courseBox" in _classes(tag) or tag.find(class_="courseBox--shortname") is not None


def _parse_account_courses(soup: BeautifulSoup) -> dict[str, Any]:
    """Parse the course boxes of a Gradescope account page.

    Replaces gradescopeapi's ``get_courses_info``, which only found course
    links that are ``<a>`` siblings after a term heading and decided
    instructor vs student solely by the "Create Course" button, so a TA
    without that button or a page whose boxes sit in other wrapper elements
    could come back as a silent empty list.

    Walks the page in document order, so each course box is attributed to
    the nearest preceding section heading (``.pageHeading``) and term
    (``.courseList--term``) whatever containers wrap it. Returns
    ``{"courses": [...], "boxes": n, "unreadable": n, "course_links": n,
    "has_container": bool}``.
    """
    has_create_button = soup.select_one(".js-createNewCourse") is not None
    heading = None
    term = None
    courses: list[dict[str, Any]] = []
    boxes = unreadable = 0
    seen: set[str] = set()
    link_ids: set[str] = set()
    course_links = 0
    for a in soup.find_all("a", href=True):
        match = _COURSE_HREF_RE.match(str(a["href"]).strip())
        if match:
            course_links += 1
            link_ids.add(match.group(1))
    box_ids: set[str] = set()
    for tag in soup.find_all(True):
        classes = _classes(tag)
        if tag.name in ("h1", "h2", "h3") and "pageHeading" in classes:
            heading = _text(tag) or None
            term = None
        elif "courseList--term" in classes:
            term = _text(tag) or None
        elif _is_course_box(tag):
            boxes += 1
            match = _COURSE_HREF_RE.match(str(tag["href"]).strip())
            assert match is not None
            course_id = match.group(1)
            box_ids.add(course_id)
            short = _text(tag.find(class_="courseBox--shortname"))
            if not short:
                unreadable += 1
                continue
            if course_id in seen:
                continue
            seen.add(course_id)
            assignments = tag.find(class_="courseBox--assignments")
            courses.append(
                {
                    "id": course_id,
                    "name": short,
                    "full_name": _text(tag.find(class_="courseBox--name")),
                    "term": term or "",
                    "heading": heading or "",
                    "role": _role_for_heading(heading, has_create_button),
                    # The separator keeps "1 assignment" apart from a child
                    # label such as "No Published Grades".
                    "num_assignments": (
                        _assignment_count_text(assignments.get_text("\n"))
                        if assignments is not None
                        else "N/A"
                    ),
                }
            )
    has_container = (
        soup.select_one("#account-show") is not None or soup.select_one(".courseList") is not None
    )
    return {
        "courses": courses,
        "boxes": boxes,
        "unreadable": unreadable,
        "course_links": course_links,
        "has_container": has_container,
        # Course IDs linked on the page that no course box carries: markup
        # this parser does not recognise, so those courses are not listed.
        "unmatched_ids": sorted(link_ids - box_ids, key=int),
    }
