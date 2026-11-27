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
        conn,
        user_id=user,
        run_id=rid,
        connector=connector,
        scope=scope,
        secret="synthetic",
        clock=FixedClock(NOW),
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
        b = asyncio.create_task(
            pipeline(second, user, Second([]), SyncScope(kind="course", course_platform_id="12345"))
        )
        try:
            await asyncio.sleep(0.1)
            assert not second_entered.is_set()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(a, b), 5)
    row = await (
        await conn.execute("select raw_title,status from item_sources where user_id=%s", (user,))
    ).fetchone()
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
    rows = await (
        await conn.execute("select id from item_sources where user_id=%s", (user,))
    ).fetchall()
    assert not rows
    assert await (await conn.execute("select id from courses where user_id=%s", (user,))).fetchone()


@pytest.mark.parametrize("error", [AuthExpired(), PlatformError("private response"), ValueError()])
async def test_s46_t05_replacement_not_poisoned_by_old_failure(conn, user, error):
    entered, release = asyncio.Event(), asyncio.Event()
    async with await open_conn() as worker:
        task = asyncio.create_task(pipeline(worker, user, Paused(entered, release, error)))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            await repo.upsert_connection_secret(
                conn, user, "canvas", b"replacement", "canvas_token"
            )
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    connection = await repo.get_connection(conn, user, "canvas")
    assert connection and connection.status == "active" and connection.last_error is None
    assert result.status == "failed"


async def test_s46_t06_queue_binds_epoch_and_old_job_cannot_adopt_replacement(
    conn, user, monkeypatch
):
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
    legacy = jobs.SyncJob.model_validate(
        legacy.model_dump(exclude={"connection_id", "secret_revision"})
    )
    assert await jobs.execute_sync(conn, legacy, final_attempt=True) == "ignored"
    assert connector.calls == 0


async def test_s46_t06_queue_after_disconnect_returns_clear_conflict(conn, user):
    from app.core.errors import AppError

    await repo.disconnect(conn, user, "canvas", NOW)
    with pytest.raises(AppError) as error:
        await queued(conn, user)
    assert error.value.status == 409
    assert error.value.code == "conflict"


async def test_s46_t08_legacy_secret_update_rotates_epoch_and_invalidates_run(conn, user):
    job = await queued(conn, user)
    await conn.execute(
        "update connection_secrets set ciphertext='changed'::bytea where connection_id="
        "(select id from connections where user_id=%s and platform='canvas')",
        (user,),
    )
    run = await repo.get_run(conn, user, job.sync_run_id)
    assert run and run.status == "failed"


async def test_s46_t04_disconnect_waits_for_entered_transaction_only(conn, user, monkeypatch):
    from app.db.repositories import processing
    from tests.integration.test_s10_sync_db import material

    entered, release, disconnected = asyncio.Event(), asyncio.Event(), asyncio.Event()
    capture = processing.capture

    async def paused_capture(*args, **kwargs):
        entered.set()
        await release.wait()
        return await capture(*args, **kwargs)

    monkeypatch.setattr(processing, "capture", paused_capture)

    class Transactional(FakeConnector):
        async def fetch(self, ctx, scope):
            yield course()
            yield material(text="Synthetic notes")
            await disconnected.wait()
            yield item()

    async def disconnect():
        await repo.disconnect(conn, user, "canvas", NOW)
        disconnected.set()

    async with await open_conn() as worker:
        task = asyncio.create_task(pipeline(worker, user, Transactional([])))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            stop = asyncio.create_task(disconnect())
            try:
                await asyncio.sleep(0.1)
                assert not stop.done()
            finally:
                release.set()
                await asyncio.wait_for(stop, 5)
        finally:
            release.set()
            disconnected.set()
            result = await asyncio.wait_for(task, 5)
    assert result.status == "failed"
    assert await (
        await conn.execute("select id from materials where user_id=%s", (user,))
    ).fetchone()
    assert not await (
        await conn.execute("select id from item_sources where user_id=%s", (user,))
    ).fetchone()


async def test_s46_t05_disconnect_reconnect_same_secret_is_new_grant(conn, user):
    entered, release = asyncio.Event(), asyncio.Event()
    original = await repo.get_connection(conn, user, "canvas")
    async with await open_conn() as worker:
        task = asyncio.create_task(pipeline(worker, user, Paused(entered, release)))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            ciphertext = await repo.get_secret(conn, user, "canvas")
            assert ciphertext
            await repo.disconnect(conn, user, "canvas", NOW)
            await repo.upsert_connection_secret(conn, user, "canvas", ciphertext, "canvas_token")
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    replacement = await repo.get_connection(conn, user, "canvas")
    assert replacement and original and replacement.id != original.id
    assert replacement.status == "active" and replacement.last_sync_at is None
    assert result.status == "failed"


