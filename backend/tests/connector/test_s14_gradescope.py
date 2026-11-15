"""S14 Gradescope connector: fixture HTML through a fake requests adapter (no live Gradescope).
docs/specs/S14-gradescope-connector.md.
"""

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import requests
from gradescopeapi.classes.assignments import Assignment
from gradescopeapi.classes.connection import GSConnection
from pydantic import SecretStr
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

from app.connectors.base import AuthExpired, ConnectorContext, NCourse, NItem, PlatformError
from app.connectors.base import SyncScope as Scope
from app.connectors.gradescope.client import connection_from_storage_state
from app.connectors.gradescope.connector import GradescopeConnector
from app.connectors.gradescope.login import page_shows_logged_in
from app.connectors.gradescope.parsers import (
    check_logged_in,
    gs_submitted,
    item_type,
    parse_assignments,
    parse_course_list,
    student_courses,
    to_ncourse,
    to_nitem,
)
from app.core.clock import FixedClock

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "gradescope"
BASE = "https://www.gradescope.com"
NY = ZoneInfo("America/New_York")


def fixture(name: str) -> str:
    return (FIX / name).read_text()


STATE = {
    "cookies": [
        {
            "name": "_gradescope_session",
            "value": "gs-cookie",
            "domain": "www.gradescope.com",
            "path": "/",
            "secure": True,
        },
        {"name": "signed_token", "value": "gs-token", "domain": ".gradescope.com", "path": "/"},
        {
            "name": "shib_idp_session",
            "value": "sso-secret",
            "domain": "webauth.umass.edu",
            "path": "/",
        },
        {"name": "duo", "value": "duo-secret", "domain": ".duosecurity.com", "path": "/"},
    ],
    "origins": [],
}


class FixtureAdapter(BaseAdapter):
    """Serves fixture HTML by path; records every request (method, url)."""

    def __init__(self, routes: dict[str, tuple[int, str, dict[str, str]]]) -> None:
        super().__init__()
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        url = str(request.url)
        self.calls.append((str(request.method), url))
        status, body, headers = self.routes.get(urlsplit(url).path, (404, "Not found", {}))
        resp = requests.Response()
        resp.status_code = status
        resp._content = body.encode()  # type: ignore[attr-defined]
        resp._content_consumed = True  # type: ignore[attr-defined]
        resp.raw = io.BytesIO(b"")
        resp.url = url
        resp.encoding = "utf-8"
        resp.headers = CaseInsensitiveDict({"Content-Type": "text/html; charset=utf-8", **headers})
        resp.request = request
        return resp

    def close(self) -> None:
        pass


def page(html: str) -> tuple[int, str, dict[str, str]]:
    return (200, html, {})


ROUTES = {
    "/account": page(fixture("account_mixed.html")),
    "/courses/100001": page(fixture("course_student.html")),
    "/courses/100002": page(fixture("course_empty.html")),
    "/courses/100003": page(fixture("course_empty.html")),
}


def make_connector(routes: dict[str, Any]) -> tuple[GradescopeConnector, FixtureAdapter]:
    adapter = FixtureAdapter(routes)

    def factory(state: dict[str, Any], base_url: str) -> GSConnection:
        conn = connection_from_storage_state(state, base_url)
        conn.session.mount("https://", adapter)
        conn.session.mount("http://", adapter)
        return conn

    return (
        GradescopeConnector(min_interval_s=0, connection_factory=factory, save_debug=_no_debug),
        adapter,
    )


def _no_debug(name: str, html: str) -> None:
    pass


def ctx() -> ConnectorContext:
    return ConnectorContext(
        user_id=uuid4(),
        platform="gradescope",
        secret=SecretStr(json.dumps(STATE)),
        clock=FixedClock(datetime(2026, 11, 14, tzinfo=UTC)),
    )


async def collect(connector: GradescopeConnector, scope: Scope | None = None) -> list[Any]:
    return [r async for r in connector.fetch(ctx(), scope or Scope(kind="full"))]


