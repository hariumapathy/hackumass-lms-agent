# pyright: reportArgumentType=false, reportIndexIssue=false, reportCallIssue=false, reportOptionalSubscript=false
"""S16 merge + change detection: integration tests against the local DB.

Records go through the real S10 pipeline (fake connectors for Canvas and Gradescope), then
`merge_user` runs, the same order the worker uses.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.connectors.base import (
    AccountInfo,
    ConnectorContext,
    NCourse,
    NItem,
    NormalizedRecord,
    SyncScope,
)
from app.core.clock import FixedClock
from app.core.embeddings import FakeEmbeddings
from app.db.repositories import sync as repo
from app.db.seed import seed_user
from app.sync.merge import merge_user
from app.sync.pipeline import run_sync
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)
DUE = NOW + timedelta(days=4)
CV = "https://example.instructure.com/courses/12345"
GS = "https://example.gradescope.com/courses/777"


class FakeConnector:
    def __init__(self, platform: str, records: list[Any]) -> None:
        self.platform, self.records = platform, records

    async def validate(self, ctx: ConnectorContext) -> AccountInfo:
        return AccountInfo(account_label="Test")

    async def fetch(
        self, ctx: ConnectorContext, scope: SyncScope
    ) -> AsyncIterator[NormalizedRecord]:
        for r in self.records:
            yield r


def cv_course(**kw: Any) -> NCourse:
    base: dict[str, Any] = dict(
        platform_id="12345",
        name="Intro to Algorithms",
        code="COMPSCI 311 SEC 01",
        term="Fall 2026",
        source_url=CV,
    )
    return NCourse(**{**base, **kw})


def gs_course(**kw: Any) -> NCourse:
    base: dict[str, Any] = dict(
        platform_id="777", name="CS311 Algos", code="CS 311", term="Fall 2026", source_url=GS
    )
    return NCourse(**{**base, **kw})


def cv_item(**kw: Any) -> NItem:
    base: dict[str, Any] = dict(
        platform_id="a4",
        course_platform_id="12345",
        type="assignment",
        title="HW4",
        due_at=DUE,
        points=60,
        source_url=f"{CV}/assignments/4",
    )
    return NItem(**{**base, **kw})


def gs_item(**kw: Any) -> NItem:
    base: dict[str, Any] = dict(
        platform_id="g4",
        course_platform_id="777",
        type="assignment",
        title="Homework 4 (PDF)",
        due_at=DUE + timedelta(hours=1),
        points=50,
        source_url=f"{GS}/assignments/4",
    )
    return NItem(**{**base, **kw})


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    for p in ("canvas", "gradescope"):
        await conn.execute("insert into connections (user_id, platform) values (%s, %s)", (uid, p))
    yield uid
    await delete_auth_user(conn, uid)


async def _sync(conn: Any, uid: UUID, platform: str, records: list[Any]) -> Any:
    scope = SyncScope()
    run_id = await repo.create_run(
        conn, uid, platform, scope.model_dump(mode="json"), "manual", NOW
    )
    return await run_sync(
        conn,
        user_id=uid,
        run_id=run_id,
        scope=scope,
        connector=FakeConnector(platform, records),
        secret="tok",
        clock=FixedClock(NOW),
    )


async def _rows(conn: Any, sql: str, *params: Any) -> list[dict[str, Any]]:
    cur = await conn.execute(sql, params)
    return await cur.fetchall()


async def _count(conn: Any, sql: str, *params: Any) -> int:
    rows = await _rows(conn, f"select count(*) as n from {sql}", *params)  # noqa: S608
    return rows[0]["n"]


async def _both_synced(conn: Any, uid: UUID) -> None:
    await _sync(conn, uid, "canvas", [cv_course(), cv_item()])
    await _sync(conn, uid, "gradescope", [gs_course(), gs_item()])
    await merge_user(conn, uid, clock=FixedClock(NOW))


async def test_s16_t02_canvas_and_gradescope_course_become_one(conn, user) -> None:  # noqa: ANN001
    await _sync(conn, user, "canvas", [cv_course(), cv_item()])
    await _sync(conn, user, "gradescope", [gs_course(), gs_item()])
    assert await _count(conn, "courses where user_id = %s", user) == 2
    stats = await merge_user(conn, user, clock=FixedClock(NOW))
    assert stats.courses_merged == 1
    courses = await _rows(conn, "select id, name from courses where user_id = %s", user)
    assert len(courses) == 1 and courses[0]["name"] == "Intro to Algorithms"  # Canvas name
    cid = courses[0]["id"]
    assert await _count(conn, "course_links where user_id = %s and course_id = %s", user, cid) == 2
    # S16-T03 end to end: one canonical item with both sources, Canvas fields win.
    items = await _rows(
        conn, "select id, title, due_at, points from items where user_id = %s", user
    )
    assert len(items) == 1
    assert (items[0]["title"], items[0]["due_at"], float(items[0]["points"])) == ("HW4", DUE, 60)
    assert (
        await _count(conn, "item_sources where user_id = %s and item_id = %s", user, items[0]["id"])
        == 2
    )
    assert await _count(conn, "changes where user_id = %s", user) == 0


async def test_s16_t02_different_terms_stay_separate(conn, user) -> None:  # noqa: ANN001
    await _sync(conn, user, "canvas", [cv_course(), cv_item()])
    await _sync(conn, user, "gradescope", [gs_course(term="Spring 2026"), gs_item()])
    await merge_user(conn, user, clock=FixedClock(NOW))
    assert await _count(conn, "courses where user_id = %s", user) == 2
    assert await _count(conn, "items where user_id = %s", user) == 2


async def test_s16_t02_late_course_match_folds_existing_items(conn, user) -> None:  # noqa: ANN001
    """Both sides already have canonical items when the courses finally match (term arrives
    later): the Gradescope item folds into the Canvas one, references follow it."""
    await _sync(conn, user, "canvas", [cv_course(), cv_item()])
    await _sync(conn, user, "gradescope", [gs_course(term=None), gs_item()])
    await merge_user(conn, user, clock=FixedClock(NOW))
    assert await _count(conn, "items where user_id = %s", user) == 2
    gs_item_id = (
        await _rows(
            conn,
            "select item_id from item_sources where user_id = %s and platform = 'gradescope'",
            user,
        )
    )[0]["item_id"]
    await conn.execute(
        "insert into study_blocks (user_id, item_id, title, start_at, end_at) "
        "values (%s, %s, 'Study', now(), now() + interval '1 hour')",
        (user, gs_item_id),
    )
    await _sync(conn, user, "gradescope", [gs_course(), gs_item()])
    stats = await merge_user(conn, user, clock=FixedClock(NOW))
    assert stats.courses_merged == 1 and stats.items_folded == 1
    items = await _rows(conn, "select id, title from items where user_id = %s", user)
    assert len(items) == 1 and items[0]["title"] == "HW4"
    blocks = await _rows(conn, "select item_id from study_blocks where user_id = %s", user)
    assert blocks[0]["item_id"] == items[0]["id"]
    assert await _count(conn, "changes where user_id = %s", user) == 0


async def test_s16_t07_canonical_due_change_writes_one_change(conn, user) -> None:  # noqa: ANN001
    await _both_synced(conn, user)
    moved = DUE + timedelta(days=2)
    await _sync(conn, user, "canvas", [cv_course(), cv_item(due_at=moved)])
    # The pipeline itself no longer writes item field changes (S16 writes canonical ones).
    assert await _count(conn, "changes where user_id = %s", user) == 0
    stats = await merge_user(conn, user, clock=FixedClock(NOW))
    assert stats.changes_written == 1
    rows = await _rows(
        conn,
        "select entity_type, entity_id, field, old_value, new_value from changes "
        "where user_id = %s",
        user,
    )
    it = (await _rows(conn, "select id, due_at, status from items where user_id = %s", user))[0]
    assert len(rows) == 1
    assert rows[0]["entity_type"] == "item" and rows[0]["entity_id"] == it["id"]
    assert rows[0]["field"] == "due_at"
    assert rows[0]["old_value"] == DUE.isoformat() and rows[0]["new_value"] == moved.isoformat()
    assert it["due_at"] == moved and it["status"] == "changed"


async def test_s16_t07_non_canonical_source_change_writes_nothing(conn, user) -> None:  # noqa: ANN001
    """Gradescope's due moves but Canvas's due is the canonical one: no canonical change."""
    await _both_synced(conn, user)
    await _sync(conn, user, "gradescope", [gs_course(), gs_item(due_at=DUE + timedelta(hours=5))])
    await merge_user(conn, user, clock=FixedClock(NOW))
    assert await _count(conn, "changes where user_id = %s", user) == 0
    it = (await _rows(conn, "select due_at, status from items where user_id = %s", user))[0]
    assert it["due_at"] == DUE and it["status"] == "active"


async def test_s16_t07_title_and_points_changes(conn, user) -> None:  # noqa: ANN001
    await _both_synced(conn, user)
    await _sync(conn, user, "canvas", [cv_course(), cv_item(title="HW4 (revised)", points=70)])
    await merge_user(conn, user, clock=FixedClock(NOW))
    rows = await _rows(conn, "select field, new_value from changes where user_id = %s", user)
    assert {(r["field"], r["new_value"]) for r in rows} == {
        ("title", "HW4 (revised)"),
        ("points", 70),
    }


async def test_s16_t08_all_sources_removed_item_removed(conn, user) -> None:  # noqa: ANN001
    await _both_synced(conn, user)
    await _sync(conn, user, "canvas", [cv_course()])  # full scope: Canvas source removed
    await merge_user(conn, user, clock=FixedClock(NOW))
    # Gradescope still has it: not removed; the canonical fields now follow Gradescope.
    it = (await _rows(conn, "select title, status from items where user_id = %s", user))[0]
    assert it["status"] == "changed" and it["title"] == "Homework 4 (PDF)"
    await _sync(conn, user, "gradescope", [gs_course()])
    stats = await merge_user(conn, user, clock=FixedClock(NOW))
    assert stats.items_removed == 1
    it = (await _rows(conn, "select id, status from items where user_id = %s", user))[0]
    assert it["status"] == "removed"
    rows = await _rows(
        conn, "select entity_id, field, new_value from changes where user_id = %s", user
    )
    assert [
        (r["entity_id"], r["field"], r["new_value"]) for r in rows if r["field"] == "status"
    ] == [(it["id"], "status", "removed")]


async def _snapshot(conn: Any, uid: UUID) -> dict[str, Any]:
    q = {
        "courses": "select id, name, code, term from courses where user_id = %s order by id",
        "course_links": "select id, course_id from course_links where user_id = %s order by id",
        "items": "select id, course_id, type, title, due_at, points, status, updated_at "
        "from items where user_id = %s order by id",
        "item_sources": "select id, item_id, course_id from item_sources where user_id = %s "
        "order by id",
        "changes": "select id from changes where user_id = %s order by id",
    }
    return {k: await _rows(conn, sql, uid) for k, sql in q.items()}


async def test_s16_t09_merge_is_idempotent(conn, user) -> None:  # noqa: ANN001
    await _both_synced(conn, user)
    await _sync(conn, user, "canvas", [cv_course(), cv_item(due_at=DUE + timedelta(days=1))])
    await merge_user(conn, user, clock=FixedClock(NOW))
    before = await _snapshot(conn, user)
    stats = await merge_user(conn, user, clock=FixedClock(NOW + timedelta(minutes=5)))
    assert stats.model_dump() == {k: 0 for k in stats.model_dump()}
    assert await _snapshot(conn, user) == before


async def test_s16_seed_items_stay_one_item_each(conn, user) -> None:  # noqa: ANN001
    """Acceptance 1: seeded Canvas + Gradescope items remain one item; merge is a no-op."""
    await conn.execute("delete from connections where user_id = %s", (user,))
    await seed_user(conn, user, FakeEmbeddings(), namespace=f"test-{uuid4().hex[:8]}")
    before = await _snapshot(conn, user)
    multi = await _count(
        conn,
        "(select item_id from item_sources where user_id = %s group by item_id "
        "having count(*) > 1) x",
        user,
    )
    assert multi > 0
    stats = await merge_user(conn, user)
    assert stats.model_dump() == {k: 0 for k in stats.model_dump()}
    assert await _snapshot(conn, user) == before
