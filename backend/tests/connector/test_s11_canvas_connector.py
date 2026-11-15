"""S11 Canvas connector against a respx-mocked Canvas (fixtures in tests/fixtures/canvas/)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.connectors.base import (
    AuthExpired,
    ConnectorContext,
    NCourse,
    NItem,
    NMaterial,
    NPost,
    PlatformError,
    SyncScope,
)
from app.connectors.canvas.client import CanvasClient, ForbiddenMethod
from app.connectors.canvas.connector import CanvasConnector
from app.core.clock import FixedClock
from tests.canvas_fake import API, BASE, fx, mock_canvas

NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)
TOKEN = "fake-canvas-token-123"


def ctx(last_success_at: datetime | None = None) -> ConnectorContext:
    return ConnectorContext(
        user_id=uuid4(),
        platform="canvas",
        secret=SecretStr(TOKEN),
        last_success_at=last_success_at,
        clock=FixedClock(NOW),
    )


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, s: float) -> None:
        self.calls.append(s)


def connector(**kw: Any) -> CanvasConnector:
    return CanvasConnector(base_url=BASE, sleep=kw.pop("sleep", Sleeps()), **kw)


async def collect(c: CanvasConnector, scope: SyncScope | None = None, **kw: Any) -> list[Any]:
    return [r async for r in c.fetch(ctx(**kw), scope or SyncScope())]


def by_type(records: list[Any], cls: type) -> list[Any]:
    return [r for r in records if isinstance(r, cls)]


# ---------------------------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "post", "HEAD"])
async def test_s11_t01_client_refuses_non_get(method: str) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.route().respond(200, json={})
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, SecretStr(TOKEN), http)
            with pytest.raises(ForbiddenMethod):
                await client.request(method, "/api/v1/courses/1/assignments/2/submissions")
        assert not route.called
    for name in ("post", "put", "patch", "delete"):
        assert not hasattr(CanvasClient, name)


async def test_s11_t02_paginate_follows_link_next_across_three_pages() -> None:
    def page(request: httpx.Request) -> httpx.Response:
        n = int(request.url.params.get("page", "1"))
        headers = {}
        if n < 3:
            headers["Link"] = (
                f'<{API}/courses?page={n + 1}&per_page=2>; rel="next", '
                f'<{API}/courses?page=1&per_page=2>; rel="first"'
            )
        return httpx.Response(200, json=[2 * n - 1, 2 * n], headers=headers)

    with respx.mock(assert_all_called=False) as router:
        route = router.get(f"{API}/courses").mock(side_effect=page)
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, SecretStr(TOKEN), http)
            got = [x async for x in client.paginate("/api/v1/courses", {"per_page": 2})]
    assert got == [1, 2, 3, 4, 5, 6]
    assert route.call_count == 3
    for call in route.calls:
        assert call.request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert TOKEN not in str(call.request.url)


async def test_s11_paginate_refuses_next_link_to_another_host() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses").respond(
            json=[1], headers={"Link": '<https://evil.example.com/steal?page=2>; rel="next"'}
        )
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, SecretStr(TOKEN), http)
            with pytest.raises(PlatformError):
                _ = [x async for x in client.paginate("/api/v1/courses")]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(500, json={"errors": []}),
        httpx.Response(429, text="slow down"),
        httpx.Response(403, text="403 Forbidden (Rate Limit Exceeded)"),
    ],
)
async def test_s11_5xx_and_rate_limit_responses_are_platform_errors(
    response: httpx.Response,
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/users/self").mock(return_value=response)
        with pytest.raises(PlatformError):
            await connector().validate(ctx())


async def test_s11_timeout_is_platform_error() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/users/self").mock(side_effect=httpx.ConnectTimeout("timeout"))
        with pytest.raises(PlatformError):
            await connector().validate(ctx())


async def test_s11_t11_low_rate_limit_remaining_throttles() -> None:
    sleeps = Sleeps()
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/users/self").mock(
            side_effect=[
                httpx.Response(200, json={}, headers={"X-Rate-Limit-Remaining": "700.0"}),
                httpx.Response(200, json={}, headers={"X-Rate-Limit-Remaining": "12.5"}),
                httpx.Response(200, json={}, headers={"X-Rate-Limit-Remaining": "600"}),
                httpx.Response(200, json={}),
            ]
        )
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, SecretStr(TOKEN), http, sleep=sleeps)
            await client.get("/api/v1/users/self")
            assert sleeps.calls == []
            await client.get("/api/v1/users/self")  # this response says 12.5 left
            assert sleeps.calls == []
            await client.get("/api/v1/users/self")  # -> waits before sending
            assert sleeps.calls == [1.0]
            await client.get("/api/v1/users/self")  # back above 50 -> no wait
            assert sleeps.calls == [1.0]


# ---------------------------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------------------------
async def test_s11_validate_returns_account_info() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        info = await connector().validate(ctx())
    assert info.account_label == "Test Student"
    assert info.platform_user_id == "1000001"


async def test_s11_t09_401_validate_and_fetch_raise_auth_expired() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/users/self").respond(401, json=fx("unauthorized"))
        router.get(f"{API}/courses").respond(401, json=fx("unauthorized"))
        with pytest.raises(AuthExpired):
            await connector().validate(ctx())
        with pytest.raises(AuthExpired):
            await collect(connector())


async def test_s11_full_fetch_maps_everything() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        records = await collect(connector())

    courses = by_type(records, NCourse)
    assert [(c.platform_id, c.code, c.term) for c in courses] == [
        ("12345", "COMPSCI 311", "Fall 2026"),
        ("23456", "MATH 235", "Fall 2026"),
    ]  # 34567 (access_restricted_by_date) and 45678 (no name) skipped
    assert courses[0].source_url == f"{BASE}/courses/12345"

    items = {i.platform_id: i for i in by_type(records, NItem)}
    assert {k: v.type for k, v in items.items()} == {
        "99812": "exam",
        "99813": "quiz",
        "99814": "lab",
        "99815": "project",
        "99816": "assignment",
        "event-70001": "exam",
        "80001": "assignment",
    }
    mid = items["99812"]  # the spec's example
    assert mid.course_platform_id == "12345" and mid.title == "Midterm 1"
    assert mid.due_at == datetime(2026, 11, 21, tzinfo=UTC) and mid.points == 100
    assert mid.source_url == f"{BASE}/courses/12345/assignments/99812"
    assert mid.source_updated_at == datetime(2026, 11, 10, 14, 2, tzinfo=UTC)
    assert items["99816"].due_at is None  # lock_at present but due_at null: don't guess
    assert items["99813"].description == "Covers interval scheduling."
    # Submission state (include[]=submission) lands on raw.submitted; never the whole object.
    assert items["80001"].raw["submitted"] is True
    assert items["99813"].raw["submitted"] is False
    assert items["99812"].raw["submitted"] is False
    assert items["event-70001"].raw.get("submitted") is None
    assert "submission" not in items["80001"].raw

    posts = by_type(records, NPost)
    assert [p.platform_id for p in posts] == ["88001", "88002"]
    p = posts[0]
    assert p.kind == "announcement" and p.author == "Prof Example"
    assert p.source_url == f"{BASE}/courses/12345/discussion_topics/88001"
    assert "(https://example.instructure.com/courses/12345/files/501)" in p.body
    assert p.posted_at == datetime(2026, 11, 12, 15, 30, tzinfo=UTC)

    mats = {m.platform_id: m for m in by_type(records, NMaterial)}
    assert set(mats) == {"syllabus-12345", "501", "502", "701", "702"}
    syl = mats["syllabus-12345"]
    assert syl.kind == "syllabus" and syl.download is None
    assert syl.text and "Midterm 1 20%" in syl.text and "<" not in syl.text
    assert syl.source_url == f"{BASE}/courses/12345/assignments/syllabus"
    pdf = mats["501"]
    assert pdf.kind == "file" and pdf.title == "Lecture 7 - Greedy.pdf"
    assert pdf.mime_type == "application/pdf"
    assert pdf.source_url == f"{BASE}/courses/12345/files/501"
    assert pdf.source_updated_at == datetime(2026, 11, 12, 9, 0, tzinfo=UTC)
    assert pdf.download is not None
    assert pdf.download.url == f"{BASE}/files/501/download?download_frd=1"
    assert pdf.download.size_bytes == 482113
    for m in mats.values():  # never a token or a verifier in a stored URL
        for url in (m.source_url, m.download.url if m.download else ""):
            assert TOKEN not in url and "verifier" not in url


async def test_s11_t05_calendar_events_only_exams_become_items() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        records = await collect(connector())
        call = next(
            c
            for c in router.calls
            if c.request.url.path == "/api/v1/calendar_events"
            and c.request.url.params["context_codes[]"] == "course_12345"
        )
    ev = [i for i in by_type(records, NItem) if i.platform_id.startswith("event-")]
    assert len(ev) == 1
    assert ev[0].title == "Midterm 2" and ev[0].type == "exam"
    assert ev[0].due_at == datetime(2026, 12, 3, 15, 0, tzinfo=UTC)
    assert "Office hours" not in [i.title for i in by_type(records, NItem)]
    q = call.request.url.params
    assert q["type"] == "event"
    assert q["start_date"].startswith("2026-09-02")  # term start
    assert q["end_date"].startswith((NOW + timedelta(days=120)).date().isoformat())


async def test_s11_t07_files_403_falls_back_to_modules() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router, files_23456_forbidden=True)
        records = await collect(connector())
    mats = [m for m in by_type(records, NMaterial) if m.course_platform_id == "23456"]
    assert sorted(m.platform_id for m in mats) == ["701", "702"]  # 701 listed twice -> once
    assert {m.title for m in mats} == {"Week 1 notes.docx", "Matrix cheat sheet.txt"}


async def test_s11_t07_files_and_modules_both_403_skip_files_only() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        router.get(f"{API}/courses/23456/modules").respond(403, json=fx("forbidden"))
        records = await collect(connector())
    assert not [m for m in by_type(records, NMaterial) if m.course_platform_id == "23456"]
    assert [i for i in by_type(records, NItem) if i.course_platform_id == "23456"]


async def test_s11_t08_unsupported_file_types_skipped() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        records = await collect(connector())
    ids = {m.platform_id for m in by_type(records, NMaterial)}
    assert "503" not in ids and "504" not in ids  # png, zip
    assert {"501", "502"} <= ids


async def test_s11_files_capped_per_course() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        records = await collect(connector(max_files_per_course=1))
    assert [m.platform_id for m in by_type(records, NMaterial) if m.kind == "file"][:1] == ["501"]
    assert "502" not in {m.platform_id for m in by_type(records, NMaterial)}


async def test_s11_t10_item_scope_fetches_exactly_one_assignment() -> None:
    with respx.mock(assert_all_called=False) as router:
        one = router.get(f"{API}/courses/12345/assignments/99812").respond(
            json=fx("assignments_12345")[0]
        )
        records = await collect(
            connector(), SyncScope(kind="item", course_platform_id="12345", platform_id="99812")
        )
        assert one.call_count == 1
        assert len(router.calls) == 1
    assert len(records) == 1 and isinstance(records[0], NItem)
    assert records[0].platform_id == "99812" and records[0].type == "exam"


async def test_s11_item_scope_calendar_event() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/calendar_events/70001").respond(json=fx("calendar_events_12345")[0])
        records = await collect(
            connector(),
            SyncScope(kind="item", course_platform_id="12345", platform_id="event-70001"),
        )
    assert [(r.platform_id, r.type) for r in records] == [("event-70001", "exam")]


async def test_s11_item_scope_missing_assignment_yields_nothing() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345/assignments/1").respond(404, json={"errors": []})
        records = await collect(
            connector(), SyncScope(kind="item", course_platform_id="12345", platform_id="1")
        )
    assert records == []


async def test_s11_material_scope_fetches_one_file() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345/files/501").respond(json=fx("files_12345")[0])
        records = await collect(
            connector(), SyncScope(kind="material", course_platform_id="12345", platform_id="501")
        )
        assert len(router.calls) == 1
    assert [(r.platform_id, r.kind) for r in records] == [("501", "file")]


async def test_s11_material_scope_syllabus() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345").respond(json=fx("course_12345"))
        records = await collect(
            connector(),
            SyncScope(kind="material", course_platform_id="12345", platform_id="syllabus-12345"),
        )
    assert [(r.platform_id, r.kind) for r in records] == [("syllabus-12345", "syllabus")]


async def test_s11_course_scope_yields_only_that_course() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        records = await collect(connector(), SyncScope(kind="course", course_platform_id="12345"))
        paths = {c.request.url.path for c in router.calls}
        assert "/api/v1/courses" not in paths  # the course list is not needed
    assert [c.platform_id for c in by_type(records, NCourse)] == ["12345"]
    assert {r.course_platform_id for r in records if not isinstance(r, NCourse)} == {"12345"}
    assert by_type(records, NItem) and by_type(records, NPost) and by_type(records, NMaterial)


async def test_s11_announcements_window_and_incremental() -> None:
    def start_dates(router: respx.MockRouter) -> set[str]:
        return {
            c.request.url.params["start_date"]
            for c in router.calls
            if c.request.url.path == "/api/v1/announcements"
        }

    last = NOW - timedelta(hours=3)
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        await collect(connector())
        assert {d[:10] for d in start_dates(router)} == {
            (NOW - timedelta(days=60)).date().isoformat()
        }
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        await collect(connector(), last_success_at=last)
        assert {d[:10] for d in start_dates(router)} == {
            (NOW - timedelta(days=60)).date().isoformat()
        }
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        await collect(connector(incremental_announcements=True), last_success_at=last)
        assert start_dates(router) == {(last - timedelta(days=1)).isoformat()}


async def test_submitted_assignments_request_includes_submission() -> None:
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        await collect(connector())
        urls = [str(c.request.url) for c in router.calls if "/assignments" in c.request.url.path]
    assert urls and all("include%5B%5D=submission" in u for u in urls), urls


async def test_submitted_item_scope_includes_submission() -> None:
    with respx.mock(assert_all_called=False) as router:
        one = router.get(f"{API}/courses/23456/assignments/80001").respond(
            json=fx("assignments_23456")[0]
        )
        records = await collect(
            connector(), SyncScope(kind="item", course_platform_id="23456", platform_id="80001")
        )
        assert "include%5B%5D=submission" in str(one.calls[0].request.url)
    assert isinstance(records[0], NItem) and records[0].raw["submitted"] is True