# --- S14-T01 / T02: course list ----------------------------------------------------------------
def test_s14_t01_parse_course_list_ids_names_terms_roles() -> None:
    courses = parse_course_list(fixture("account_mixed.html"))
    got = [(c.id, c.name, c.full_name, c.term, c.role) for c in courses]
    assert got == [
        (
            "900001",
            "COMPSCI 121",
            "Intro to Problem Solving with Computers",
            "Fall 2026",
            "instructor",
        ),
        ("100001", "COMPSCI 311", "Introduction to Algorithms", "Fall 2026", "student"),
        ("100002", "MATH 235", "Introduction to Linear Algebra", "Fall 2026", "student"),
        ("100003", "COMPSCI 220", "Programming Methodology", "Spring 2026", "student"),
    ]


def test_s14_t01_student_only_page_counts_as_student() -> None:
    courses = parse_course_list(fixture("account_student_only.html"))
    assert [(c.id, c.role) for c in courses] == [("100001", "student")]


def test_s14_t02_only_student_role_courses_become_ncourse() -> None:
    ncourses = [
        to_ncourse(c) for c in student_courses(parse_course_list(fixture("account_mixed.html")))
    ]
    assert [c.platform_id for c in ncourses] == ["100001", "100002", "100003"]
    assert ncourses[0] == NCourse(
        platform_id="100001",
        name="Introduction to Algorithms",
        code="COMPSCI 311",
        term="Fall 2026",
        source_url="https://www.gradescope.com/courses/100001",
    )


async def test_s14_t02_fetch_skips_staff_course_and_handles_empty_course() -> None:
    connector, adapter = make_connector(ROUTES)
    records = await collect(connector)
    courses = [r.platform_id for r in records if isinstance(r, NCourse)]
    items = [r for r in records if isinstance(r, NItem)]
    assert courses == ["100001", "100002", "100003"]
    assert {i.course_platform_id for i in items} == {"100001"}  # empty courses: no items
    assert len(items) == 5
    assert not any("/courses/900001" in url for _, url in adapter.calls)


# --- S14-T03 / T04 / T07: assignment mapping ------------------------------------------------------
def items_by_title() -> dict[str, NItem]:
    return {
        i.title: i
        for i in (to_nitem(a, "100001") for a in parse_assignments(fixture("course_student.html")))
    }


def test_s14_t03_to_nitem_maps_title_ids_dates_status_score() -> None:
    hw = items_by_title()["Homework 1: Recurrences"]
    assert hw.platform_id == "200001"
    assert hw.course_platform_id == "100001"
    assert hw.source_url == "https://www.gradescope.com/courses/100001/assignments/200001"
    assert hw.due_at == datetime(2026, 9, 10, 3, 59, tzinfo=UTC)
    assert hw.due_at is not None and hw.due_at.utcoffset() is not None
    assert hw.points == 10.0
    assert hw.raw == {
        "released_at": "2026-09-02T09:00:00-04:00",
        "late_due_at": "2026-09-11T23:59:00-04:00",
        "submission_status": "Submitted",
        "submitted": True,
        "score": 8.5,
        "max_score": 10.0,
    }


def test_s14_t03_unsubmitted_and_no_due_date_and_bad_date() -> None:
    items = items_by_title()
    lab = items["Lab 2: Greedy Algorithms"]
    assert lab.platform_id == "200002"
    assert lab.raw["submission_status"] == "No Submission"
    assert lab.raw["submitted"] is False
    assert lab.raw["score"] is None and lab.points is None
    assert lab.due_at == datetime(2026, 11, 21, 4, 59, tzinfo=UTC)  # EST (-05:00)
    proposal = items["Final Project Proposal"]  # not submittable: no Gradescope id in the row
    assert proposal.due_at is None
    assert proposal.platform_id.startswith("name-")
    assert proposal.source_url == "https://www.gradescope.com/courses/100001"
    quiz = items["Quiz 3"]  # unparseable due date → null, never guessed
    assert quiz.due_at is None


