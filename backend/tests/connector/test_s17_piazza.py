"""S17 Piazza connector: fixture JSON through a fake piazza-api transport (no live Piazza).
docs/specs/S17-piazza-connector.md.
"""

import inspect
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.connectors.base import (
    AuthExpired,
    ConnectorContext,
    NCourse,
    NPost,
    PlatformError,
    get_connector,
)
from app.connectors.base import SyncScope as Scope
from app.connectors.browser.manager import login_spec_for
from app.connectors.piazza._vendored.client import PiazzaClient, _TimeoutSession
from app.connectors.piazza._vendored.normalizer import PiazzaNormalizer
from app.connectors.piazza.connector import PiazzaConnector
from app.connectors.piazza.login import PIAZZA_LOGIN, page_shows_logged_in
from app.connectors.piazza.mapping import author_role, is_current_term, to_npost
from app.core.clock import FixedClock
from tests.piazza_fake import CS220, CS311, STATE, FakePiazza, fx, make_connector

NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)


def ctx(state: Any = STATE, last_success_at: datetime | None = None) -> ConnectorContext:
    secret = state if isinstance(state, str) else json.dumps(state)
    return ConnectorContext(
        user_id=uuid4(),
        platform="piazza",
        secret=SecretStr(secret),
        last_success_at=last_success_at,
        clock=FixedClock(NOW),
    )


async def collect(conn: PiazzaConnector, c: ConnectorContext, scope: Scope | None = None) -> list:
    return [r async for r in conn.fetch(c, scope or Scope())]


def raw_post(nr: str) -> dict[str, Any]:
    return fx("posts_cs311.json")[nr]["result"]


def npost(nr: str) -> NPost:
    raw = raw_post(nr)
    return to_npost(PiazzaNormalizer().normalize_thread(raw, CS311), raw, NOW)


# --- S17-T01: labelled body ------------------------------------------------------------------
def test_s17_t01_normalizer_folds_question_and_answers_into_one_labelled_post() -> None:
    p = npost("2")
    assert p.kind == "piazza" and p.title == "Is BFS on the midterm?"
    assert p.body == (
        "Q: Is BFS/DFS on the midterm since Lecture 9 started graphs?\n\n"
        "A (instructor): The midterm covers material through dynamic programming, not graphs.\n\n"
        "A (student): I think graphs are on Midterm 2."
    )
    assert "Thanks" not in p.body  # followups are not part of the body
    assert p.posted_at == datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
    assert p.source_updated_at == datetime(2026, 11, 10, 18, 30, tzinfo=UTC)
    assert p.platform_id == f"{CS311}:2" and p.course_platform_id == CS311


def test_s17_t01_note_uses_newest_revision_as_plain_text() -> None:
    p = npost("3")
    assert p.body == ("Note: Midterm 1 is cumulative through dynamic programming. Room: ILC S131 .")


# --- S17-T02: source URL ---------------------------------------------------------------------
def test_s17_t02_source_url_is_piazza_class_post_url() -> None:
    assert npost("1").source_url == f"https://piazza.com/class/{CS311}/post/1"


# --- S17-T03: no names -----------------------------------------------------------------------
def test_s17_t03_author_mapped_to_role_never_a_name() -> None:
    assert npost("3").author == "Instructor"
    assert npost("2").author == "Anonymous"  # anon "stud": hidden from classmates
    assert npost("1").author == "Student"
    assert author_role({"history": [{"anon": "full"}], "tags": ["instructor-note"]}) == "Anonymous"


async def test_s17_t03_no_names_or_user_ids_in_any_synced_record() -> None:
    conn, _ = make_connector()
    records = await collect(conn, ctx())
    dumped = json.dumps([r.model_dump(mode="json") for r in records])
    for secret in ("Jordan Fakename", "jfake@example.edu", "fakeuid"):
        assert secret not in dumped
    assert {r.author for r in records if isinstance(r, NPost)} <= {
        "Instructor",
        "Student",
        "Anonymous",
    }


