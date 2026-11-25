"""S42 real local DB, mocked Canvas: completeness controls absence inference end to end."""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.connectors.base import SyncScope
from app.connectors.canvas.connector import CanvasConnector
from app.core.clock import FixedClock
from app.db.repositories import sync as repo
from app.sync.pipeline import run_sync
from tests.canvas_fake import API, BASE, fx, mock_canvas
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 24, tzinfo=UTC)


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):
    uid = await create_auth_user(conn)
    try:
        await conn.execute("insert into connections(user_id,platform) values (%s,'canvas')", (uid,))
        yield uid
    finally:
        await delete_auth_user(conn, uid)


async def sync(conn, uid, mode="initial"):
    run = await repo.create_run(conn, uid, "canvas", {"kind": "full"}, "manual", NOW)
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        if mode in ("cap", "module", "complete"):
            # Another fully enumerated course still reconciles its genuine missing files.
            router.get(f"{API}/courses/23456/files").respond(json=[])
        if mode == "module":
            router.get(f"{API}/courses/12345/files").respond(403, json={})
            router.get(f"{API}/courses/12345/modules").respond(json=[])
        if mode == "complete":
            router.get(f"{API}/courses/12345/files").respond(json=fx("files_12345")[:1])
        if mode == "malformed":
            router.get(f"{API}/courses/12345/files").respond(
                json={"error": "synthetic invalid list"}
            )
        if mode in ("partial_failure", "partial_forbidden"):

            def pages(request):
                if request.url.params.get("page") == "2":
                    return httpx.Response(503 if mode == "partial_failure" else 403, json={})
                return httpx.Response(
                    200,
                    json=fx("files_12345")[:1],
                    headers={"Link": f'<{API}/courses/12345/files?page=2>; rel="next"'},
                )

            router.get(f"{API}/courses/12345/files").mock(side_effect=pages)
            router.get(f"{API}/courses/12345/modules").respond(json=[])
        return await run_sync(
            conn,
            user_id=uid,
            run_id=run,
            scope=SyncScope(),
            connector=CanvasConnector(
                base_url=BASE, max_files_per_course=1 if mode == "cap" else 500
            ),
            secret="synthetic-test-only",
            clock=FixedClock(NOW),
        )


@pytest.mark.parametrize("mode", ["cap", "module", "partial_forbidden"])
async def test_s42_t04_partial_listing_preserves_old_files(conn, user, mode):
    assert (await sync(conn, user)).status == "succeeded"
    result = await sync(conn, user, mode)
    assert result.status == "succeeded"
    rows = await (
        await conn.execute("select platform_id,status from materials where user_id=%s", (user,))
    ).fetchall()
    statuses = {r["platform_id"]: r["status"] for r in rows}
    assert statuses["501"] == "active" and statuses["502"] == "active"
    if mode != "partial_forbidden":
        assert statuses["701"] == "removed" and statuses["702"] == "removed"


async def test_s42_t05_complete_shorter_listing_still_removes_missing(conn, user):
    assert (await sync(conn, user)).status == "succeeded"
    assert (await sync(conn, user, "complete")).status == "succeeded"
    row = await (
        await conn.execute(
            "select status from materials where user_id=%s and platform_id='502'", (user,)
        )
    ).fetchone()
    assert row["status"] == "removed"


@pytest.mark.parametrize("mode", ["partial_failure", "malformed"])
async def test_s42_t05_failed_listing_never_runs_removal(conn, user, mode):
    assert (await sync(conn, user)).status == "succeeded"
    assert (await sync(conn, user, mode)).status == "failed"
    rows = await (
        await conn.execute("select status from materials where user_id=%s", (user,))
    ).fetchall()
    assert all(r["status"] == "active" for r in rows)
