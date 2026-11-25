"""S43 fake connector/local DB regressions for presence, distinct from content/index changes."""

import asyncio
from datetime import timedelta

import pytest

from app.connectors.base import SyncScope
from app.core.clock import FixedClock
from app.db.models import Platform
from app.db.repositories import agent
from app.db.repositories import sync as repo
from app.sync.merge import merge_user
from app.sync.pipeline import run_sync
from tests.integration.db import ONE_VEC, conn_fixture, create_auth_user, delete_auth_user
from tests.integration.test_s10_sync_db import NOW, FakeConnector, course, item, material, post

pytestmark = pytest.mark.integration
TABLES = ("course_links", "item_sources", "posts", "materials")


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def users(conn):
    ids = [await create_auth_user(conn), await create_auth_user(conn)]
    try:
        for uid in ids:
            await conn.execute(
                "insert into connections(user_id,platform) values (%s,'canvas')", (uid,)
            )
        yield ids
    finally:
        for uid in ids:
            await delete_auth_user(conn, uid)


def records():
    return [course(), item(), material(), post()]


async def sync(conn, uid, rows, platform: Platform = "canvas", **kwargs):
    rid = await repo.create_run(conn, uid, platform, {}, "manual", NOW)
    connector = FakeConnector(rows)
    connector.platform = platform
    return await run_sync(
        conn,
        user_id=uid,
        run_id=rid,
        scope=SyncScope(),
        connector=connector,
        secret="synthetic",
        clock=FixedClock(NOW + timedelta(hours=1)),
        **kwargs,
    )


async def snapshot(conn, uid):
    result = {}
    for table in TABLES:
        result[table] = await (
            await conn.execute(f"select * from {table} where user_id=%s", (uid,))
        ).fetchone()
    return result


async def test_s43_t01_identical_return_restores_sources_preserves_saved_chunks(conn, users):
    uid, _ = users
    queued = []

    async def queue(*args):
        queued.append(args)

    await sync(conn, uid, records(), process_material=queue, process_post=queue)
    await merge_user(conn, uid, clock=FixedClock(NOW))
    before = await snapshot(conn, uid)
    mid = before["materials"]["id"]
    await conn.execute(
        "update materials set processing_status='done',version=3 where id=%s", (mid,)
    )
    await conn.execute(
        "insert into chunks(user_id,course_id,material_id,text,token_count,embedding,"
        "material_version) values (%s,%s,%s,'memoization',1,%s,3)",
        (uid, before["materials"]["course_id"], mid, ONE_VEC),
    )
    await sync(conn, uid, [])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    assert all(v["status"] == "removed" for v in (await snapshot(conn, uid)).values())
    assert await agent.material_chunks(conn, uid, mid) == []
    queued.clear()
    result = await sync(conn, uid, records(), process_material=queue, process_post=queue)
    assert result.stats == {"new": 0, "changed": 0, "unchanged": 4, "removed": 0}
    after = await snapshot(conn, uid)
    assert all(v["status"] == "active" for v in after.values())
    assert all(
        after[t]["id"] == before[t]["id"] and after[t]["content_hash"] == before[t]["content_hash"]
        for t in TABLES
    )
    assert after["materials"]["version"] == 3 and after["materials"]["processing_status"] == "done"
    assert len(await agent.material_chunks(conn, uid, mid)) == 1
    assert not queued
    await merge_user(conn, uid, clock=FixedClock(NOW))
    row = await (await conn.execute("select status from items where user_id=%s", (uid,))).fetchone()
    assert row["status"] == "active"


async def test_s43_t02_changed_return_restores_course_and_keeps_real_diffs(conn, users):
    uid, _ = users
    await sync(conn, uid, records())
    await sync(conn, uid, [])
    changed = [
        course().model_copy(update={"name": "Revised course"}),
        item(),
        material(title="Revised file"),
        post().model_copy(update={"body": "Revised announcement"}),
    ]
    result = await sync(conn, uid, changed)
    assert result.stats["changed"] == 3
    state = await snapshot(conn, uid)
    assert state["course_links"]["status"] == "active"
    assert state["item_sources"]["status"] == "active"
    assert state["posts"]["status"] == "changed" and state["materials"]["status"] == "changed"
    events = await (
        await conn.execute(
            "select entity_type,field,new_value from changes where user_id=%s "
            "and new_value <> '\"removed\"'::jsonb",
            (uid,),
        )
    ).fetchall()
    assert sum(r["field"] == "status" and r["new_value"] == "active" for r in events) == 2
    assert {(r["entity_type"], r["field"]) for r in events if r["field"] != "status"} == {
        ("material", "title"),
        ("post", "body"),
    }


