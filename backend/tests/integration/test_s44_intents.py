"""S44 uses local synthetic accounts, encrypted fake source text and fake queue/processors."""

import json

import pytest

from app.connectors.base import PlatformError, SyncScope
from app.core.clock import FixedClock
from app.core.crypto import decrypt
from app.db.repositories import sync as sync_repo
from app.sync.pipeline import run_sync
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user
from tests.integration.test_s10_sync_db import NOW, FakeConnector, course, material, post

pytestmark = pytest.mark.integration
TEXT = "synthetic private lesson memoization"


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):
    uid = await create_auth_user(conn)
    await conn.execute("insert into connections(user_id,platform) values (%s,'canvas')", (uid,))
    try:
        yield uid
    finally:
        await delete_auth_user(conn, uid)


async def sync(conn, uid, rows, error=None):
    rid = await sync_repo.create_run(conn, uid, "canvas", {}, "manual", NOW)
    return await run_sync(
        conn,
        user_id=uid,
        run_id=rid,
        scope=SyncScope(),
        connector=FakeConnector(rows, error),
        secret="synthetic",
        clock=FixedClock(NOW),
    )


async def test_s44_t01_partial_commit_keeps_durable_encrypted_intent(conn, user):
    outcome = await sync(
        conn,
        user,
        [course(), material(text=TEXT), post()],
        PlatformError("synthetic later-page failure"),
    )
    assert outcome.status == "failed"
    assert await (
        await conn.execute("select id from materials where user_id=%s", (user,))
    ).fetchone()
    table = await (
        await conn.execute("select to_regclass('public.processing_intents') as name")
    ).fetchone()
    assert table["name"] is not None, "Committed source has no durable processing intent"
    rows = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchall()
    assert len(rows) == 2
    payload = next(r["payload_ciphertext"] for r in rows if r["material_id"])
    assert TEXT.encode() not in bytes(payload)
    assert json.loads(decrypt(bytes(payload)))["text"] == TEXT
    assert all(r["dispatched_at"] is None and r["completed_at"] is None for r in rows)


async def test_s44_t02_enqueue_failure_then_recovery(conn, user):
    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])
    jobs = []

    async def unavailable(args):
        raise RuntimeError("synthetic queue outage")

    async def enqueue(args):
        jobs.append(args)

    assert await intents.dispatch_pending(conn, user_id=user, defer=unavailable) == 0
    assert await intents.dispatch_pending(conn, user_id=user, defer=enqueue) == 1
    assert await intents.dispatch_pending(conn, user_id=user, defer=enqueue) == 0
    assert len(jobs) == 1 and set(jobs[0]) == {"user_id", "intent_id", "revision"}
    assert TEXT not in str(jobs[0]) and "http" not in str(jobs[0])


async def test_s44_t02_expired_lease_recovers_after_crash(conn, user):
    from uuid import uuid4

    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])
    await conn.execute(
        "update processing_intents set "
        "dispatch_token=%s,dispatch_started_at=now()-interval '10 minutes' where user_id=%s",
        (uuid4(), user),
    )
    queued = []

    async def enqueue(args):
        queued.append(args)

    assert await intents.dispatch_pending(conn, user_id=user, defer=enqueue) == 1
    assert len(queued) == 1


async def test_s44_t04_new_revision_is_not_acknowledged_by_old_dispatch(conn, user):
    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])
    jobs = []

    async def enqueue(args):
        jobs.append(args)
        await sync(conn, user, [course(), material(text="synthetic replacement")])

    await intents.dispatch_pending(conn, user_id=user, defer=enqueue)
    row = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()
    assert str(row["revision"]) != jobs[0]["revision"]
    assert row["dispatched_at"] is None

    async def newer(args):
        jobs.append(args)

    assert await intents.dispatch_pending(conn, user_id=user, defer=newer) == 1
    assert (
        jobs[0]["intent_id"] == jobs[1]["intent_id"] and jobs[0]["revision"] != jobs[1]["revision"]
    )