async def test_s46_t08_secret_delete_reinsert_cannot_reuse_epoch(conn, user):
    old = await queued(conn, user)
    await conn.execute(
        "delete from connection_secrets where connection_id=%s", (old.connection_id,)
    )
    await conn.execute(
        "insert into connection_secrets(connection_id,ciphertext,kind,revision) "
        "values (%s,'new'::bytea,'canvas_token',%s)",
        (old.connection_id, old.secret_revision),
    )
    new = await queued(conn, user)
    assert new.secret_revision != old.secret_revision
    assert new.sync_run_id != old.sync_run_id


async def test_s46_t08_canceled_waiter_releases_session_lock(conn, user):
    from app.sync.access import source_lock

    async with await open_conn() as holder, await open_conn() as waiter:
        async with source_lock(holder, user, "canvas"):
            entered = asyncio.Event()

            async def wait():
                entered.set()
                async with source_lock(waiter, user, "canvas"):
                    pytest.fail("must not enter held lock")

            task = asyncio.create_task(wait())
            await entered.wait()
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert waiter.closed
    async with asyncio.timeout(3):
        async with source_lock(conn, user, "canvas"):
            pass


async def test_s46_t08_rotation_only_invalidates_owner_platform(conn, user):
    other = await create_auth_user(conn)
    try:
        await repo.upsert_connection_secret(conn, other, "canvas", b"other", "canvas_token")
        other_job = await queued(conn, other)
        mine = await queued(conn, user)
        await repo.upsert_connection_secret(conn, user, "canvas", b"changed", "canvas_token")
        mine_run = await repo.get_run(conn, user, mine.sync_run_id)
        other_run = await repo.get_run(conn, other, other_job.sync_run_id)
        assert mine_run and mine_run.status == "failed"
        assert other_run and other_run.status == "queued"
    finally:
        await delete_auth_user(conn, other)


async def test_s46_t06_rotation_cancels_real_queued_job_not_doing_ack(conn, user):
    from uuid import uuid4

    from procrastinate import PsycopgConnector

    from app.core.settings import get_settings

    queue = f"test-s46-{uuid4().hex[:12]}"
    jobs.app.replace_connector(PsycopgConnector(conninfo=get_settings().database_url))

    async def defer(job, priority):
        await jobs.sync_platform.configure(queue=queue, priority=priority).defer_async(
            job=job.model_dump(mode="json")
        )

    async with jobs.app.open_async():
        try:
            running = await jobs.enqueue_sync(
                conn, user, "canvas", SyncScope(), "manual", defer=defer
            )
            # Framework SQL accepts a NULL worker for synthetic/manual fetches (S10 precedent).
            doing = await jobs.app.job_manager.fetch_job(queues=[queue], worker_id=None)  # type: ignore[arg-type]
            assert doing
            pending = await jobs.enqueue_sync(
                conn,
                user,
                "canvas",
                SyncScope(kind="course", course_platform_id="12345"),
                "manual",
                defer=defer,
            )
            await repo.upsert_connection_secret(conn, user, "canvas", b"new", "canvas_token")
            rows = await (
                await conn.execute(
                    "select status,args from procrastinate_jobs where queue_name=%s", (queue,)
                )
            ).fetchall()
            statuses = {r["args"]["job"]["sync_run_id"]: r["status"] for r in rows}
            assert statuses[str(running)] == "doing"
            assert statuses[str(pending)] == "cancelled"
            new = await jobs.enqueue_sync(conn, user, "canvas", SyncScope(), "manual", defer=defer)
            assert new != running
        finally:
            await conn.execute("delete from procrastinate_jobs where queue_name=%s", (queue,))


async def test_s46_t06_duplicate_inflight_delivery_fetches_once(conn, user, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    job = await queued(conn, user)
    connector = Paused(entered, release)
    monkeypatch.setattr(jobs, "get_connector", lambda _: connector)

    # No real queue operations from this synthetic execution.
    async def defer(*args, **kwargs):
        pass

    monkeypatch.setattr(jobs, "_defer", defer)
    async with await open_conn() as first, await open_conn() as second:
        a = asyncio.create_task(jobs.execute_sync(first, job, final_attempt=True))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            b = asyncio.create_task(jobs.execute_sync(second, job, final_attempt=True))
            await asyncio.sleep(0.05)
        finally:
            release.set()
            results = await asyncio.wait_for(asyncio.gather(a, b), 5)
    assert sorted(results) == ["ignored", "succeeded"]
    run = await repo.get_run(conn, user, job.sync_run_id)
    assert run and run.status == "succeeded"
