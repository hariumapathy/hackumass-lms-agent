"""S14 pure functions (fixture-tested): HTML → Gradescope courses/assignments → NCourse/NItem.

Course list: vendored gradescope-mcp parser (keeps the role). Assignments: `gradescopeapi`'s
student-view parser. Dates: timezone-aware; naive values are read as America/New_York.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import dateutil.parser
from bs4 import BeautifulSoup
from gradescopeapi.classes._helpers._assignment_helpers import get_assignments_student_view
from gradescopeapi.classes.assignments import Assignment
from pydantic import BaseModel

from app.connectors.base import AuthExpired, NCourse, NItem, PlatformError
from app.connectors.gradescope._vendored.auth_checks import _is_logged_out_page, _is_login_path
from app.connectors.gradescope._vendored.courses import _parse_account_courses
from app.connectors.gradescope.login import GRADESCOPE_BASE_URL
from app.db.models import ItemType

log = logging.getLogger("app.connectors.gradescope")

DEFAULT_TZ = "America/New_York"
LAYOUT_CHANGED = "layout_changed"


class GsCourse(BaseModel):
    id: str
    name: str  # short name, e.g. "COMPSCI 311"
    full_name: str = ""
    term: str = ""
    role: str  # student | instructor | other
    num_assignments: str = ""


def check_logged_in(response_html: str, url: str) -> None:
    """Raise AuthExpired for Gradescope's login page or logged-out page (vendored checks)."""
    from urllib.parse import urlsplit

    if _is_login_path(urlsplit(url).path):
        raise AuthExpired("Gradescope served its login page")
    if _is_logged_out_page(BeautifulSoup(response_html, "html.parser"), url):
        raise AuthExpired("Gradescope served its logged-out page with the login form")


def parse_course_list(html: str) -> list[GsCourse]:
    parsed = _parse_account_courses(BeautifulSoup(html, "html.parser"))
    if not parsed["has_container"] and not parsed["courses"]:
        raise PlatformError(LAYOUT_CHANGED)
    if parsed["unreadable"] or parsed["unmatched_ids"]:
        log.warning(
            "gradescope account page: %s unreadable boxes, %s unmatched course links",
            parsed["unreadable"],
            len(parsed["unmatched_ids"]),
        )
    return [GsCourse.model_validate(c) for c in parsed["courses"]]


def student_courses(courses: list[GsCourse]) -> list[GsCourse]:
    """S14 rule 2: only courses where the student's role is `student`."""
    return [c for c in courses if c.role == "student"]


def to_ncourse(c: GsCourse, base_url: str = GRADESCOPE_BASE_URL) -> NCourse:
    return NCourse(
        platform_id=c.id,
        name=c.full_name or c.name,
        code=c.name or None,
        term=c.term or None,
        source_url=f"{base_url}/courses/{c.id}",
    )


# --- assignments ------------------------------------------------------------------------------
_DATE_CLASSES = ("submissionTimeChart--releaseDate", "submissionTimeChart--dueDate")


def _sanitize_dates(soup: BeautifulSoup) -> None:
    """Blank out unparseable datetimes so gradescopeapi doesn't raise (rule 3: never guess)."""
    for cls in _DATE_CLASSES:
        for el in soup.find_all(class_=cls):
            value = el.get("datetime")
            if not value:
                continue
            try:
                dateutil.parser.parse(str(value))
            except (ValueError, OverflowError):
                log.warning("gradescope: unparseable date %r ignored", value)
                el["datetime"] = ""


def _ensure_tail_row(soup: BeautifulSoup) -> None:
    """gradescopeapi skips the last `tr[role=row]` (the upload dropzone template). If a page has no
    such tail row, add an empty one so the last assignment isn't dropped."""
    rows = soup.find_all("tr", role="row")
    if len(rows) < 2:
        return
    last = rows[-1]
    is_dropzone = "dropzonePreview" in " ".join(last.get("class") or []) or (
        last.select_one('[class*="dropzonePreview"]') is not None
    )
    if not is_dropzone and last.find("th") is not None:
        tail = soup.new_tag("tr", attrs={"role": "row"})
        last.insert_after(tail)


def parse_assignments(html: str) -> list[Assignment]:
    """Student view of a course page → gradescopeapi `Assignment`s. No table → layout_changed."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="assignments-student-table")
    if table is None and not soup.find_all("tr", role="row"):
        raise PlatformError(LAYOUT_CHANGED)
    _sanitize_dates(soup)
    _ensure_tail_row(soup)
    try:
        return get_assignments_student_view(soup)
    except (IndexError, KeyError, AttributeError, TypeError, ValueError) as exc:
        raise PlatformError(LAYOUT_CHANGED) from exc


_EXAM = re.compile(r"\b(midterm|exam|final)\b", re.I)
_QUIZ = re.compile(r"\bquiz(zes)?\b", re.I)
_LAB = re.compile(r"\blab\b", re.I)
_PROJECT = re.compile(r"\bproject\b", re.I)


def item_type(title: str) -> ItemType:
    """S11 rule 2 title rules (Gradescope has no quiz flag, so quizzes match by title)."""
    if _EXAM.search(title):
        return "exam"
    if _QUIZ.search(title):
        return "quiz"
    if _LAB.search(title):
        return "lab"
    if _PROJECT.search(title):
        return "project"
    return "assignment"


def aware(value: Any, tz: str = DEFAULT_TZ) -> datetime | None:
    """Timezone-aware datetime; naive → `tz` (S14 rule 3); empty/unparseable → None."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = dateutil.parser.parse(value)
        except (ValueError, OverflowError):
            log.warning("gradescope: unparseable date %r ignored", value)
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=ZoneInfo(tz)) if value.tzinfo is None else value


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def assignment_platform_id(a: Assignment) -> str:
    """Gradescope's numeric id; an unsubmittable row has none → stable id from the title."""
    if a.assignment_id:
        return str(a.assignment_id)
    digest = hashlib.sha1(a.name.strip().encode()).hexdigest()[:12]  # noqa: S324
    return f"name-{digest}"


def to_nitem(
    a: Assignment,
    course_platform_id: str,
    tz: str = DEFAULT_TZ,
    base_url: str = GRADESCOPE_BASE_URL,
) -> NItem:
    title = " ".join(a.name.split())
    released, due, late = (
        aware(a.release_date, tz),
        aware(a.due_date, tz),
        aware(a.late_due_date, tz),
    )
    status = " ".join(str(a.submissions_status or "").split()) or None
    url = f"{base_url}/courses/{course_platform_id}"
    if a.assignment_id:
        url += f"/assignments/{a.assignment_id}"
    return NItem(
        platform_id=assignment_platform_id(a),
        course_platform_id=course_platform_id,
        type=item_type(title),
        title=title,
        due_at=due,
        points=_num(a.max_grade),
        source_url=url,
        raw={
            "released_at": released.isoformat() if released else None,
            "late_due_at": late.isoformat() if late else None,
            "submission_status": status,
            "score": _num(a.grade),
            "max_score": _num(a.max_grade),
        },
    )