async def test_s44_t05_worker_completes_once_and_drops_payload(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    jobs = []

    async def enqueue(args):
        jobs.append(args)

    await intents.dispatch_pending(conn, user_id=user, defer=enqueue)
    calls = []

    async def process(c, uid, mid, source):
        calls.append(source)
        return "done"

    monkeypatch.setattr(worker, "run_process_material", process)
    assert await intents.execute(conn, **jobs[0]) == "done"
    assert await intents.execute(conn, **jobs[0]) == "already_complete"
    assert calls == [{"download": None, "text": TEXT, "cues": None}]
    row = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()
    assert row["completed_at"] and row["payload_ciphertext"] is None


async def test_s44_t06_clear_and_client_privileges(conn, user):
    import psycopg

    from app.db.repositories import profiles
    from tests.integration.db import AsUser

    await sync(conn, user, [course(), material(text=TEXT)])
    for role, uid in [("authenticated", user), ("anon", None)]:
        async with AsUser(conn, uid, role=role):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute("select * from processing_intents")
    await profiles.delete_user_data(conn, user)
    assert (
        await (
            await conn.execute("select id from processing_intents where user_id=%s", (user,))
        ).fetchone()
        is None
    )


async def test_s44_t03_intent_failure_rolls_back_source_and_prevents_removal(
    conn, user, monkeypatch
):
    from app.db.repositories import processing

    await sync(conn, user, [course(), material(text=TEXT)])
    before = await (
        await conn.execute("select * from materials where user_id=%s", (user,))
    ).fetchone()
    old = await (
        await conn.execute("select revision from processing_intents where user_id=%s", (user,))
    ).fetchone()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic encryption/persistence failure")

    monkeypatch.setattr(processing, "encrypt", fail)
    outcome = await sync(conn, user, [course(), material(text="changed synthetic content")])
    assert outcome.status == "failed"
    after = await (
        await conn.execute("select * from materials where user_id=%s", (user,))
    ).fetchone()
    assert after["id"] == before["id"] and after["content_hash"] == before["content_hash"]
    assert after["status"] == "active"
    current = await (
        await conn.execute("select revision from processing_intents where user_id=%s", (user,))
    ).fetchone()
    assert current == old


async def test_s44_t04_completion_reset_and_old_worker_cannot_change_new_revision(
    conn, user, monkeypatch
):
    from uuid import UUID

    from app.db.repositories import processing
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    jobs = []

    async def enqueue(args):
        jobs.append(args)

    await intents.dispatch_pending(conn, user_id=user, defer=enqueue)
    old = jobs[0]

    async def process(*args):
        await sync(conn, user, [course(), material(text="new synthetic replacement")])
        return "done"

    monkeypatch.setattr(worker, "run_process_material", process)
    await intents.execute(conn, **old)
    await processing.reset(conn, user, UUID(old["intent_id"]), UUID(old["revision"]))
    await processing.complete(conn, user, UUID(old["intent_id"]), UUID(old["revision"]))
    assert await intents.execute(conn, **old) == "superseded"
    row = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()
    assert row["completed_at"] is None and row["dispatched_at"] is None
    assert (
        json.loads(decrypt(bytes(row["payload_ciphertext"])))["text"] == "new synthetic replacement"
    )


async def test_s44_t02_fast_worker_reset_is_not_overwritten_by_late_ack(conn, user):
    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])

    async def enqueue(args):
        await conn.execute("update materials set status='removed' where user_id=%s", (user,))
        assert await intents.execute(conn, **args) == "unavailable"

    await intents.dispatch_pending(conn, user_id=user, defer=enqueue)
    row = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()
    assert row["dispatched_at"] is None and row["dispatch_token"] is None
    await conn.execute("update materials set status='active' where user_id=%s", (user,))
    queued = []

    async def later(args):
        queued.append(args)

    assert await intents.dispatch_pending(conn, user_id=user, defer=later) == 1
    assert len(queued) == 1


async def test_s44_t02_ack_failure_replays_same_revision(conn, user, monkeypatch):
    from app.db.repositories import processing
    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])
    jobs = []

    async def enqueue(args):
        jobs.append(args)

    original = processing.acknowledge

    async def failed_ack(*args):
        raise RuntimeError("synthetic crash after enqueue")

    monkeypatch.setattr(processing, "acknowledge", failed_ack)
    assert await intents.dispatch_pending(conn, user_id=user, defer=enqueue) == 0
    monkeypatch.setattr(processing, "acknowledge", original)
    assert await intents.dispatch_pending(conn, user_id=user, defer=enqueue) == 1
    assert jobs[0] == jobs[1]


async def test_s44_t07_legacy_pending_recovers_on_observation_healthy_is_not_requeued(conn, user):
    await sync(conn, user, [course(), material(text=TEXT), post()])
    await conn.execute("delete from processing_intents where user_id=%s", (user,))
    outcome = await sync(conn, user, [course(), material(text=TEXT), post()])
    assert outcome.stats["unchanged"] == 3
    rows = await (
        await conn.execute("select id from processing_intents where user_id=%s", (user,))
    ).fetchall()
    assert len(rows) == 2
    await conn.execute("update materials set processing_status='done' where user_id=%s", (user,))
    await conn.execute(
        "delete from processing_intents where user_id=%s and material_id is not null", (user,)
    )
    await sync(conn, user, [course(), material(text=TEXT), post()])
    assert (
        await (
            await conn.execute(
                "select id from processing_intents where user_id=%s and material_id is not null",
                (user,),
            )
        ).fetchone()
        is None
    )


