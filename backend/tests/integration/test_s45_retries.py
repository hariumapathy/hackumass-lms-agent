"""S45 synthetic local-DB retry/recovery, fake processors only."""

import httpx
import pytest

from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user
from tests.integration.test_s10_sync_db import course, material, post
from tests.integration.test_s44_intents import TEXT, sync

pytestmark = pytest.mark.integration


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


async def intent(conn, user):
    return await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()


def args(row):
    return {
        "user_id": str(row["user_id"]),
        "intent_id": str(row["id"]),
        "revision": str(row["revision"]),
    }


async def test_s45_t03_transient_backoff_then_success(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)
    calls = []

    async def failing(*a):
        calls.append(True)
        raise httpx.ReadTimeout("synthetic secret")

    monkeypatch.setattr(worker, "run_process_material", failing)
    assert await intents.execute(conn, **args(original)) == "retry_scheduled"
    row = await intent(conn, user)
    assert row["attempts"] == 1 and row["completed_at"] is None and row["blocked_reason"] is None
    assert row["next_attempt_at"] > row["last_started_at"]
    assert await intents.execute(conn, **args(original)) == "deferred"
    assert len(calls) == 1
    await conn.execute(
        "update processing_intents set next_attempt_at=now()-interval '1 second' where user_id=%s",
        (user,),
    )

    async def success(*a):
        return "done"

    monkeypatch.setattr(worker, "run_process_material", success)
    assert await intents.execute(conn, **args(original)) == "done"
    row = await intent(conn, user)
    assert row["attempts"] == 2 and row["completed_at"] and row["payload_ciphertext"] is None


async def test_s45_t03_attempt_limit_persists(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)
    calls = []

    async def fail(*a):
        calls.append(True)
        raise httpx.ConnectError("synthetic failure")

    monkeypatch.setattr(worker, "run_process_material", fail)
    for _ in range(4):
        await conn.execute(
            "update processing_intents set next_attempt_at=now()-interval '1 "
            "second' where user_id=%s",
            (user,),
        )
        await intents.execute(conn, **args(original))
    row = await intent(conn, user)
    assert row["attempts"] == 4 and row["blocked_reason"] == "exhausted"
    assert await intents.execute(conn, **args(original)) == "blocked"
    assert len(calls) == 4 and row["completed_at"] is None


async def test_s45_t01_configuration_and_permanent_failures_stop(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.failures import ProcessingFailure

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)

    async def fail(*a):
        raise ProcessingFailure("configuration", "service_configuration")

    monkeypatch.setattr(worker, "run_process_material", fail)
    assert await intents.execute(conn, **args(original)) == "blocked"
    row = await intent(conn, user)
    assert (
        row["blocked_reason"] == "configuration"
        and row["last_error_code"] == "service_configuration"
    )


async def test_s45_t05_stale_without_active_job_recovers(conn, user):
    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])
    await conn.execute(
        "update processing_intents set dispatched_at=now()-interval '20 minutes' where user_id=%s",
        (user,),
    )
    assert await intents.recover_stalled(conn, user_id=user) == 1
    row = await intent(conn, user)
    assert row["dispatched_at"] is None and row["attempts"] == 1


async def test_s45_t06_operator_resume_is_scoped_and_rotates_revision(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.failures import ProcessingFailure

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)

    async def fail(*a):
        raise ProcessingFailure("configuration", "service_configuration")

    monkeypatch.setattr(worker, "run_process_material", fail)
    await intents.execute(conn, **args(original))
    other = await create_auth_user(conn)
    try:
        assert await intents.resume(conn, other) == 0
        assert await intents.resume(conn, user) == 1
    finally:
        await delete_auth_user(conn, other)
    row = await intent(conn, user)
    assert (
        row["revision"] != original["revision"]
        and row["attempts"] == 0
        and row["blocked_reason"] is None
    )
    assert await intents.execute(conn, **args(original)) == "superseded"


async def test_s45_t07_legacy_post_backfill_uses_owned_stored_body(conn, user):
    from app.sync import intents

    await sync(conn, user, [course(), post()])
    await conn.execute("delete from processing_intents where user_id=%s", (user,))
    assert await intents.recover_legacy_posts(conn, user_id=user) == 1
    row = await intent(conn, user)
    assert row["post_id"] and row["payload_ciphertext"] is None