# --- full sync: courses + posts --------------------------------------------------------------
async def test_s17_full_sync_yields_current_term_courses_and_posts() -> None:
    conn, fake = make_connector()
    c = ctx()
    records = await collect(conn, c)
    courses = [r for r in records if isinstance(r, NCourse)]
    assert [(x.platform_id, x.code, x.term, x.name) for x in courses] == [
        (CS311, "COMPSCI 311", "Fall 2026", "Introduction to Algorithms"),
        (CS220, "CS 220", "Fall 2026", "Programming Methodology"),
    ]  # Spring 2025 class dropped (S17 rule 2)
    assert courses[0].source_url == f"https://piazza.com/class/{CS311}"
    posts = [r for r in records if isinstance(r, NPost)]
    assert [p.platform_id for p in posts] == [f"{CS311}:3", f"{CS311}:2", f"{CS311}:1"]
    assert fake.methods() == [
        "user.status",
        "network.get_my_feed",
        "content.get",
        "content.get",
        "content.get",
        "network.get_my_feed",
    ]
    assert c.incomplete == set()  # full listing of a short feed


def test_s17_current_term_filter() -> None:
    assert is_current_term("Fall 2026", NOW)
    assert not is_current_term("Spring 2026", NOW)
    assert is_current_term("Winter 2027", datetime(2027, 1, 5, tzinfo=UTC))
    assert is_current_term("Fall '26", NOW)
    assert is_current_term("Whenever", NOW)  # unreadable term: kept


# --- S17-T04: unchanged feed items skip get_post --------------------------------------------
async def test_s17_t04_unchanged_feed_items_do_not_trigger_get_post() -> None:
    conn, fake = make_connector()
    c = ctx(last_success_at=datetime(2026, 11, 11, tzinfo=UTC))
    records = await collect(conn, c, Scope(kind="course", course_platform_id=CS311))
    assert [r.platform_id for r in records] == [f"{CS311}:3"]
    gets = [x["params"]["cid"] for x in fake.calls if x["method"] == "content.get"]
    assert gets == [3]
    assert (CS311, "posts") in c.incomplete  # unchanged posts aren't yielded → no removal


async def test_s17_feed_cap_marks_listing_incomplete() -> None:
    conn, fake = make_connector(max_posts=2)
    c = ctx()
    records = await collect(conn, c, Scope(kind="course", course_platform_id=CS311))
    assert len(records) == 2
    assert fake.calls[0]["params"]["limit"] == 2
    assert (CS311, "posts") in c.incomplete


async def test_s17_unusable_post_is_skipped_not_fatal() -> None:
    fake = FakePiazza()
    del fake.posts["2"]
    conn, _ = make_connector(fake)
    c = ctx()
    records = await collect(conn, c, Scope(kind="course", course_platform_id=CS311))
    assert [r.platform_id for r in records] == [f"{CS311}:3", f"{CS311}:1"]
    assert (CS311, "posts") in c.incomplete


async def test_s17_item_and_material_scopes() -> None:
    conn, fake = make_connector()
    item = Scope(kind="item", course_platform_id=CS311, platform_id=f"{CS311}:1")
    assert [r.platform_id for r in await collect(conn, ctx(), item)] == [f"{CS311}:1"]
    mat = Scope(kind="material", course_platform_id=CS311, platform_id="x")
    assert await collect(conn, ctx(), mat) == []
    assert fake.methods() == ["content.get"]


# --- S17-T05: auth failure → AuthExpired; transient → PlatformError -------------------------
async def test_s17_t05_not_logged_in_response_raises_auth_expired() -> None:
    conn, _ = make_connector(FakePiazza(override={"user.status": fx("not_logged_in.json")}))
    with pytest.raises(AuthExpired):
        await collect(conn, ctx())
    with pytest.raises(AuthExpired):
        await conn.validate(ctx())


async def test_s17_t05_http_401_raises_auth_expired() -> None:
    conn, _ = make_connector(FakePiazza(status=401))
    with pytest.raises(AuthExpired):
        await collect(conn, ctx())


