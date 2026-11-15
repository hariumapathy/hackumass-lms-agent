# pyright: reportArgumentType=false, reportIndexIssue=false, reportCallIssue=false, reportOptionalSubscript=false
"""S17 Piazza: a real `run_sync` with the Piazza connector into the local DB (fake transport)."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.connectors.base import SyncScope
from app.core.clock import FixedClock
from app.db.repositories import sync as repo
from app.sync.pipeline import run_sync
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user
from tests.piazza_fake import CS311, STATE, make_connector

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    yield uid
    await delete_auth_user(conn, uid)


async def test_s17_run_sync_with_piazza_connector_into_db(conn, user):  # noqa: ANN001, ANN201
    await conn.execute("insert into connections (user_id, platform) values (%s, 'piazza')", (user,))
    connector, fake = make_connector()

    async def sync() -> Any:
        run_id = await repo.create_run(conn, user, "piazza", {"kind": "full"}, "connect", NOW)
        return await run_sync(
            conn,
            user_id=user,
            run_id=run_id,
            scope=SyncScope(),
            connector=connector,
            secret=json.dumps(STATE),
            clock=FixedClock(NOW),
        )

    out = await sync()
    assert out.status == "succeeded", out.error
    assert out.stats == {"new": 5, "changed": 0, "unchanged": 0, "removed": 0}  # 2 courses, 3 posts
    cur = await conn.execute(
        "select code, term from courses where user_id = %s order by code", (user,)
    )
    assert [(r["code"], r["term"]) for r in await cur.fetchall()] == [
        ("COMPSCI 311", "Fall 2026"),
        ("CS 220", "Fall 2026"),
    ]
    cur = await conn.execute(
        "select platform_id, kind, author, body, source_url from posts "
        "where user_id = %s order by platform_id",
        (user,),
    )
    rows = await cur.fetchall()
    assert [(r["platform_id"], r["kind"], r["author"]) for r in rows] == [
        (f"{CS311}:1", "piazza", "Student"),
        (f"{CS311}:2", "piazza", "Anonymous"),
        (f"{CS311}:3", "piazza", "Instructor"),
    ]
    assert rows[1]["body"].startswith("Q: Is BFS/DFS") and "A (instructor):" in rows[1]["body"]
    assert rows[0]["source_url"] == f"https://piazza.com/class/{CS311}/post/1"

    # Second sync: nothing changed since the last success → no get_post, nothing removed.
    fake.calls.clear()
    again = await sync()
    assert again.status == "succeeded", again.error
    assert "content.get" not in fake.methods()
    assert again.stats["removed"] == 0 and again.stats["new"] == 0
    cur = await conn.execute(
        "select count(*) as n from posts where user_id = %s and status <> 'removed'", (user,)
    )
    assert (await cur.fetchone())["n"] == 3
