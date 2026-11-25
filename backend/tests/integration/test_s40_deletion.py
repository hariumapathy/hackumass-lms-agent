"""S40 uses synthetic accounts and fake Storage; never live course data or platform calls."""

import asyncio
from uuid import uuid4

import httpx
import pytest

from app.core.errors import AppError
from app.core.settings import get_settings
from app.db.pool import close_pool
from app.db.repositories import profiles
from app.main import create_app
from tests.helpers import auth_header
from tests.integration.db import (
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
    open_conn,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


class FakeStorage:
    def __init__(self):
        self.paths = set()
        self.fail = False

    async def upload(self, path, data, content_type):
        self.paths.add(path)

    async def delete_prefix(self, prefix):
        if self.fail:
            raise RuntimeError("synthetic storage outage")
        removed = {p for p in self.paths if p.startswith(prefix.rstrip("/") + "/")}
        self.paths -= removed
        return len(removed)


@pytest.fixture
async def accounts(conn):
    a, b = await create_auth_user(conn), await create_auth_user(conn)
    try:
        yield a, b
    finally:
        await close_pool()
        for uid in (a, b):
            await delete_auth_user(conn, uid)


async def test_s40_t01_http_removes_rows_files_jobs_only_owner(conn, accounts, monkeypatch):
    from app.sync.processing import storage

    a, b = accounts
    for uid in accounts:
        await insert_minimal_rows(conn, uid)
    files = FakeStorage()
    files.paths = {f"users/{uid}/canvas/file.pdf" for uid in accounts}
    monkeypatch.setattr(storage, "get_storage", lambda: files)
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        for _ in range(2):
            response = await client.delete("/me/data", headers=auth_header(a))
            assert response.status_code == 204, response.text
    assert files.paths == {f"users/{b}/canvas/file.pdf"}
    assert await profiles.get_profile(conn, b) is not None
    for table in profiles.USER_TABLES:
        row = await (
            await conn.execute(f"select count(*) as n from {table} where user_id=%s", (a,))
        ).fetchone()
        assert row["n"] == 0, table
    row = await (await conn.execute("select id from auth.users where id=%s", (a,))).fetchone()
    assert row["id"] == a


async def test_s40_t02_storage_failure_durable_blocks_http_then_retry(conn, accounts, monkeypatch):
    from app.sync.processing import storage

    a, _ = accounts
    await profiles.ensure_profile(conn, a, None)
    files = FakeStorage()
    files.fail = True
    monkeypatch.setattr(storage, "get_storage", lambda: files)
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.delete("/me/data", headers=auth_header(a))
        assert response.status_code == 503
        assert response.json()["error"]["retryable"] is True
        assert (await client.get("/me", headers=auth_header(a))).status_code == 503
        files.fail = False
        assert (await client.delete("/me/data", headers=auth_header(a))).status_code == 204
        assert (await client.get("/me", headers=auth_header(a))).status_code == 200


async def test_s40_t03_pending_drains_shared_work_and_refuses_new(conn, accounts):
    from app.db.deletion import clear_user_data, user_work

    a, _ = accounts
    files = FakeStorage()
    worker_conn, new_conn, delete_conn = await open_conn(), await open_conn(), await open_conn()
    try:
        async with user_work(worker_conn, a):
            deleting = asyncio.create_task(
                clear_user_data(delete_conn, a, storage=files, wait_ms=50)
            )
            with pytest.raises(AppError) as error:
                await deleting
            assert error.value.retryable
            with pytest.raises(AppError):
                async with user_work(new_conn, a):
                    pytest.fail("new work entered during deletion")
        await clear_user_data(delete_conn, a, storage=files)
        async with user_work(new_conn, a):
            pass
    finally:
        for c in (worker_conn, new_conn, delete_conn):
            await c.close()


async def test_s40_t04_queue_payloads_scrubbed_without_breaking_running_ack(conn, accounts):
    from psycopg.types.json import Jsonb

    from app.db.deletion import clear_user_data, retry_pending_deletions

    a, b = accounts
    ids = []
    for uid, status, nested in [
        (a, "todo", True),
        (a, "failed", False),
        (a, "doing", False),
        (b, "todo", False),
    ]:
        args = {"user_id": str(uid), "text": "synthetic private text"}
        if nested:
            args = {"job": args}
        row = await (
            await conn.execute(
                "insert into procrastinate_jobs (queue_name,task_name,args,status) "
                "values ('process','process_post',%s,%s) returning id",
                (Jsonb(args), status),
            )
        ).fetchone()
        ids.append(row["id"])
    try:
        await clear_user_data(conn, a, storage=FakeStorage())
        rows = await (
            await conn.execute(
                "select id,args,status,abort_requested from procrastinate_jobs "
                "where id=any(%s) order by id",
                (ids,),
            )
        ).fetchall()
        assert [r["id"] for r in rows] == ids[2:]
        assert rows[0]["args"] == {"_deletion_owner": str(a)}
        assert rows[0]["abort_requested"] is True
        # Real queue acknowledgment still finds its row; maintenance removes it afterward.
        await conn.execute("select procrastinate_finish_job_v1(%s,'succeeded',false)", (ids[2],))
        await retry_pending_deletions(conn, storage=FakeStorage())
        assert (
            await (
                await conn.execute("select id from procrastinate_jobs where id=%s", (ids[2],))
            ).fetchone()
            is None
        )
        assert "synthetic private text" in str(rows[1]["args"])
    finally:
        await conn.execute("delete from procrastinate_jobs where id=any(%s)", (ids,))


async def test_s40_t05_deleted_sync_run_does_not_replay_after_reconnect(
    conn, accounts, monkeypatch
):
    from app.connectors.base import SyncScope
    from app.db.repositories import sync as repo
    from app.sync import jobs

    a, _ = accounts
    await repo.upsert_connection_secret(
        conn, a, "canvas", b"synthetic-invalid-secret", "canvas_token"
    )
    sj = jobs.SyncJob(
        user_id=a, platform="canvas", scope=SyncScope(), trigger="manual", sync_run_id=uuid4()
    )

    async def forbidden(*args, **kwargs):
        pytest.fail("deleted run reached pipeline")

    monkeypatch.setattr(jobs, "run_sync", forbidden)
    assert await jobs.execute_sync(conn, sj, final_attempt=True) == "deleted"


async def test_s40_t07_worker_recovers_pending_after_service_restart(conn, accounts):
    from app.db.deletion import clear_user_data, retry_pending_deletions, user_work

    a, _ = accounts
    files = FakeStorage()
    files.paths = {f"users/{a}/canvas/orphan.pdf"}
    files.fail = True
    with pytest.raises(AppError):
        await clear_user_data(conn, a, storage=files)
    files.fail = False
    async with await open_conn() as fresh_conn:
        await retry_pending_deletions(fresh_conn, storage=files)
        async with user_work(fresh_conn, a):
            pass
    assert not files.paths


async def test_s40_t06_old_login_cannot_restore_credentials(conn, accounts):
    from app.connectors.browser.manager import LoginManager
    from app.connectors.browser.store import login_completion_guard, login_generation
    from app.db.deletion import clear_user_data
    from tests.unit.test_s13_browser import FakeProvider

    a, _ = accounts
    ready = asyncio.Event()
    saved = []

    class Provider(FakeProvider):
        async def poll(self, handle):
            await ready.wait()
            return "succeeded"

    async def save(*args):
        saved.append(args)

    manager = LoginManager(
        Provider(), save, snapshot=login_generation, completion_guard=login_completion_guard
    )
    old = await manager.start(a, "gradescope")
    await clear_user_data(conn, a, storage=FakeStorage())
    ready.set()
    await manager.wait(old.login_id)
    assert old.state == "failed"
    assert not saved
    new = await manager.start(a, "gradescope")
    await manager.wait(new.login_id)
    assert new.state == "succeeded"
    assert len(saved) == 1


async def test_s40_t08_state_rls_and_cancel_releases_shared_lock(conn, accounts):
    import psycopg

    from app.db.deletion import clear_user_data, user_work
    from tests.integration.db import AsUser

    a, _ = accounts
    await clear_user_data(conn, a, storage=FakeStorage())
    async with AsUser(conn, a):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with conn.transaction():
                await conn.execute("update account_data_state set state='complete'")
    entered = asyncio.Event()

    async def work():
        async with await open_conn() as c:
            async with user_work(c, a):
                entered.set()
                await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await clear_user_data(conn, a, storage=FakeStorage(), wait_ms=0)


async def test_s40_t05_prefetched_merge_cannot_modify_reconnected_data(conn, accounts, monkeypatch):
    from app.db.deletion import clear_user_data
    from app.sync import jobs, merge

    a, _ = accounts
    await clear_user_data(conn, a, storage=FakeStorage())
    await profiles.ensure_profile(conn, a, None)

    async def forbidden(*args, **kwargs):
        pytest.fail("old merge modified a reconnected account")

    monkeypatch.setattr(merge, "merge_user", forbidden)
    await jobs.merge_user(user_id=str(a))  # old job envelope has no generation


async def test_s40_t03_sse_holds_guard_until_stream_finishes(conn, accounts, monkeypatch):
    from typing import Annotated

    from fastapi import Depends
    from fastapi.responses import StreamingResponse

    from app.api.deps import data_user
    from app.core.auth import UserCtx
    from app.db.deletion import clear_user_data

    a, _ = accounts
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    app = create_app()
    entered, release = asyncio.Event(), asyncio.Event()

    async def stream():
        entered.set()
        yield b"data: synthetic\n\n"
        await release.wait()

    @app.get("/s40-stream")
    async def guarded(user: Annotated[UserCtx, Depends(data_user)]):
        return StreamingResponse(stream(), media_type="text/event-stream")

    # Avoid postponed annotation/global resolution ambiguity in this local test route.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        request = asyncio.create_task(client.get("/s40-stream", headers=auth_header(a)))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            with pytest.raises(AppError):
                await clear_user_data(conn, a, storage=FakeStorage(), wait_ms=20)
        finally:
            release.set()
            await request
    await clear_user_data(conn, a, storage=FakeStorage(), wait_ms=0)


async def test_s40_t05_scheduler_rechecks_stale_due_snapshot(conn, accounts, monkeypatch):
    from app.db.deletion import clear_user_data
    from app.db.repositories import sync as repo
    from app.sync import jobs

    a, _ = accounts
    await repo.upsert_connection_secret(conn, a, "canvas", b"synthetic", "canvas_token")

    async def stale_snapshot(c, now):
        await clear_user_data(conn, a, storage=FakeStorage())
        return [(a, "canvas")]

    async def forbidden(*args, **kwargs):
        pytest.fail("stale scheduler snapshot recreated deleted runs")

    monkeypatch.setattr(jobs, "due_connections", stale_snapshot)
    monkeypatch.setattr(jobs, "enqueue_sync", forbidden)
    await jobs.schedule_syncs(timestamp=0)


async def test_s40_t02_public_calendar_refuses_pending_cleanup(conn, accounts, monkeypatch):
    from app.db.deletion import clear_user_data
    from app.db.repositories import calendar

    a, _ = accounts
    token = await calendar.feed_token(conn, a)
    files = FakeStorage()
    files.fail = True
    with pytest.raises(AppError):
        await clear_user_data(conn, a, storage=files)
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get(f"/calendar/{token}.ics")
        assert response.status_code == 404  # feed row was already revoked before storage failed


async def test_s40_t08_lost_lock_connection_cannot_recreate_cleared_rows(
    conn, accounts, monkeypatch
):
    from contextlib import asynccontextmanager
    from typing import Annotated

    from fastapi import Depends

    from app.api.deps import data_user
    from app.core.auth import UserCtx
    from app.db import deletion
    from app.db.pool import connection

    a, _ = accounts
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    original = deletion.user_work
    entered, release = asyncio.Event(), asyncio.Event()
    pids = []

    @asynccontextmanager
    async def capture(c, uid):
        async with original(c, uid) as epoch:
            pids.append(c.pgconn.backend_pid)
            yield epoch

    monkeypatch.setattr(deletion, "user_work", capture)
    app = create_app()

    @app.get("/s40-delayed-write")
    async def delayed(user: Annotated[UserCtx, Depends(data_user)]):
        entered.set()
        await release.wait()
        async with connection() as c:
            await profiles.ensure_profile(c, user.user_id, None)
        return {"ok": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        request = asyncio.create_task(client.get("/s40-delayed-write", headers=auth_header(a)))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await conn.execute("select pg_terminate_backend(%s)", (pids[0],))
            await deletion.clear_user_data(conn, a, storage=FakeStorage())
        finally:
            release.set()
            try:
                await request
            except RuntimeError:
                pass  # old dependency can fail unlocking after its response already started
    assert await profiles.get_profile(conn, a) is None


async def test_s40_t08_request_leases_reuse_session_and_serialize_transactions(accounts):
    from app.db.deletion import user_session
    from app.db.pool import connection

    a, _ = accounts
    events = []
    async with user_session(a):
        async with connection() as outer:
            async with connection() as inner:
                assert inner is outer

        async def tool(name):
            async with connection() as c:
                assert c is outer
                async with c.transaction():
                    events.append(name)
                    await asyncio.sleep(0.01)
                    await c.execute("select 1")
                    events.append(name)

        await asyncio.wait_for(asyncio.gather(tool("a"), tool("b")), 2)
    assert events in (["a", "a", "b", "b"], ["b", "b", "a", "a"])


async def test_s40_t08_escaped_task_cannot_borrow_after_request_ends(accounts):
    from app.db.deletion import user_session
    from app.db.pool import connection

    a, _ = accounts
    ready = asyncio.Event()

    async def escaped():
        await ready.wait()
        with pytest.raises(AppError):
            async with connection():
                pytest.fail("escaped task borrowed a fresh connection")

    async with user_session(a):
        task = asyncio.create_task(escaped())
    ready.set()
    await task


async def test_s40_t06_login_outlives_request_with_its_own_guard(accounts):
    from app.connectors.browser.manager import LoginManager
    from app.connectors.browser.store import login_completion_guard, login_generation
    from app.db.deletion import user_session
    from app.db.pool import connection
    from tests.unit.test_s13_browser import FakeProvider

    a, _ = accounts
    ready = asyncio.Event()

    class Provider(FakeProvider):
        async def poll(self, handle):
            await ready.wait()
            return "succeeded"

    async def save(uid, platform, state):
        # Mimics the real callback's DB lease; must reuse completion guard, not expired request.
        async with connection() as c:
            await profiles.ensure_profile(c, uid, None)

    manager = LoginManager(
        Provider(), save, snapshot=login_generation, completion_guard=login_completion_guard
    )
    async with user_session(a):
        session = await manager.start(a, "gradescope")
    ready.set()
    await asyncio.wait_for(manager.wait(session.login_id), 2)
    assert session.state == "succeeded"


async def test_s40_t08_request_exit_drains_entered_child_lease(conn, accounts):
    from app.db.deletion import clear_user_data, user_session
    from app.db.pool import connection

    a, _ = accounts
    entered, leaving, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    children = []

    async def child():
        async with connection() as c:
            entered.set()
            await release.wait()
            await profiles.ensure_profile(c, a, None)

    async def parent():
        async with user_session(a):
            children.append(asyncio.create_task(child()))
            await entered.wait()
            leaving.set()

    request = asyncio.create_task(parent())
    await leaving.wait()
    await asyncio.sleep(0.01)
    try:
        with pytest.raises(AppError):
            await clear_user_data(conn, a, storage=FakeStorage(), wait_ms=20)
    finally:
        release.set()
        await request
        await asyncio.gather(*children)
    await clear_user_data(conn, a, storage=FakeStorage(), wait_ms=0)
    assert await profiles.get_profile(conn, a) is None
