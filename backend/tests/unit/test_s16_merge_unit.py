"""S16 merge: pure matching and precedence rules. docs/specs/S16-merge-and-changes.md."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.sync.merge import (
    CourseRow,
    ItemRow,
    SourceRow,
    canonical_fields,
    clean_title,
    items_match,
    match_course,
    match_item,
    normalize_course_code,
    normalize_term,
)

NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)


def course(code: str | None, term: str | None, *platforms: str, age: int = 0) -> CourseRow:
    return CourseRow(
        id=uuid4(),
        code=code,
        term=term,
        platforms=frozenset(platforms),
        created_at=NOW - timedelta(minutes=age),
    )


def src(platform: str, title: str, due: datetime | None = NOW, **kw) -> SourceRow:  # noqa: ANN003
    base = dict(
        id=uuid4(),
        item_id=None,
        course_id=uuid4(),
        platform=platform,
        title=title,
        due_at=due,
        points=None,
        type="assignment",
        description=None,
        status="active",
        created_at=NOW,
    )
    return SourceRow(**{**base, **kw})  # type: ignore[arg-type]


def item(title: str, due: datetime | None = NOW, *platforms: str, type: str = "assignment"):  # noqa: ANN201, A002
    return ItemRow(
        id=uuid4(),
        course_id=uuid4(),
        type=type,  # type: ignore[arg-type]
        title=title,
        due_at=due,
        points=None,
        status="active",
        platforms=frozenset(platforms or ("canvas",)),
    )


# --- S16-T01: course code normalization + aliases --------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPSCI 311 SEC 01", ("COMPSCI", "311")),
        ("CS 311", ("COMPSCI", "311")),
        ("CMPSCI311", ("COMPSCI", "311")),
        ("compsci-320", ("COMPSCI", "320")),
        ("STAT 315", ("STATS", "315")),
        ("STATS 315", ("STATS", "315")),
        ("MATH 235H", ("MATH", "235H")),
        ("", None),
        ("Algorithms", None),
    ],
)
def test_s16_t01_course_code_normalization(raw: str, expected: tuple[str, str] | None) -> None:
    assert normalize_course_code(raw) == expected


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Fall 2026", "fall  2026", True),
        ("Fall 2026", "2026 Fall", True),
        ("Fall 2026", "FA26", True),
        ("Fall 2026", "Spring 2026", False),
        ("Fall 2026", "Fall 2025", False),
        (None, None, True),
        ("Fall 2026", None, False),
    ],
)
def test_s16_t01_term_normalization(a: str | None, b: str | None, same: bool) -> None:
    assert (normalize_term(a) == normalize_term(b)) is same


# --- S16-T02: same code/term on Canvas + Gradescope -> one course ----------------------------
def test_s16_t02_canvas_and_gradescope_same_code_term_match() -> None:
    canvas = course("COMPSCI 311", "Fall 2026", "canvas")
    gs = course("CS 311", "Fall 2026", "gradescope")
    assert match_course(gs, [canvas]) is canvas


def test_s16_t02_different_term_or_code_no_match() -> None:
    canvas = course("COMPSCI 311", "Fall 2026", "canvas")
    assert match_course(course("COMPSCI 311", "Spring 2026", "gradescope"), [canvas]) is None
    assert match_course(course("COMPSCI 320", "Fall 2026", "gradescope"), [canvas]) is None
    assert match_course(course(None, "Fall 2026", "gradescope"), [canvas]) is None


def test_s16_t02_two_sections_same_platform_stay_separate() -> None:
    a = course("COMPSCI 311", "Fall 2026", "canvas")
    b = course("COMPSCI 311", "Fall 2026", "canvas")
    assert match_course(b, [a]) is None  # same platform twice: separate sections
    # A Gradescope course that could join either section is ambiguous -> not merged.
    assert match_course(course("COMPSCI 311", "Fall 2026", "gradescope"), [a, b]) is None


# --- S16-T03: similar title + close dates -> merged -----------------------------------------
@pytest.mark.parametrize(
    ("canvas_title", "gs_title"),
    [
        ("HW4", "Homework 4 (PDF)"),
        ("Homework 4: Dynamic Programming", "HW 4 - Dynamic Programming"),
        ("Midterm 1", "Midterm 1 (Gradescope submission)"),
        ("Problem Set 3", "PS3"),
        ("Project 2: Scheduler", "Submit Project 2"),
    ],
)
def test_s16_t03_similar_titles_close_dates_merge(canvas_title: str, gs_title: str) -> None:
    canvas = item(canvas_title, NOW)
    gs = src("gradescope", gs_title, NOW + timedelta(hours=2))
    assert match_item(gs, [canvas]) is canvas


def test_s16_t03_dates_more_than_36h_apart_do_not_merge() -> None:
    canvas = item("HW 4", NOW)
    assert match_item(src("gradescope", "HW 4", NOW + timedelta(hours=37)), [canvas]) is None
    assert match_item(src("gradescope", "HW 4", NOW + timedelta(hours=36)), [canvas]) is canvas


def test_s16_t03_one_null_due_still_merges() -> None:
    assert match_item(src("gradescope", "HW 4", None), [item("HW 4", NOW)]) is not None
    assert match_item(src("gradescope", "HW 4", NOW), [item("HW 4", None)]) is not None


def test_s16_t03_type_compatibility() -> None:
    exam = item("Midterm 1", NOW, type="exam")
    assert match_item(src("gradescope", "Midterm 1", type="exam"), [exam]) is exam
    # A Gradescope "assignment" titled like an exam still joins the exam (exam wins the type).
    assert match_item(src("gradescope", "Midterm 1", type="assignment"), [exam]) is exam
    # A real assignment never merges with an exam, even with the same words.
    hw = item("Exam review homework", NOW, type="assignment")
    assert not items_match(src("gradescope", "Exam review", type="exam"), hw)
    assert match_item(src("gradescope", "Lab 2", type="lab"), [item("Lab 2", NOW)]) is not None


def test_s16_t03_same_platform_never_merges() -> None:
    canvas = item("HW 4", NOW, "canvas")
    assert match_item(src("canvas", "HW 4"), [canvas]) is None


def test_s16_t03_dissimilar_titles_do_not_merge() -> None:
    assert match_item(src("gradescope", "Reading response"), [item("Lab 3", NOW)]) is None


def test_s16_clean_title_strips_noise() -> None:
    assert clean_title("Homework 4 (PDF) - Submit on Gradescope") == "homework 4"
    assert clean_title("HW4") == "homework 4"


# --- S16-T04: ordinal guard -----------------------------------------------------------------
@pytest.mark.parametrize(
    ("a", "b"),
    [("Midterm 1", "Midterm 2"), ("HW 4", "HW 5"), ("Homework 4", "HW5"), ("Lab 10", "Lab 1")],
)
def test_s16_t04_ordinal_guard(a: str, b: str) -> None:
    exam = "exam" if "Midterm" in a else "assignment"
    assert match_item(src("gradescope", b, type=exam), [item(a, NOW, type=exam)]) is None


# --- S16-T05: ambiguous candidates -> not merged ---------------------------------------------
def test_s16_t05_two_candidates_is_ambiguous() -> None:
    a = item("Project report", NOW)
    b = item("Project report", NOW + timedelta(hours=3))
    assert match_item(src("gradescope", "Project report"), [a, b]) is None
    # With only one candidate it would merge.
    assert match_item(src("gradescope", "Project report"), [a]) is a


# --- S16-T06: precedence --------------------------------------------------------------------
def test_s16_t06_canvas_title_and_due_win() -> None:
    gs = src("gradescope", "Homework 4 (PDF)", NOW + timedelta(hours=1), points=50, type="exam")
    cv = src("canvas", "HW4", NOW, points=60)
    c = canonical_fields([gs, cv])
    assert (c.title, c.due_at, c.points) == ("HW4", NOW, 60)
    assert c.type == "exam"  # exam wins over others


def test_s16_t06_gradescope_fills_null_canvas_due() -> None:
    cv = src("canvas", "HW4", None, points=None)
    gs = src("gradescope", "Homework 4", NOW, points=50)
    c = canonical_fields([cv, gs])
    assert (c.title, c.due_at, c.points) == ("HW4", NOW, 50)


def test_s16_t06_gradescope_beats_others() -> None:
    p = src("piazza", "hw4 thread", NOW - timedelta(hours=2), type="other")
    gs = src("gradescope", "Homework 4", NOW, type="assignment")
    c = canonical_fields([p, gs])
    assert (c.title, c.due_at, c.type) == ("Homework 4", NOW, "assignment")


def test_s16_t06_unknown_type_keeps_none() -> None:
    c = canonical_fields([src("canvas", "HW4", type=None)])
    assert c.type is None
