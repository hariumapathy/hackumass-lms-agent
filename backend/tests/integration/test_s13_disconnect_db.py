"""S13-T06: disconnect deletes the secret and cancels queued jobs (local DB + real queue)."""

from datetime import UTC, datetime

import pytest
from procrastinate import PsycopgConnector

from app.connectors.base import SyncScope
from app.core.clock import FixedClock
from app.core.settings import get_settings
from app.db.repositories import sync as repo
from app.sync import jobs
from app.sync.disconnect import DISCONNECTED, disconnect_platform
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 14, 21, 0, tzinfo=UTC)


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


async def _queued_jobs(conn, uid) -> int:  # noqa: ANN001
    cur = await conn.execute(
        "select count(*) as n from procrastinate_jobs where status = 'todo' "
        "and args->'job'->>'user_id' = %s",
        (str(uid),),
    )
    row = await cur.fetchone()
    return row["n"]


async def test_s13_t06_disconnect_deletes_secret_and_cancels_jobs(conn) -> None:  # noqa: ANN001
    uid = await create_auth_user(conn)
    other = await create_auth_user(conn)
    jobs.app.replace_connector(PsycopgConnector(conninfo=get_settings().database_url))
    try:
        async with jobs.app.open_async():
            for u in (uid, other):
                await repo.upsert_connection_secret(conn, u, "gradescope", b"ct", "storage_state")
                await repo.upsert_connection_secret(conn, u, "canvas", b"ct", "canvas_token")
            run = await jobs.enqueue_sync(conn, uid, "gradescope", SyncScope(), "manual")
            await jobs.enqueue_sync(conn, uid, "canvas", SyncScope(), "manual")
            await jobs.enqueue_sync(conn, other, "gradescope", SyncScope(), "manual")
            assert await _queued_jobs(conn, uid) == 2

            assert await disconnect_platform(conn, uid, "gradescope", clock=FixedClock(NOW))

            assert await repo.get_connection(conn, uid, "gradescope") is None
            assert await repo.get_secret(conn, uid, "gradescope") is None
            r = await repo.get_run(conn, uid, run)
            assert r and r.status == "failed" and r.error == DISCONNECTED
            assert await _queued_jobs(conn, uid) == 1  # canvas job untouched
            assert await repo.get_secret(conn, uid, "canvas") == b"ct"
            assert await repo.get_secret(conn, other, "gradescope") == b"ct"  # other student
            assert await _queued_jobs(conn, other) == 1
            # Idempotent
            assert not await disconnect_platform(conn, uid, "gradescope")
    finally:
        await conn.execute(
            "delete from procrastinate_jobs where args->'job'->>'user_id' in (%s, %s)",
            (str(uid), str(other)),
        )
        await delete_auth_user(conn, uid)
        await delete_auth_user(conn, other)


async def test_s13_t06_disconnect_route_db_mode(conn, monkeypatch) -> None:  # noqa: ANN001
    import httpx

    from app.db.pool import close_pool
    from app.main import create_app
    from tests.helpers import auth_header

    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    uid = await create_auth_user(conn)
    try:
        await repo.upsert_connection_secret(conn, uid, "canvas", b"ct", "canvas_token")
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.delete("/connections/canvas", headers=auth_header(uid))
            assert r.status_code == 204
            assert await repo.get_connection(conn, uid, "canvas") is None
            again = await client.delete("/connections/canvas", headers=auth_header(uid))
            assert again.status_code == 204
            assert (await client.delete("/connections/canvas")).status_code == 401
    finally:
        await close_pool()
        await delete_auth_user(conn, uid)
