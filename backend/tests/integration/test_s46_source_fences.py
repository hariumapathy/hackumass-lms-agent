"""S46: synthetic imports, independent DB sessions, no live platforms."""

import asyncio

import pytest

from app.connectors.base import AuthExpired, PlatformError, SyncScope
from app.core.clock import FixedClock
from app.core.crypto import encrypt, get_fernet
from app.db.repositories import sync as repo
from app.sync import jobs
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user, open_conn
from tests.integration.test_s10_sync_db import NOW, FakeConnector, course, item

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):
    uid = await create_auth_user(conn)
    await repo.upsert_connection_secret(
        conn, uid, "canvas", encrypt("synthetic", get_fernet()), "canvas_token"
    )
    try:
        yield uid
    finally:
        await conn.execute(
            "delete from procrastinate_jobs where args->'job'->>'user_id'=%s", (str(uid),)
        )
        await delete_auth_user(conn, uid)


async def queued(conn, user, scope=None):
    captured = []

    async def defer(job, priority):
        captured.append(job)

    await jobs.enqueue_sync(conn, user, "canvas", scope or SyncScope(), "manual", defer=defer)
    return captured[0]


async def pipeline(conn, user, connector, scope=None):
    from app.sync.pipeline import run_sync

    scope = scope or SyncScope()
    rid = await repo.create_run(conn, user, connector.platform, {}, "manual", NOW)
    return await run_sync(
        conn, user_id=user, run_id=rid, connector=connector, scope=scope,
        secret="synthetic", clock=FixedClock(NOW),
    )


class Paused(FakeConnector):
    def __init__(self, entered, release, error=None):
        super().__init__([], error)
        self.entered, self.release = entered, release

    async def fetch(self, ctx, scope):
        yield course()
        self.entered.set()
        await self.release.wait()
        if self.error:
            raise self.error
        yield item(title="old")


async def test_s46_t01_overlapping_scopes_serialize(conn, user):
    entered, release, second_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class Second(FakeConnector):
        async def fetch(self, ctx, scope):
            second_entered.set()
            yield item(title="new")

    async with await open_conn() as first, await open_conn() as second:
        a = asyncio.create_task(pipeline(first, user, Paused(entered, release)))
        await asyncio.wait_for(entered.wait(), 3)
        b = asyncio.create_task(pipeline(
            second, user, Second([]), SyncScope(kind="course", course_platform_id="12345")
        ))
        try:
            await asyncio.sleep(.1)
            assert not second_entered.is_set()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(a, b), 5)
    row = await (await conn.execute(
        "select raw_title,status from item_sources where user_id=%s", (user,)
    )).fetchone()
    assert row["raw_title"] == "new" and row["status"] != "removed"


@pytest.mark.parametrize("other", ["platform", "user"])
async def test_s46_t02_independent_sources_proceed(conn, user, other):
    entered, release = asyncio.Event(), asyncio.Event()
    other_user = await create_auth_user(conn) if other == "user" else user
    platform = "piazza" if other == "platform" else "canvas"
    await conn.execute(
        "insert into connections(user_id,platform) values (%s,%s) on conflict do nothing",
        (other_user, platform),
    )
    connector = FakeConnector([course()])
    connector.platform = platform
    try:
        async with await open_conn() as first, await open_conn() as second:
            a = asyncio.create_task(pipeline(first, user, Paused(entered, release)))
            try:
                await asyncio.wait_for(entered.wait(), 3)
                result = await asyncio.wait_for(pipeline(second, other_user, connector), 3)
                assert result.status == "succeeded"
            finally:
                release.set()
                await asyncio.wait_for(a, 5)
    finally:
        if other_user != user:
            await delete_auth_user(conn, other_user)


async def test_s46_t03_disconnect_fences_late_record(conn, user):
    entered, release = asyncio.Event(), asyncio.Event()
    async with await open_conn() as worker:
        task = asyncio.create_task(pipeline(worker, user, Paused(entered, release)))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            await asyncio.wait_for(repo.disconnect(conn, user, "canvas", NOW), 3)
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    assert result.status == "failed"
    assert await repo.get_connection(conn, user, "canvas") is None
    rows = await (await conn.execute(
        "select id from item_sources where user_id=%s", (user,)
    )).fetchall()
    assert not rows
    assert await (await conn.execute(
        "select id from courses where user_id=%s", (user,)
    )).fetchone()


@pytest.mark.parametrize("error", [AuthExpired(), PlatformError("private response"), ValueError()])
async def test_s46_t05_replacement_not_poisoned_by_old_failure(conn, user, error):
    entered, release = asyncio.Event(), asyncio.Event()
    async with await open_conn() as worker:
        task = asyncio.create_task(pipeline(worker, user, Paused(entered, release, error)))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            await repo.upsert_connection_secret(conn, user, "canvas", b"replacement", "canvas_token")
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    connection = await repo.get_connection(conn, user, "canvas")
    assert connection.status == "active" and connection.last_error is None
    assert result.status == "failed"


async def test_s46_t06_queue_binds_epoch_and_old_job_cannot_adopt_replacement(conn, user, monkeypatch):
    old = await queued(conn, user)
    assert old.connection_id and old.secret_revision
    await repo.upsert_connection_secret(conn, user, "canvas", b"replacement", "canvas_token")
    new = await queued(conn, user)
    assert old.sync_run_id != new.sync_run_id
    assert old.secret_revision != new.secret_revision
    connector = FakeConnector([])
    monkeypatch.setattr(jobs, "get_connector", lambda _: connector)
    assert await jobs.execute_sync(conn, old, final_attempt=True) == "ignored"
    assert connector.calls == 0


async def test_s46_t06_terminal_duplicate_and_legacy_job_fail_closed(conn, user, monkeypatch):
    job = await queued(conn, user)
    connector = FakeConnector([])
    monkeypatch.setattr(jobs, "get_connector", lambda _: connector)
    await repo.mark_run(conn, user, job.sync_run_id, "succeeded", NOW)
    assert await jobs.execute_sync(conn, job, final_attempt=True) == "ignored"
    legacy = await queued(conn, user)
    legacy = jobs.SyncJob.model_validate(legacy.model_dump(exclude={"connection_id", "secret_revision"}))
    assert await jobs.execute_sync(conn, legacy, final_attempt=True) == "ignored"
    assert connector.calls == 0


async def test_s46_t08_legacy_secret_update_rotates_epoch_and_invalidates_run(conn, user):
    job = await queued(conn, user)
    await conn.execute(
        "update connection_secrets set ciphertext='changed'::bytea where connection_id="
        "(select id from connections where user_id=%s and platform='canvas')", (user,)
    )
    run = await repo.get_run(conn, user, job.sync_run_id)
    assert run.status == "failed"