async def test_s43_t03_status_back_alerts_are_once_not_fake_content_changes(conn, users):
    uid, _ = users
    await sync(conn, uid, records())
    await merge_user(conn, uid, clock=FixedClock(NOW))
    await sync(conn, uid, [])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    for _ in range(2):
        await sync(conn, uid, records())
        await merge_user(conn, uid, clock=FixedClock(NOW))
    rows = await (
        await conn.execute(
            "select entity_type,field,new_value from changes where user_id=%s", (uid,)
        )
    ).fetchall()
    assert len(rows) == 6
    assert all(r["field"] == "status" for r in rows)
    assert {(r["entity_type"], r["new_value"]) for r in rows} == {
        (t, s) for t in ("item", "post", "material") for s in ("removed", "active")
    }


async def test_s43_t03_canonical_back_event_when_a_source_is_live_again(conn, users):
    uid, _ = users
    await sync(conn, uid, [course(), item()])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    await sync(conn, uid, [course()])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    # Independently isolate merge's missing alert from source restoration implementation.
    await conn.execute("update item_sources set status='active' where user_id=%s", (uid,))
    await merge_user(conn, uid, clock=FixedClock(NOW))
    rows = await (
        await conn.execute(
            "select new_value from changes where user_id=%s and field='status' order by id", (uid,)
        )
    ).fetchall()
    assert sorted(r["new_value"] for r in rows) == ["active", "removed"]


async def test_s43_t04_submitted_raw_update_and_owner_isolation(conn, users):
    uid, other = users
    for owner in users:
        await sync(conn, owner, records())
        await sync(conn, owner, [])
    returned = [course(), item(raw={"submitted": True}), material(), post()]
    await sync(conn, uid, returned)
    mine = await snapshot(conn, uid)
    assert (
        mine["item_sources"]["status"] == "active"
        and mine["item_sources"]["raw"]["submitted"] is True
    )
    assert all(v["status"] == "removed" for v in (await snapshot(conn, other)).values())


async def test_s43_t03_returning_one_source_does_not_announce_live_item_back(conn, users):
    uid, _ = users
    await conn.execute("insert into connections(user_id,platform) values (%s,'gradescope')", (uid,))
    await sync(conn, uid, [course(), item()])
    await sync(conn, uid, [course(), item()], platform="gradescope")
    await merge_user(conn, uid, clock=FixedClock(NOW))
    await sync(conn, uid, [course()])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    await sync(conn, uid, [course(), item()])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    rows = await (
        await conn.execute("select status from items where user_id=%s", (uid,))
    ).fetchall()
    assert len(rows) == 1 and rows[0]["status"] == "active"
    alerts = await (
        await conn.execute("select id from changes where user_id=%s and field='status'", (uid,))
    ).fetchall()
    assert alerts == []


async def test_s43_t06_unseen_incomplete_sources_do_not_magically_return(conn, users):
    uid, _ = users
    await sync(conn, uid, records())
    await sync(conn, uid, [])

    class Incomplete(FakeConnector):
        async def fetch(self, ctx, scope):
            ctx.incomplete.update({("12345", t) for t in ("materials", "posts", "item_sources")})
            async for record in super().fetch(ctx, scope):
                yield record

    rid = await repo.create_run(conn, uid, "canvas", {}, "manual", NOW)
    await run_sync(
        conn,
        user_id=uid,
        run_id=rid,
        scope=SyncScope(),
        connector=Incomplete([course()]),
        secret="synthetic",
        clock=FixedClock(NOW),
    )
    state = await snapshot(conn, uid)
    assert state["course_links"]["status"] == "active"
    assert all(state[t]["status"] == "removed" for t in ("materials", "posts", "item_sources"))


async def test_s43_t03_concurrent_return_writes_one_back_event(conn, users):
    from tests.integration.db import open_conn

    uid, _ = users
    await sync(conn, uid, records())
    await sync(conn, uid, [])
    async with await open_conn() as other_conn:
        await asyncio.gather(sync(conn, uid, records()), sync(other_conn, uid, records()))
    rows = await (
        await conn.execute(
            "select entity_type,count(*) as n from changes where user_id=%s "
            "and field='status' and new_value='\"active\"'::jsonb group by entity_type",
            (uid,),
        )
    ).fetchall()
    assert {r["entity_type"]: r["n"] for r in rows} == {"post": 1, "material": 1}


async def test_s43_t03_canonical_return_with_real_changes_is_idempotent(conn, users):
    uid, _ = users
    await sync(conn, uid, [course(), item()])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    await sync(conn, uid, [course()])
    await merge_user(conn, uid, clock=FixedClock(NOW))
    await sync(conn, uid, [course(), item(title="Revised exam", due_at=NOW + timedelta(days=6))])
    for _ in range(2):
        await merge_user(conn, uid, clock=FixedClock(NOW))
    rows = await (
        await conn.execute(
            "select field,new_value from changes where user_id=%s and entity_type='item'",
            (uid,),
        )
    ).fetchall()
    assert len(rows) == 4
    assert sorted(r["field"] for r in rows) == ["due_at", "status", "status", "title"]
    assert {r["new_value"] for r in rows if r["field"] == "status"} == {"removed", "active"}