async def test_s44_t05_foreign_intent_never_calls_processor(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    row = await (
        await conn.execute("select id,revision from processing_intents where user_id=%s", (user,))
    ).fetchone()
    other = await create_auth_user(conn)

    async def forbidden(*args, **kwargs):
        pytest.fail("foreign owner reached processing")

    monkeypatch.setattr(worker, "run_process_material", forbidden)
    try:
        assert (
            await intents.execute(
                conn, user_id=str(other), intent_id=str(row["id"]), revision=str(row["revision"])
            )
            == "missing"
        )
    finally:
        await delete_auth_user(conn, other)


async def test_s44_t02_actual_queue_preserves_each_delivery_revision(conn, user, monkeypatch):
    from uuid import uuid4

    from procrastinate import PsycopgConnector

    from app.core.settings import get_settings
    from app.sync import intents, jobs

    queue = f"test-s44-{uuid4().hex[:8]}"
    await sync(conn, user, [course(), material(text=TEXT)])
    row = await (
        await conn.execute("select id,revision from processing_intents where user_id=%s", (user,))
    ).fetchone()
    old = {"user_id": str(user), "intent_id": str(row["id"]), "revision": str(row["revision"])}
    configure = jobs.process_intent.configure
    monkeypatch.setattr(
        jobs.process_intent, "configure", lambda **options: configure(queue=queue, **options)
    )
    jobs.app.replace_connector(PsycopgConnector(conninfo=get_settings().database_url))
    try:
        async with jobs.app.open_async():
            await intents._defer(old)
            await intents._defer(old)
            await sync(conn, user, [course(), material(text="replacement")])
            row = await (
                await conn.execute(
                    "select revision from processing_intents where user_id=%s", (user,)
                )
            ).fetchone()
            await intents._defer({**old, "revision": str(row["revision"])})
        queued = await (
            await conn.execute("select args from procrastinate_jobs where queue_name=%s", (queue,))
        ).fetchall()
        assert len(queued) == 3
        assert {r["args"]["revision"] for r in queued} == {old["revision"], str(row["revision"])}
    finally:
        await conn.execute("delete from procrastinate_jobs where queue_name=%s", (queue,))


async def test_s44_t02_notification_failure_does_not_strand_metadata_run(conn, user):
    async def unavailable(*args):
        raise RuntimeError("synthetic callback/queue connection failure")

    rid = await sync_repo.create_run(conn, user, "canvas", {}, "manual", NOW)
    outcome = await run_sync(
        conn,
        user_id=user,
        run_id=rid,
        scope=SyncScope(),
        connector=FakeConnector([course(), material(text=TEXT), post()]),
        secret="synthetic",
        clock=FixedClock(NOW),
        process_material=unavailable,
        process_post=unavailable,
    )
    assert outcome.status == "succeeded"
    saved = await sync_repo.get_run(conn, user, rid)
    assert saved and saved.status == "succeeded"
    rows = await (
        await conn.execute("select dispatched_at from processing_intents where user_id=%s", (user,))
    ).fetchall()
    assert len(rows) == 2 and all(r["dispatched_at"] is None for r in rows)


async def test_s44_t05_failed_processing_is_not_falsely_completed(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    row = await (
        await conn.execute("select id,revision from processing_intents where user_id=%s", (user,))
    ).fetchone()

    async def failed(*args):
        return "failed"

    monkeypatch.setattr(worker, "run_process_material", failed)
    assert (
        await intents.execute(
            conn, user_id=str(user), intent_id=str(row["id"]), revision=str(row["revision"])
        )
        == "retry_scheduled"
    )
    row = await (
        await conn.execute(
            "select completed_at,payload_ciphertext from processing_intents where user_id=%s",
            (user,),
        )
    ).fetchone()
    assert row["completed_at"] is None and row["payload_ciphertext"] is not None


async def test_s44_t02_doing_job_replay_does_not_break_framework_retry(conn, user, monkeypatch):
    from uuid import uuid4

    from procrastinate import PsycopgConnector

    from app.core.settings import get_settings
    from app.sync import intents, jobs

    queue = f"test-s44-retry-{uuid4().hex[:8]}"
    await sync(conn, user, [course(), material(text=TEXT)])
    row = await (
        await conn.execute("select id,revision from processing_intents where user_id=%s", (user,))
    ).fetchone()
    args = {"user_id": str(user), "intent_id": str(row["id"]), "revision": str(row["revision"])}
    configure = jobs.process_intent.configure
    monkeypatch.setattr(
        jobs.process_intent, "configure", lambda **options: configure(queue=queue, **options)
    )
    jobs.app.replace_connector(PsycopgConnector(conninfo=get_settings().database_url))
    try:
        async with jobs.app.open_async():
            await intents._defer(args)
            original = await (
                await conn.execute(
                    "select id from procrastinate_jobs where queue_name=%s", (queue,)
                )
            ).fetchone()
            await conn.execute(
                "update procrastinate_jobs set status='doing' where id=%s", (original["id"],)
            )
            await intents._defer(args)  # enqueue-before-marker replay while original is doing
            await conn.execute(
                "select procrastinate_retry_job_v2(%s::bigint,now(),null,null,null)",
                (original["id"],),
            )
        rows = await (
            await conn.execute(
                "select status from procrastinate_jobs where queue_name=%s", (queue,)
            )
        ).fetchall()
        assert len(rows) == 2 and all(r["status"] == "todo" for r in rows)
        from app.sync.processing import worker

        calls = []

        async def process(*args):
            calls.append(True)
            return "done"

        monkeypatch.setattr(worker, "run_process_material", process)
        assert await intents.execute(conn, **args) == "done"
        assert await intents.execute(conn, **args) == "already_complete"
        assert len(calls) == 1
    finally:
        await conn.execute("delete from procrastinate_jobs where queue_name=%s", (queue,))