async def test_s45_t07_legacy_refresh_has_finite_no_record_budget(conn, user):
    from app.db.repositories import sync as connections
    from app.sync.recovery import recover_legacy_materials

    await sync(conn, user, [course(), material(text=TEXT)])
    await conn.execute("delete from processing_intents where user_id=%s", (user,))
    await conn.execute("update materials set processing_status='failed' where user_id=%s", (user,))
    await connections.upsert_connection_secret(conn, user, "canvas", b"synthetic", "canvas_token")
    from psycopg.types.json import Jsonb

    parent = await (
        await conn.execute("select id from materials where user_id=%s", (user,))
    ).fetchone()
    active = await (
        await conn.execute(
            "insert into procrastinate_jobs(queue_name,task_name,args,status) "
            "values ('test-s45','process_material',%s,'doing') returning id",
            (Jsonb({"user_id": str(user), "material_id": str(parent["id"])}),),
        )
    ).fetchone()
    try:
        assert await recover_legacy_materials(conn, user_id=user, enqueue=lambda *a: None) == 0
        assert await intent(conn, user) is None
    finally:
        await conn.execute("delete from procrastinate_jobs where id=%s", (active["id"],))
    queued = []

    async def enqueue(c, uid, platform, scope, trigger):
        queued.append((uid, platform, scope.kind))

    for _ in range(4):
        await conn.execute(
            "update processing_intents set next_attempt_at=now()-interval '1 "
            "second' where user_id=%s",
            (user,),
        )
        assert await recover_legacy_materials(conn, user_id=user, enqueue=enqueue) == 1
    assert await recover_legacy_materials(conn, user_id=user, enqueue=enqueue) == 0
    row = await intent(conn, user)
    assert (
        row["blocked_reason"] == "exhausted"
        and row["attempts"] == 4
        and row["payload_ciphertext"] is None
    )
    assert len(queued) == 4 and all(
        q[0] == user and q[1:] == ("canvas", "material") for q in queued
    )


async def test_s45_t06_same_hash_new_reference_recovers_source_access(conn, user, monkeypatch):
    from app.connectors.base import DownloadRef
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.failures import ProcessingFailure

    old = material(download=DownloadRef(url="https://canvas.example/old-ref"))
    await sync(conn, user, [course(), old])
    before = await intent(conn, user)

    async def inaccessible(*a):
        raise ProcessingFailure("source_auth", "source_access")

    monkeypatch.setattr(worker, "run_process_material", inaccessible)
    await intents.execute(conn, **args(before))
    # Same inaccessible reference is not a fresh authorization signal.
    await sync(conn, user, [course(), old])
    assert (await intent(conn, user))["blocked_reason"] == "source_auth"
    fresh = old.model_copy(update={"download": DownloadRef(url="https://canvas.example/fresh-ref")})
    await sync(conn, user, [course(), fresh])
    after = await intent(conn, user)
    assert after["source_hash"] == before["source_hash"] and after["revision"] != before["revision"]
    assert after["blocked_reason"] is None and after["attempts"] == 0


async def test_s45_t05_active_job_is_not_stolen(conn, user):
    from psycopg.types.json import Jsonb

    from app.sync import intents

    await sync(conn, user, [course(), material(text=TEXT)])
    row = await intent(conn, user)
    await conn.execute(
        "update processing_intents set dispatched_at=now()-interval '20 minutes' where user_id=%s",
        (user,),
    )
    job = await (
        await conn.execute(
            "insert into procrastinate_jobs(queue_name,task_name,args) values "
            "('test-s45','process_intent',%s) returning id",
            (Jsonb(args(row)),),
        )
    ).fetchone()
    try:
        assert await intents.recover_stalled(conn, user_id=user) == 0
        assert (await intent(conn, user))["attempts"] == 0
    finally:
        await conn.execute("delete from procrastinate_jobs where id=%s", (job["id"],))


async def test_s45_t06_newly_validated_credential_resumes_auth_only(conn, user, monkeypatch):
    from app.db.repositories import sync as connections
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.failures import ProcessingFailure

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)

    async def inaccessible(*a):
        raise ProcessingFailure("source_auth", "source_access")

    monkeypatch.setattr(worker, "run_process_material", inaccessible)
    await intents.execute(conn, **args(original))
    await connections.upsert_connection_secret(
        conn, user, "canvas", b"synthetic-new-secret", "canvas_token"
    )
    current = await intent(conn, user)
    assert current["blocked_reason"] is None and current["revision"] != original["revision"]
    assert current["attempts"] == 0


