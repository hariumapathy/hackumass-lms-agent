"""Submitted work is done work: never Overdue, flagged everywhere else (split-2026-11-15 B1).

The connectors store `raw.submitted` on `item_sources` (no schema change); an item is submitted
when any live source says so.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.connectors.base import NItem
from app.core.clock import FixedClock
from app.core.settings import get_settings
from app.db.pool import close_pool
from app.db.repositories import agent as agent_repo
from app.main import create_app
from app.sync.pipeline import _Store
from tests.helpers import auth_header
from tests.integration.db import (
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)


@pytest.fixture
async def student():  # noqa: ANN201
    async for conn in conn_fixture():
        uid = await create_auth_user(conn)
        ids = await insert_minimal_rows(conn, uid)
        try:
            yield conn, uid, ids
        finally:
            await close_pool()
            await delete_auth_user(conn, uid)


@pytest.fixture
async def client(monkeypatch):  # noqa: ANN001, ANN201
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(clock=FixedClock(NOW))),
        base_url="http://test",
    ) as client:
        yield client


async def _item(conn, uid, course_id, title: str, due: datetime, raw: dict) -> None:  # noqa: ANN001
    cur = await conn.execute(
        "insert into items (user_id, course_id, title, due_at) values (%s,%s,%s,%s) returning id",
        (uid, course_id, title, due),
    )
    iid = (await cur.fetchone())["id"]
    from psycopg.types.json import Jsonb

    await conn.execute(
        "insert into item_sources (user_id, item_id, course_id, raw_title, raw, platform, "
        "platform_id, source_url, content_hash) values (%s,%s,%s,%s,%s,'canvas',%s,'https://x','h')",
        (uid, iid, course_id, title, Jsonb(raw), f"s-{title}"),
    )


async def test_submitted_not_overdue_and_flagged(student, client):  # noqa: ANN001, ANN201
    conn, uid, ids = student
    await conn.execute("update items set status = 'removed' where user_id = %s", (uid,))
    past = NOW - timedelta(days=1)
    await _item(conn, uid, ids["courses"], "done hw", past, {"submitted": True})
    await _item(conn, uid, ids["courses"], "missing hw", past, {"submitted": False})
    await _item(conn, uid, ids["courses"], "old hw", past, {})  # synced before this change
    await _item(
        conn, uid, ids["courses"], "done early", NOW + timedelta(hours=2), {"submitted": True}
    )
    h = auth_header(uid)

    today = (await client.get("/today", headers=h)).json()
    assert sorted(i["title"] for i in today["overdue"]) == ["missing hw", "old hw"]
    assert [(i["title"], i["submitted"]) for i in today["due_today"]] == [("done early", True)]

    items = {i["title"]: i for i in (await client.get("/items", headers=h)).json()}
    assert items["done hw"]["submitted"] is True
    assert items["missing hw"]["submitted"] is False and items["old hw"]["submitted"] is False

    rows = {r["title"]: r for r in await agent_repo.list_items(conn, uid, None, None)}
    assert rows["done hw"]["submitted"] is True and rows["missing hw"]["submitted"] is False


async def test_submitted_any_source_counts_and_removed_source_ignored(student, client):  # noqa: ANN001, ANN201
    conn, uid, ids = student
    await conn.execute("update items set status = 'removed' where user_id = %s", (uid,))
    await _item(conn, uid, ids["courses"], "hw", NOW - timedelta(days=1), {"submitted": False})
    cur = await conn.execute("select id from items where user_id = %s and title = 'hw'", (uid,))
    iid = (await cur.fetchone())["id"]
    from psycopg.types.json import Jsonb

    await conn.execute(
        "insert into item_sources (user_id, item_id, course_id, raw_title, raw, platform, "
        "platform_id, source_url, content_hash, status) values "
        "(%s,%s,%s,'hw',%s,'gradescope','g1','https://g','h','removed')",
        (uid, iid, ids["courses"], Jsonb({"submitted": True})),
    )
    h = auth_header(uid)
    assert [i["title"] for i in (await client.get("/today", headers=h)).json()["overdue"]] == ["hw"]
    await conn.execute(
        "update item_sources set status = 'active' where user_id = %s and platform_id = 'g1'",
        (uid,),
    )
    assert (await client.get("/today", headers=h)).json()["overdue"] == []


async def test_submitted_resync_updates_flag_without_content_change(student):  # noqa: ANN001, ANN201
    """Submitting doesn't change title/due/points (the hash), but the stored flag must follow."""
    conn, uid, _ = student
    store = _Store(conn, uid, "canvas", NOW)

    def rec(submitted: bool) -> NItem:
        return NItem(
            platform_id="a-77",
            course_platform_id="c-77",
            type="assignment",
            title="HW 7",
            due_at=NOW - timedelta(days=1),
            source_url="https://example.instructure.com/courses/77/assignments/77",
            raw={"id": 77, "submitted": submitted},
        )

    first, sid = await store.item(rec(False))
    again, sid2 = await store.item(rec(True))
    assert first == "new" and again == "unchanged" and sid == sid2
    cur = await conn.execute("select raw from item_sources where id = %s", (sid,))
    assert (await cur.fetchone())["raw"]["submitted"] is True
