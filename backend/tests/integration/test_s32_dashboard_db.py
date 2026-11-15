"""Dashboard HTTP regressions: the signed-in student's stored data, never the mock semester."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.clock import FixedClock
from app.core.settings import get_settings
from app.db.pool import close_pool
from app.main import create_app
from tests.helpers import auth_header
from tests.integration.db import (
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)  # DST ends in New York today


@pytest.fixture
async def dashboard():  # noqa: ANN201
    async for conn in conn_fixture():
        users = [await create_auth_user(conn) for _ in range(2)]
        rows = [await insert_minimal_rows(conn, uid) for uid in users]
        try:
            yield conn, users, rows
        finally:
            await close_pool()
            for uid in users:
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


async def test_S32_T01_T02_today_windows_dst_and_sources(dashboard, client):  # noqa: ANN001, ANN201
    conn, users, rows = dashboard
    uid, ids = users[0], rows[0]
    await conn.execute("update items set status = 'removed' where user_id = %s", (uid,))
    dates = {
        "old": NOW - timedelta(days=8),
        "overdue": NOW - timedelta(hours=1),
        "today": datetime(2026, 11, 2, 4, 59, tzinfo=UTC),  # 23:59 EST (25-hour day)
        "week": datetime(2026, 11, 2, 5, tzinfo=UTC),
        "exam": NOW + timedelta(days=29),
        "far exam": NOW + timedelta(days=31),
    }
    for title, due in dates.items():
        await conn.execute(
            "insert into items (user_id, course_id, title, due_at, type) values (%s,%s,%s,%s,%s)",
            (uid, ids["courses"], title, due, "exam" if "exam" in title else "assignment"),
        )
    res = await client.get("/today", headers=auth_header(uid))
    assert res.status_code == 200, res.text
    body = res.json()
    for section, title in [
        ("overdue", "overdue"),
        ("due_today", "today"),
        ("due_this_week", "week"),
        ("upcoming_exams", "exam"),
    ]:
        assert [i["title"] for i in body[section]] == [title]
    assert body["date"] == "2026-11-01"
    assert body["timezone"] == "America/New_York"
    assert [s["platform"] for s in body["sources"]] == ["canvas"]
    # Near midnight in another profile timezone, the same deadline changes sections.
    await conn.execute("update profiles set timezone = 'Asia/Tokyo' where user_id = %s", (uid,))
    tokyo = (await client.get("/today", headers=auth_header(uid))).json()
    assert tokyo["due_today"] == []
    assert {i["title"] for i in tokyo["due_this_week"]} == {"today", "week"}


async def test_S32_T02_T03_db_routes_scoped_and_seen_persists(dashboard, client):  # noqa: ANN001, ANN201
    conn, users, rows = dashboard
    uid, ids = users[0], rows[0]
    await conn.execute(
        "update items set due_at = %s, status = 'changed' where user_id = %s",
        (NOW + timedelta(hours=1), uid),
    )
    await conn.execute(
        "update changes set entity_type = 'item', entity_id = %s, field = 'due_at', "
        "detected_at = %s where user_id = %s",
        (ids["items"], NOW, uid),
    )
    await conn.execute("update posts set posted_at = %s where user_id = %s", (NOW, uid))
    h = auth_header(uid)
    courses = (await client.get("/courses", headers=h)).json()
    assert len(courses) == 1 and courses[0]["id"] == str(ids["courses"])
    assert courses[0]["upcoming_count"] == 1 and courses[0]["platforms"] == ["canvas"]
    detail = (await client.get(f"/courses/{ids['courses']}", headers=h)).json()
    assert detail["items"][0]["sources"][0]["source_url"] == "https://example.instructure.com/x"
    assert detail["items"][0]["changed_fields"] == ["due_at"]
    assert len(detail["materials"]) == len(detail["recent_posts"]) == 1
    assert (await client.get(f"/courses/{rows[1]['courses']}", headers=h)).status_code == 404
    assert (
        await client.get("/items", params={"course_id": str(rows[1]["courses"])}, headers=h)
    ).json() == []
    assert (await client.get("/items", params={"type": "exam"}, headers=h)).json() == []
    assert (
        await client.get(
            "/items", params={"from": (NOW + timedelta(days=1)).isoformat()}, headers=h
        )
    ).json() == []
    today = (await client.get("/today", headers=h)).json()
    assert len(today["changes"]) == len(today["new_posts"]) == 1
    seen = await client.post(
        "/changes/seen", json={"ids": [str(r["changes"]) for r in rows]}, headers=h
    )
    assert seen.status_code == 204
    assert (await client.get("/changes?unseen=true", headers=h)).json() == []
    assert (await client.get("/today", headers=h)).json()["due_today"][0]["changed_fields"] == []
    assert (await client.get("/items", headers=h)).json()[0]["status"] == "active"
    other = (await client.get("/changes?unseen=true", headers=auth_header(users[1]))).json()
    assert len(other) == 1


async def test_S23_T09_citations_resolve_only_callers_chunks(dashboard, client):  # noqa: ANN001, ANN201
    _, users, rows = dashboard
    ids = f"{rows[0]['chunks']},{rows[1]['chunks']},999999999"
    res = await client.get("/citations", params={"ids": ids}, headers=auth_header(users[0]))
    assert res.status_code == 200, res.text
    assert [c["chunk_id"] for c in res.json()] == [rows[0]["chunks"]]
    assert res.json()[0]["quote"] == "memoization"


async def test_S32_T11_import_stays_running_until_merge_finishes(dashboard, client):  # noqa: ANN001, ANN201
    conn, users, _ = dashboard
    from psycopg.types.json import Jsonb

    uid = users[0]
    await conn.execute("update sync_runs set status = 'succeeded' where user_id = %s", (uid,))
    cur = await conn.execute(
        "insert into procrastinate_jobs (task_name, queue_name, args) "
        "values ('merge_user', 'sync', %s) returning id",
        (Jsonb({"user_id": str(uid)}),),
    )
    job_id = (await cur.fetchone())["id"]
    try:
        h = auth_header(uid)
        assert (await client.get("/sync/status", headers=h)).json()["sources"][0]["running"]
        await conn.execute(
            "update procrastinate_jobs set status = 'succeeded' where id = %s", (job_id,)
        )
        assert not (await client.get("/sync/status", headers=h)).json()["sources"][0]["running"]
    finally:
        await conn.execute("delete from procrastinate_jobs where id = %s", (job_id,))


async def test_S32_empty_student_has_no_demo_data(dashboard, client):  # noqa: ANN001, ANN201
    conn, _, _ = dashboard
    uid = await create_auth_user(conn)
    try:
        h = auth_header(uid)
        assert (await client.get("/courses", headers=h)).json() == []
        today = (await client.get("/today", headers=h)).json()
        assert all(
            today[k] == []
            for k in [
                "overdue",
                "due_today",
                "due_this_week",
                "upcoming_exams",
                "changes",
                "new_posts",
                "sources",
            ]
        )
    finally:
        await delete_auth_user(conn, uid)


async def test_S13_T06_disconnect_forgets_secret_and_cancels_queued_jobs(dashboard, client):  # noqa: ANN001, ANN201
    conn, users, rows = dashboard
    from psycopg.types.json import Jsonb

    for uid, ids in zip(users, rows, strict=True):
        await conn.execute(
            "insert into procrastinate_jobs (task_name, queue_name, args) "
            "values ('sync_platform', 'sync', %s)",
            (
                Jsonb(
                    {
                        "job": {
                            "user_id": str(uid),
                            "platform": "canvas",
                            "sync_run_id": str(ids["sync_runs"]),
                        }
                    }
                ),
            ),
        )
    try:
        h = auth_header(users[0])
        assert (await client.delete("/connections/canvas", headers=h)).status_code == 204
        assert (await client.get("/me", headers=h)).json()["connections"] == []
        assert (await client.get("/sync/status", headers=h)).json()["sources"] == []
        cur = await conn.execute(
            "select count(*) as n from connection_secrets where connection_id = %s",
            (rows[0]["connections"],),
        )
        assert (await cur.fetchone())["n"] == 0
        cur = await conn.execute(
            "select status from sync_runs where id = %s", (rows[0]["sync_runs"],)
        )
        assert (await cur.fetchone())["status"] == "failed"
        cur = await conn.execute(
            "select status from procrastinate_jobs where args->'job'->>'user_id' = %s",
            (str(users[0]),),
        )
        assert (await cur.fetchone())["status"] == "cancelled"
        assert (
            len((await client.get("/me", headers=auth_header(users[1]))).json()["connections"]) == 1
        )
        cur = await conn.execute(
            "select status from procrastinate_jobs where args->'job'->>'user_id' = %s",
            (str(users[1]),),
        )
        assert (await cur.fetchone())["status"] == "todo"
        # Idempotent, and old data stays available after disconnect.
        assert (await client.delete("/connections/canvas", headers=h)).status_code == 204
        assert len((await client.get("/courses", headers=h)).json()) == 1
    finally:
        for uid in users:
            await conn.execute(
                "delete from procrastinate_jobs where args->'job'->>'user_id' = %s", (str(uid),)
            )