async def test_s45_t04_old_failure_cannot_mark_replacement_material_failed(conn, user, monkeypatch):
    from app.core.embeddings import FakeEmbeddings
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.process import MaterialSource, process_material

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)

    class Interrupted(FakeEmbeddings):
        async def embed(self, texts):
            await sync(conn, user, [course(), material(text="newer replacement lesson")])
            raise httpx.ReadTimeout("synthetic old attempt failure")

    async def process(c, uid, mid, source):
        return await process_material(
            c, uid, mid, source=MaterialSource.model_validate(source), embeddings=Interrupted()
        )

    monkeypatch.setattr(worker, "run_process_material", process)
    assert await intents.execute(conn, **args(original)) == "superseded"
    current = await intent(conn, user)
    assert current["attempts"] == 0 and current["blocked_reason"] is None
    row = await (
        await conn.execute("select processing_status from materials where user_id=%s", (user,))
    ).fetchone()
    assert row["processing_status"] == "pending"


async def test_s45_t03_concurrent_duplicate_claim_cannot_bypass_backoff(conn, user, monkeypatch):
    import asyncio

    from app.sync import intents
    from app.sync.processing import worker
    from tests.integration.db import open_conn

    await sync(conn, user, [course(), material(text=TEXT)])
    row = await intent(conn, user)
    calls = []

    async def fail(*a):
        calls.append(True)
        await asyncio.sleep(0.01)
        raise httpx.ReadTimeout("synthetic")

    monkeypatch.setattr(worker, "run_process_material", fail)
    async with await open_conn() as other:
        outcomes = await asyncio.gather(
            intents.execute(conn, **args(row)), intents.execute(other, **args(row))
        )
    assert sorted(outcomes) == ["deferred", "retry_scheduled"] and len(calls) == 1
    assert (await intent(conn, user))["attempts"] == 1


async def test_s45_t04_changed_source_resets_permanent_failure(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.failures import ProcessingFailure

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)

    async def fail(*a):
        raise ProcessingFailure("permanent", "extraction_failed")

    monkeypatch.setattr(worker, "run_process_material", fail)
    await intents.execute(conn, **args(original))
    await sync(conn, user, [course(), material(text=TEXT)])
    assert (await intent(conn, user))["blocked_reason"] == "permanent"
    await sync(conn, user, [course(), material(text="fixed source")])
    current = await intent(conn, user)
    assert current["blocked_reason"] is None and current["attempts"] == 0
    assert await intents.execute(conn, **args(original)) == "superseded"


async def test_s45_t06_pending_deletion_prevents_operator_resume(conn, user):
    from app.core.errors import AppError
    from app.sync import intents

    await conn.execute(
        "insert into account_data_state(user_id,generation,state) values (%s,1,'pending')", (user,)
    )
    with pytest.raises(AppError):
        await intents.resume(conn, user)


async def test_s45_t07_legacy_post_with_active_processor_is_not_backfilled(conn, user):
    from psycopg.types.json import Jsonb

    from app.sync import intents

    await sync(conn, user, [course(), post()])
    original = await intent(conn, user)
    await conn.execute("delete from processing_intents where user_id=%s", (user,))
    job = await (
        await conn.execute(
            "insert into procrastinate_jobs(queue_name,task_name,args,status) "
            "values ('test-s45','process_post',%s,'doing') returning id",
            (Jsonb({"user_id": str(user), "post_id": str(original["post_id"])}),),
        )
    ).fetchone()
    try:
        assert await intents.recover_legacy_posts(conn, user_id=user) == 0
        assert await intent(conn, user) is None
    finally:
        await conn.execute("delete from procrastinate_jobs where id=%s", (job["id"],))


async def test_s45_t01_one_inaccessible_file_does_not_expire_whole_connection(
    conn, user, monkeypatch, caplog
):
    from app.connectors.base import DownloadRef, SourceAccessError
    from app.core.embeddings import FakeEmbeddings
    from app.db.repositories import sync as connections
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.process import MaterialSource, process_material

    await sync(
        conn,
        user,
        [course(), material(download=DownloadRef(url="https://canvas.example/private-file"))],
    )
    original = await intent(conn, user)

    async def download(ref):
        raise SourceAccessError("synthetic-sensitive-file-link")

    async def process(c, uid, mid, source):
        return await process_material(
            c,
            uid,
            mid,
            source=MaterialSource.model_validate(source),
            embeddings=FakeEmbeddings(),
            downloader=download,
        )

    monkeypatch.setattr(worker, "run_process_material", process)
    assert await intents.execute(conn, **args(original)) == "blocked"
    connection = await connections.get_connection(conn, user, "canvas")
    assert connection is not None and connection.status == "active"
    assert (await intent(conn, user))["blocked_reason"] == "source_auth"
    assert "synthetic-sensitive-file-link" not in caplog.text


async def test_s45_t02_posts_use_the_same_retry_policy(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), post()])
    row = await intent(conn, user)

    async def fail(*a):
        raise httpx.ConnectTimeout("synthetic provider failure")

    monkeypatch.setattr(worker, "run_process_post", fail)
    assert await intents.execute(conn, **args(row)) == "retry_scheduled"
    current = await intent(conn, user)
    assert (
        current["attempts"] == 1
        and current["blocked_reason"] is None
        and current["completed_at"] is None
    )