def test_s14_t04_naive_datetime_is_america_new_york() -> None:
    exam = items_by_title()["Midterm Exam 1"]
    assert exam.due_at == datetime(2026, 10, 15, 21, 0, tzinfo=NY)
    assert exam.due_at is not None and exam.due_at.utcoffset() is not None
    assert exam.due_at.astimezone(UTC) == datetime(2026, 10, 16, 1, 0, tzinfo=UTC)
    naive = Assignment("1", "HW", None, datetime(2026, 12, 1, 12), None, "", "", "")  # type: ignore[arg-type]
    assert to_nitem(naive, "c").due_at == datetime(2026, 12, 1, 12, tzinfo=NY)


def test_s14_t07_type_mapping_reuses_s11_rules() -> None:
    assert item_type("Midterm Exam 1") == "exam"
    assert item_type("Final") == "exam"
    assert item_type("Quiz 3") == "quiz"
    assert item_type("Lab 2: Greedy Algorithms") == "lab"
    assert item_type("Final Project Proposal") == "exam"  # "final" wins, same as S11 order
    assert item_type("Project 2") == "project"
    assert item_type("Homework 1: Recurrences") == "assignment"
    types = {t: i.type for t, i in items_by_title().items()}
    assert types["Quiz 3"] == "quiz" and types["Lab 2: Greedy Algorithms"] == "lab"


def test_s14_last_assignment_kept_without_dropzone_tail_row() -> None:
    html = fixture("course_student.html").replace(
        '<tr role="row" class="dropzonePreview--fileNameHeader">\n'
        '      <td colspan="4"></td>\n    </tr>',
        "",
    )
    assert "dropzonePreview" not in html
    assert [a.name for a in parse_assignments(html)][-1] == "Quiz 3"


async def test_s14_course_scope_and_item_scope() -> None:
    connector, adapter = make_connector(ROUTES)
    items = await collect(connector, Scope(kind="course", course_platform_id="100001"))
    assert len(items) == 5 and all(isinstance(i, NItem) for i in items)
    assert [u for _, u in adapter.calls] == [f"{BASE}/courses/100001"]
    one = await collect(
        connector, Scope(kind="item", course_platform_id="100001", platform_id="200002")
    )
    assert [i.platform_id for i in one] == ["200002"]


# --- S14-T05: logged out → AuthExpired ------------------------------------------------------------
def test_s14_t05_check_logged_in_raises_on_login_page_and_logged_out_html() -> None:
    with pytest.raises(AuthExpired):
        check_logged_in(fixture("logged_out.html"), f"{BASE}/")
    with pytest.raises(AuthExpired):
        check_logged_in("<html></html>", f"{BASE}/login")
    check_logged_in(fixture("account_mixed.html"), f"{BASE}/account")  # no raise


async def test_s14_t05_redirect_to_login_raises_auth_expired() -> None:
    connector, _ = make_connector(
        {
            "/account": (302, "", {"Location": f"{BASE}/login"}),
            "/login": page(fixture("logged_out.html")),
        }
    )
    with pytest.raises(AuthExpired):
        await collect(connector)
    with pytest.raises(AuthExpired):
        await connector.validate(ctx())


async def test_s14_t05_logged_out_home_page_with_200_raises_auth_expired() -> None:
    connector, _ = make_connector({"/account": page(fixture("logged_out.html"))})
    with pytest.raises(AuthExpired):
        await collect(connector)


async def test_s14_t05_unreadable_secret_is_auth_expired() -> None:
    connector, _ = make_connector(ROUTES)
    bad = ctx().model_copy(update={"secret": SecretStr("not json")})
    with pytest.raises(AuthExpired):
        await connector.validate(bad)