@pytest.mark.parametrize(
    "secret",
    [
        "not json",
        json.dumps([1]),
        json.dumps({"cookies": [{"name": "session_id", "value": "x", "domain": "evil.com"}]}),
    ],
)
async def test_s17_t05_missing_or_unreadable_session_raises_auth_expired(secret: str) -> None:
    conn, fake = make_connector()
    with pytest.raises(AuthExpired):
        await collect(conn, ctx(secret))
    assert fake.calls == []


async def test_s17_transient_errors_raise_platform_error() -> None:
    conn, _ = make_connector(FakePiazza(status=503))
    with pytest.raises(PlatformError):
        await collect(conn, ctx())
    conn, _ = make_connector(FakePiazza(override={"user.status": {"result": None, "error": "x"}}))
    with pytest.raises(PlatformError):
        await collect(conn, ctx())


async def test_s17_validate_returns_no_personal_info() -> None:
    conn, _ = make_connector()
    info = await conn.validate(ctx())
    assert info.account_label is None and info.platform_user_id is None


# --- S17-T06: read-only client, session cookies only ----------------------------------------
def test_s17_t06_client_has_no_login_post_or_edit_methods() -> None:
    names = {n for n, _ in inspect.getmembers(PiazzaClient) if not n.startswith("__")}
    public = {n for n in names if not n.startswith("_")}
    assert public == {"from_storage_state", "session", "list_courses", "list_posts", "get_post"}
    banned = ("login", "create", "edit", "update", "delete", "mark", "post_", "reply", "follow")
    assert not [n for n in names if any(b in n.lower() for b in banned)]
    src = inspect.getsource(PiazzaClient)
    assert "user_login" not in src and "password" not in src


async def test_s17_t06_only_read_methods_and_piazza_cookies_are_sent() -> None:
    conn, fake = make_connector()
    await collect(conn, ctx())
    assert set(fake.methods()) <= {"user.status", "network.get_my_feed", "content.get"}
    for call in fake.calls:
        assert call["http"] == "POST" and call["url"].startswith("https://piazza.com/logic/api")
        assert call["csrf"] == "pz-session"  # piazza-api sends session_id as CSRF-Token
        assert "session_id=pz-session" in call["cookie"]
        assert "sso-secret" not in call["cookie"] and "duo-secret" not in call["cookie"]


def test_s17_throttle_at_most_one_request_per_second() -> None:
    clock = [100.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        clock[0] += s

    session = _TimeoutSession(5.0, monotonic=lambda: clock[0], sleep=sleep)
    session.mount("https://", FakePiazza())
    for _ in range(3):
        session.post("https://piazza.com/logic/api?method=user.status", data="{}")
        clock[0] += 0.25
    assert slept == [0.75, 0.75]


# --- registration + S13 live login -----------------------------------------------------------
def test_s17_registered_and_login_spec_available() -> None:
    import app.connectors.registry  # noqa: F401

    assert isinstance(get_connector("piazza"), PiazzaConnector)
    spec = login_spec_for("piazza")
    assert spec is PIAZZA_LOGIN and spec.platform == "piazza"
    assert spec.start_url.startswith("https://piazza.com/") and spec.check_url.endswith("/class")


def test_s17_login_detection() -> None:
    feed_page = "<html><body><div id='feed'>Class feed</div></body></html>"
    login_page = "<html><body><form><input type='password' name='password'></form></body></html>"
    assert page_shows_logged_in(f"https://piazza.com/class/{CS311}", feed_page)
    assert page_shows_logged_in("https://piazza.com/class", feed_page)
    assert not page_shows_logged_in("https://piazza.com/account/login", feed_page)
    assert not page_shows_logged_in("https://piazza.com/class", login_page)
    assert not page_shows_logged_in("https://piazza.com/", feed_page)
    assert not page_shows_logged_in("https://webauth.umass.edu/class", feed_page)
    assert not page_shows_logged_in("https://piazza.com.evil.example/class", feed_page)