async def test_s45_t01_binary_source_without_storage_blocks_configuration(conn, user, monkeypatch):
    from app.connectors.base import DownloadRef
    from app.sync import intents
    from app.sync.processing import worker
    from app.sync.processing.storage import StorageError

    await sync(
        conn, user, [course(), material(download=DownloadRef(url="https://canvas.example/file"))]
    )
    row = await intent(conn, user)

    def unavailable():
        raise StorageError("missing local configuration")

    from app.core.embeddings import FakeEmbeddings

    monkeypatch.setattr(worker, "get_embeddings", lambda **options: FakeEmbeddings())

    def forbidden(*a):
        pytest.fail("binary download was reached without required Storage configuration")

    monkeypatch.setattr(worker, "http_downloader", forbidden)
    monkeypatch.setattr(worker, "get_storage", unavailable)
    assert await intents.execute(conn, **args(row)) == "blocked"
    current = await intent(conn, user)
    assert (
        current["blocked_reason"] == "configuration" and current["payload_ciphertext"] is not None
    )


async def test_s45_t05_stale_snapshot_cannot_reopen_a_new_stop_state(conn, user, monkeypatch):
    from contextlib import asynccontextmanager

    from app.sync import recovery

    await sync(conn, user, [course(), material(text=TEXT)])
    await conn.execute(
        "update processing_intents set dispatched_at=now()-interval '20 "
        "minutes',last_started_at=now()-interval '20 minutes',attempts=1 where user_id=%s",
        (user,),
    )

    @asynccontextmanager
    async def worker_finished(c, iid, **options):
        await c.execute(
            "update processing_intents set "
            "blocked_reason='configuration',dispatched_at=null where id=%s",
            (iid,),
        )
        yield True

    monkeypatch.setattr(recovery, "intent_lock", worker_finished)
    assert await recovery.recover_stalled(conn, user_id=user) == 0
    assert (await intent(conn, user))["blocked_reason"] == "configuration"


async def test_s45_t05_busy_intent_does_not_stall_other_recovery(conn, user):
    import asyncio

    from app.sync import recovery
    from tests.integration.db import open_conn

    await sync(
        conn,
        user,
        [course(), material(text=TEXT), material(text="second source", platform_id="f8")],
    )
    rows = await (
        await conn.execute(
            "select id from processing_intents where user_id=%s order by created_at,id", (user,)
        )
    ).fetchall()
    await conn.execute(
        "update processing_intents set dispatched_at=now()-interval '20 minutes' where user_id=%s",
        (user,),
    )
    key = f"index-work:{rows[0]['id']}"
    async with await open_conn() as held:
        await held.execute("select pg_advisory_lock(hashtextextended(%s,0))", (key,))
        try:
            assert await asyncio.wait_for(recovery.recover_stalled(conn, user_id=user), 0.5) == 1
        finally:
            await held.execute("select pg_advisory_unlock(hashtextextended(%s,0))", (key,))
    attempts = await (
        await conn.execute(
            "select attempts from processing_intents where user_id=%s order by created_at,id",
            (user,),
        )
    ).fetchall()
    assert [r["attempts"] for r in attempts] == [0, 1]


async def test_s45_t03_orphaned_replacement_dispatches_consume_budget(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    await sync(conn, user, [course(), material(text=TEXT)])
    original = await intent(conn, user)

    async def fail(*a):
        raise httpx.ReadTimeout("synthetic first processing failure")

    monkeypatch.setattr(worker, "run_process_material", fail)
    assert await intents.execute(conn, **args(original)) == "retry_scheduled"
    await conn.execute(
        "update processing_intents set last_started_at=now()-interval '20 minutes' "
        "where user_id=%s",
        (user,),
    )

    async def lost_delivery(a):
        pass  # queue acknowledged but the job vanished before the worker claimed it

    for _ in range(3):
        await conn.execute(
            "update processing_intents set next_attempt_at=now()-interval '1 second' "
            "where user_id=%s",
            (user,),
        )
        assert await intents.dispatch_pending(conn, user_id=user, defer=lost_delivery) == 1
        assert await intents.recover_stalled(conn, user_id=user) == 0
        await conn.execute(
            "update processing_intents set dispatched_at=now()-interval '20 minutes' "
            "where user_id=%s",
            (user,),
        )
        assert await intents.recover_stalled(conn, user_id=user) == 1
    row = await intent(conn, user)
    assert row["attempts"] == 4 and row["blocked_reason"] == "exhausted"