def test_s14_login_detection_for_live_login() -> None:
    assert page_shows_logged_in(f"{BASE}/account", fixture("account_mixed.html"))
    assert not page_shows_logged_in(f"{BASE}/login", fixture("logged_out.html"))
    assert not page_shows_logged_in(f"{BASE}/", fixture("logged_out.html"))
    assert not page_shows_logged_in("https://webauth.umass.edu/idp", "<a href='/logout'>x</a>")


# --- S14-T06: layout changed ----------------------------------------------------------------------
def test_s14_t06_unparseable_table_raises_layout_changed() -> None:
    with pytest.raises(PlatformError, match="layout_changed"):
        parse_assignments(fixture("course_broken.html"))
    with pytest.raises(PlatformError, match="layout_changed"):
        parse_course_list("<html><body><p>Welcome</p><a href='/logout'>x</a></body></html>")


async def test_s14_t06_connector_saves_debug_html_on_layout_change() -> None:
    saved: list[str] = []
    connector, _ = make_connector(
        {**ROUTES, "/courses/100001": page(fixture("course_broken.html"))}
    )
    connector.save_debug = lambda name, html: saved.append(name)
    with pytest.raises(PlatformError, match="layout_changed"):
        await collect(connector)
    assert saved == ["course_100001"]


# --- S14-T08 / T09: session cookies only, never login or write ------------------------------------
def test_s14_t08_connection_loads_only_gradescope_cookies_never_password_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("password login must never be called")

    monkeypatch.setattr(GSConnection, "login", boom)
    monkeypatch.setattr(
        "gradescopeapi.classes.connection.login_set_session_cookies", boom, raising=True
    )
    monkeypatch.setattr(
        "gradescopeapi.classes.connection.get_auth_token_init_gradescope_session", boom
    )
    conn = connection_from_storage_state(STATE)
    names = {c.name: (c.value, c.domain) for c in conn.session.cookies}
    assert names == {
        "_gradescope_session": ("gs-cookie", "www.gradescope.com"),
        "signed_token": ("gs-token", ".gradescope.com"),
    }
    assert conn.logged_in and conn.account is not None


async def test_s14_t09_connector_never_invokes_write_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def spy(name: str) -> Any:
        def _f(*a: Any, **k: Any) -> None:
            calls.append(name)
            raise AssertionError(f"write method called: {name}")

        return _f

    for target in [
        "gradescopeapi.classes.assignments.update_assignment_date",
        "gradescopeapi.classes.assignments.update_assignment_title",
        "gradescopeapi.classes.extensions.update_student_extension",
        "gradescopeapi.classes.upload.upload_assignment",
        "gradescopeapi.classes.connection.GSConnection.login",
        "gradescopeapi.classes.connection.GSConnection.logout",
    ]:
        monkeypatch.setattr(target, spy(target))
    for method in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(requests.Session, method, spy(f"Session.{method}"))

    connector, adapter = make_connector(ROUTES)
    await connector.validate(ctx())
    await collect(connector)
    assert calls == []
    assert {m for m, _ in adapter.calls} == {"GET"}


def test_s14_throttle_waits_between_requests() -> None:
    from app.connectors.gradescope.client import GradescopeClient

    adapter = FixtureAdapter(ROUTES)
    conn = connection_from_storage_state(STATE)
    conn.session.mount("https://", adapter)
    now = [100.0]
    slept: list[float] = []
    client = GradescopeClient(
        conn, min_interval_s=1.0, monotonic=lambda: now[0], sleep=slept.append
    )
    client.get_html("/account")
    now[0] += 0.25
    client.get_html("/courses/100001")
    assert slept == [0.75]


@pytest.mark.parametrize(
    ("status", "score", "expected"),
    [
        ("Submitted", None, True),
        ("No Submission", None, False),
        ("Graded", None, True),
        ("Late Submission", None, True),
        ("Ungraded", None, False),
        ("", 7.0, True),  # a graded row shows the score instead of a status
        (None, None, False),
    ],
)
def test_submitted_gradescope_status(
    status: str | None, score: float | None, expected: bool
) -> None:
    assert gs_submitted(status, score) is expected
