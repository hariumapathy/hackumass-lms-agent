"""S48 synthetic two-session processing races. Worker paused; no real providers/platforms."""

import asyncio
from pathlib import Path

import pytest

from app.connectors.base import DownloadRef
from app.core.embeddings import FakeEmbeddings
from app.sync.processing import MaterialSource, process_material, process_post
from app.sync.processing.failures import ProcessingFailure
from app.sync.processing.storage import StorageError
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user, open_conn
from tests.integration.test_s12_processing_db import (
    FakeStorage,
    add_material,
    chunks,
    material_row,
    setup_course,
)

pytestmark = pytest.mark.integration
MIGRATION = (
    Path(__file__).resolve().parents[3] / "supabase/migrations/0007_processing_source_revision.sql"
)


@pytest.fixture
def migration_sql():
    return MIGRATION.read_text()


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):
    uid = await create_auth_user(conn)
    try:
        yield uid
    finally:
        await delete_auth_user(conn, uid)


class PausedEmbeddings(FakeEmbeddings):
    def __init__(self, entered, release, error=None):
        self.entered, self.release, self.error = entered, release, error

    async def embed(self, texts):
        self.entered.set()
        await self.release.wait()
        if self.error:
            raise self.error
        return await super().embed(texts)


async def text_process(conn, user, mid, text="old lesson", embeddings=None):
    return await process_material(
        conn,
        user,
        mid,
        source=MaterialSource(text=text),
        embeddings=embeddings or FakeEmbeddings(),
    )


@pytest.mark.parametrize("change", ["replace", "aba", "remove", "delete"])
async def test_s48_t01_t02_stale_material_cannot_publish(conn, user, change):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")
    entered, release = asyncio.Event(), asyncio.Event()
    async with await open_conn() as worker:
        task = asyncio.create_task(
            text_process(worker, user, mid, embeddings=PausedEmbeddings(entered, release))
        )
        try:
            await asyncio.wait_for(entered.wait(), 3)
            if change in {"replace", "aba"}:
                await conn.execute(
                    "update materials set content_hash='new',title='new' where id=%s", (mid,)
                )
                if change == "aba":
                    await conn.execute(
                        "update materials set content_hash='h',title='Lecture 7 slides' "
                        "where id=%s",
                        (mid,),
                    )
            elif change == "remove":
                await conn.execute("update materials set status='removed' where id=%s", (mid,))
            else:
                await conn.execute("delete from materials where id=%s", (mid,))
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    assert result == "superseded"
    assert not await chunks(conn, mid)
    if change != "delete":
        assert (await material_row(conn, mid))["processing_status"] != "done"


async def test_s48_t01_post_aba_does_not_publish_old_result(conn, user):
    cid = await setup_course(conn, user)
    pid = (
        await (
            await conn.execute(
                "insert into posts(user_id,course_id,kind,title,body,posted_at,"
                "platform,platform_id,"
                "source_url,content_hash) values (%s,%s,'announcement','Title','original',now(),"
                "'canvas','a1','https://example.edu/post','h') returning id",
                (user, cid),
            )
        ).fetchone()
    )["id"]
    entered, release = asyncio.Event(), asyncio.Event()
    async with await open_conn() as worker:
        task = asyncio.create_task(
            process_post(worker, user, pid, embeddings=PausedEmbeddings(entered, release))
        )
        try:
            await asyncio.wait_for(entered.wait(), 3)
            await conn.execute("update posts set body='changed' where id=%s", (pid,))
            await conn.execute("update posts set body='original' where id=%s", (pid,))
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    assert result == "superseded"
    assert not await chunks(conn, pid, "post_id")


async def test_s48_t04_same_parent_serializes_without_duplicate_current_chunks(conn, user):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")
    entered, release, second = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class Second(FakeEmbeddings):
        async def embed(self, texts):
            second.set()
            return await super().embed(texts)

    async with await open_conn() as a, await open_conn() as b:
        first = asyncio.create_task(
            text_process(a, user, mid, embeddings=PausedEmbeddings(entered, release))
        )
        await asyncio.wait_for(entered.wait(), 3)
        other = asyncio.create_task(text_process(b, user, mid, embeddings=Second()))
        try:
            await asyncio.sleep(0.05)
            assert not second.is_set()
        finally:
            release.set()
            results = await asyncio.wait_for(asyncio.gather(first, other), 5)
    assert sorted(results) == ["done", "unchanged"]
    assert len(await chunks(conn, mid)) == 1


async def test_s48_t05_late_timed_out_upload_cannot_overwrite_winning_bytes(conn, user):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")

    class LateStorage(FakeStorage):
        late = None

        async def upload(self, path, data, content_type):
            if self.late is None:
                self.late = (path, data)
                raise StorageError("synthetic ambiguous upload timeout")
            await super().upload(path, data, content_type)

    storage = LateStorage()

    async def attempt(text):
        async def download(ref):
            return text.encode()

        return await process_material(
            conn,
            user,
            mid,
            source=MaterialSource(
                download=DownloadRef(url="https://example.edu/f", filename="f.txt")
            ),
            embeddings=FakeEmbeddings(),
            downloader=download,
            storage=storage,
        )

    with pytest.raises(ProcessingFailure):
        await attempt("old bytes")
    await conn.execute("update materials set content_hash='new' where id=%s", (mid,))
    assert await attempt("new bytes") == "done"
    published = (await material_row(conn, mid))["storage_path"]
    assert storage.late is not None
    late_path, late_bytes = storage.late
    storage.files[late_path] = (
        late_bytes  # Remote side finishes after its original client timed out.
    )
    assert late_path != published
    assert storage.files[published] == b"new bytes"


async def test_s48_t06_embedding_failure_does_not_upload_candidate(conn, user):
    from tests.integration.test_s12_processing_db import FailingEmbeddings

    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")
    storage = FakeStorage()

    async def download(ref):
        return b"synthetic lesson"

    with pytest.raises(ProcessingFailure):
        await process_material(
            conn,
            user,
            mid,
            source=MaterialSource(download=DownloadRef(url="https://example.edu/f")),
            embeddings=FailingEmbeddings(),
            downloader=download,
            storage=storage,
        )
    assert not storage.files
    assert (await material_row(conn, mid))["storage_path"] is None


async def test_s48_t07_failure_cannot_poison_same_hash_replacement(conn, user):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")
    entered, release = asyncio.Event(), asyncio.Event()
    async with await open_conn() as worker:
        task = asyncio.create_task(
            text_process(
                worker,
                user,
                mid,
                embeddings=PausedEmbeddings(entered, release, TimeoutError("synthetic")),
            )
        )
        try:
            await asyncio.wait_for(entered.wait(), 3)
            await conn.execute("update materials set content_hash='new' where id=%s", (mid,))
            await conn.execute(
                "update materials set content_hash='h',processing_status='pending' where id=%s",
                (mid,),
            )
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    assert result == "superseded"
    assert (await material_row(conn, mid))["processing_status"] == "pending"


async def test_s48_t08_source_revision_is_private_and_not_freshness_or_outputs(conn, user):
    from app.db.models import Material

    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid)

    async def row():
        return await (await conn.execute("select * from materials where id=%s", (mid,))).fetchone()

    original = await row()
    assert "source_revision" in original
    await conn.execute(
        "update materials set last_synced_at=now(),processing_status='failed',"
        "version=2 where id=%s",
        (mid,),
    )
    assert (await row())["source_revision"] == original["source_revision"]
    await conn.execute(
        "update materials set source_url='https://example.edu/new' where id=%s", (mid,)
    )
    assert (await row())["source_revision"] != original["source_revision"]
    assert "source_revision" not in Material.model_validate(await row()).model_dump()


async def durable(conn, user, text):
    from tests.integration.test_s10_sync_db import course, material
    from tests.integration.test_s44_intents import sync

    await conn.execute(
        "insert into connections(user_id,platform) values (%s,'canvas') on conflict do nothing",
        (user,),
    )
    await sync(conn, user, [course(), material(text=text)])
    return await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()


def intent_args(row):
    return {
        "user_id": str(row["user_id"]),
        "intent_id": str(row["id"]),
        "revision": str(row["revision"]),
    }


async def test_s48_t03_queued_payload_does_not_adopt_raw_same_hash_revision(
    conn, user, monkeypatch
):
    from app.sync import intents
    from app.sync.processing import worker

    row = await durable(conn, user, "old queued payload")
    await conn.execute(
        "update materials set title='new raw source title' where id=%s", (row["material_id"],)
    )
    calls = []

    async def process(c, uid, mid, source):
        calls.append(True)
        return await process_material(
            c, uid, mid, source=MaterialSource.model_validate(source), embeddings=FakeEmbeddings()
        )

    monkeypatch.setattr(worker, "run_process_material", process)
    assert await intents.execute(conn, **intent_args(row)) == "unavailable"
    assert not calls and not await chunks(conn, row["material_id"])
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (row["id"],))
    ).fetchone()
    assert current["blocked_reason"] == "source_refresh" and current["payload_ciphertext"] is None


async def test_s48_t03_intent_rotation_during_embedding_does_not_complete_replacement(
    conn, user, monkeypatch
):
    from app.sync import intents
    from app.sync.processing import worker

    row = await durable(conn, user, "old durable lesson")
    entered, release = asyncio.Event(), asyncio.Event()

    async def process(c, uid, mid, source):
        return await process_material(
            c,
            uid,
            mid,
            source=MaterialSource.model_validate(source),
            embeddings=PausedEmbeddings(entered, release),
        )

    monkeypatch.setattr(worker, "run_process_material", process)
    async with await open_conn() as worker_conn:
        task = asyncio.create_task(intents.execute(worker_conn, **intent_args(row)))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            await conn.execute(
                "update processing_intents set revision=gen_random_uuid(),attempts=0 where id=%s",
                (row["id"],),
            )
            await conn.execute(
                "update materials set processing_status='pending' where id=%s",
                (row["material_id"],),
            )
        finally:
            release.set()
            result = await asyncio.wait_for(task, 5)
    assert result == "superseded"
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (row["id"],))
    ).fetchone()
    assert current["completed_at"] is None and current["attempts"] == 0
    assert not await chunks(conn, row["material_id"])
    assert (await material_row(conn, row["material_id"]))["processing_status"] == "pending"


async def test_s48_t03_source_changed_before_processor_entry_rejects_old_payload(
    conn, user, monkeypatch
):
    from app.sync import intents
    from app.sync.processing import worker

    row = await durable(conn, user, "old durable lesson")

    async def replaced(c, uid, mid, source):
        await durable(c, uid, "new durable lesson")
        return await process_material(
            c, uid, mid, source=MaterialSource.model_validate(source), embeddings=FakeEmbeddings()
        )

    monkeypatch.setattr(worker, "run_process_material", replaced)
    assert await intents.execute(conn, **intent_args(row)) == "superseded"
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (row["id"],))
    ).fetchone()
    assert current["revision"] != row["revision"] and current["completed_at"] is None
    assert current["attempts"] == 0 and current["blocked_reason"] is None
    assert not await chunks(conn, row["material_id"])


async def test_s48_t06_publication_and_completion_roll_back_together(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import process as module
    from app.sync.processing import worker

    async def process(c, uid, mid, source):
        return await process_material(
            c, uid, mid, source=MaterialSource.model_validate(source), embeddings=FakeEmbeddings()
        )

    monkeypatch.setattr(worker, "run_process_material", process)
    first = await durable(conn, user, "original durable lesson")
    assert await intents.execute(conn, **intent_args(first)) == "done"
    before = await chunks(conn, first["material_id"])
    old_version = (await material_row(conn, first["material_id"]))["version"]
    newer = await durable(conn, user, "new durable lesson")
    complete = module.complete

    async def fail_after_completion(c, work):
        await complete(c, work)
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(module, "complete", fail_after_completion)
    assert await intents.execute(conn, **intent_args(newer)) == "retry_scheduled"
    assert await chunks(conn, first["material_id"]) == before
    assert (await material_row(conn, first["material_id"]))["version"] == old_version
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (newer["id"],))
    ).fetchone()
    assert current["completed_at"] is None and current["payload_ciphertext"] is not None


async def test_s48_t07_stale_unchanged_branch_cannot_mark_replacement_done(conn, user, monkeypatch):
    from app.sync.processing import process as module

    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")
    assert await text_process(conn, user, mid) == "done"
    original = module._current_texts

    async def replace_before_noop(c, uid, col, parent):
        texts = await original(c, uid, col, parent)
        await c.execute(
            "update materials set content_hash='new',processing_status='pending' where id=%s",
            (mid,),
        )
        return texts

    monkeypatch.setattr(module, "_current_texts", replace_before_noop)
    assert await text_process(conn, user, mid) == "superseded"
    assert (await material_row(conn, mid))["processing_status"] == "pending"


async def test_s48_t07_legacy_task_ignores_old_payload_and_requests_current_work(
    conn, user, monkeypatch
):
    from app.sync import jobs

    calls = []

    async def deliver(uid, mid, source):
        calls.append((uid, mid, source))

    monkeypatch.setattr(jobs, "_defer_process_material", deliver)
    from uuid import uuid4

    mid = uuid4()
    await jobs.process_material(str(user), str(mid), {"text": "untrusted stale envelope"})
    assert calls == [(user, mid, {})]


async def test_s48_t02_other_parent_proceeds_and_foreign_owner_is_denied(conn, user):
    cid = await setup_course(conn, user)
    first = await add_material(conn, user, cid, mime="text/plain")
    second = await add_material(conn, user, cid, mime="text/plain", pid="f8")
    entered, release = asyncio.Event(), asyncio.Event()
    foreign = await create_auth_user(conn)
    try:
        assert await text_process(conn, foreign, first) == "missing"
        async with await open_conn() as worker:
            task = asyncio.create_task(
                text_process(worker, user, first, embeddings=PausedEmbeddings(entered, release))
            )
            try:
                await asyncio.wait_for(entered.wait(), 3)
                assert await asyncio.wait_for(text_process(conn, user, second), 3) == "done"
            finally:
                release.set()
                await asyncio.wait_for(task, 5)
    finally:
        await delete_auth_user(conn, foreign)


async def test_s48_t04_canceled_parent_waiter_releases_user_and_session_locks(conn, user):
    from uuid import uuid4

    from app.sync.processing.publication import parent_work

    mid = uuid4()
    async with await open_conn() as holder, await open_conn() as waiter:
        async with parent_work(holder, user, mid, "materials"):
            entered = asyncio.Event()

            async def wait():
                entered.set()
                async with parent_work(waiter, user, mid, "materials"):
                    pytest.fail("must not enter held parent lock")

            task = asyncio.create_task(wait())
            await entered.wait()
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert waiter.closed
    async with asyncio.timeout(3):
        async with parent_work(conn, user, mid, "materials"):
            pass


async def test_s48_t05_source_changes_during_upload_never_publishes_candidate(conn, user):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")

    class ReplacedUpload(FakeStorage):
        async def upload(self, path, data, content_type):
            await super().upload(path, data, content_type)
            await conn.execute(
                "update materials set content_hash='new',processing_status='pending' where id=%s",
                (mid,),
            )

    storage = ReplacedUpload()

    async def download(ref):
        return b"synthetic original"

    assert (
        await process_material(
            conn,
            user,
            mid,
            source=MaterialSource(download=DownloadRef(url="https://example.edu/file")),
            embeddings=FakeEmbeddings(),
            downloader=download,
            storage=storage,
        )
        == "superseded"
    )
    assert len(storage.files) == 1  # Unreferenced candidate; reconciliation is a separate gate.
    row = await material_row(conn, mid)
    assert row["storage_path"] is None and row["processing_status"] == "pending"
    assert not await chunks(conn, mid)


async def test_s48_t07_stale_empty_download_cannot_mark_replacement_skipped(conn, user):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")

    async def empty_after_replacement(ref):
        await conn.execute(
            "update materials set content_hash='new',processing_status='pending' where id=%s",
            (mid,),
        )
        return b""

    assert (
        await process_material(
            conn,
            user,
            mid,
            source=MaterialSource(download=DownloadRef(url="https://example.edu/file")),
            embeddings=FakeEmbeddings(),
            downloader=empty_after_replacement,
            storage=FakeStorage(),
        )
        == "superseded"
    )
    assert (await material_row(conn, mid))["processing_status"] == "pending"


@pytest.mark.parametrize("stale_before_merge", [False, True])
async def test_s48_t08_course_merge_rebinds_only_previously_matching_intents(
    conn, user, stale_before_merge
):
    from app.sync.merge import CourseRow, _Merger
    from tests.integration.test_s10_sync_db import NOW

    intent = await durable(conn, user, "same source content")
    material = await (
        await conn.execute("select * from materials where id=%s", (intent["material_id"],))
    ).fetchone()
    old_course = material["course_id"]
    keep = (
        await (
            await conn.execute(
                "insert into courses(user_id,name,code) values (%s,'Canonical','COMPSCI 311') "
                "returning id",
                (user,),
            )
        ).fetchone()
    )["id"]
    await conn.execute(
        "update processing_intents set attempts=2,blocked_reason='configuration' where id=%s",
        (intent["id"],),
    )
    if stale_before_merge:
        await conn.execute(
            "update materials set title='unobserved raw change' where id=%s",
            (intent["material_id"],),
        )
    async with conn.transaction():
        await _Merger(conn, user, NOW).absorb_course(
            CourseRow(old_course, "COMPSCI 311", None, frozenset({"canvas"}), NOW),
            CourseRow(keep, "COMPSCI 311", None, frozenset(), NOW),
        )
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (intent["id"],))
    ).fetchone()
    parent = await (
        await conn.execute("select * from materials where id=%s", (intent["material_id"],))
    ).fetchone()
    assert current["attempts"] == 2 and current["blocked_reason"] == "configuration"
    assert parent["course_id"] == keep
    if stale_before_merge:
        assert current["revision"] == intent["revision"]
        assert current["parent_source_revision"] != parent["source_revision"]
    else:
        assert current["revision"] != intent["revision"]
        assert current["parent_source_revision"] == parent["source_revision"]


async def test_s48_t03_post_mismatch_rebuilds_from_owned_current_db_text(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker
    from tests.integration.test_s10_sync_db import course, post
    from tests.integration.test_s44_intents import sync

    await conn.execute("insert into connections(user_id,platform) values (%s,'canvas')", (user,))
    await sync(conn, user, [course(), post()])
    row = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()
    await conn.execute("update posts set body='fresh owned body' where id=%s", (row["post_id"],))
    assert await intents.execute(conn, **intent_args(row)) == "unavailable"
    newer = await (
        await conn.execute("select * from processing_intents where id=%s", (row["id"],))
    ).fetchone()

    async def process(c, uid, pid):
        return await process_post(c, uid, pid, embeddings=FakeEmbeddings())

    monkeypatch.setattr(worker, "run_process_post", process)
    assert await intents.execute(conn, **intent_args(newer)) == "done"
    assert "fresh owned body" in (await chunks(conn, row["post_id"], "post_id"))[0]["text"]


async def test_s48_t03_trusted_observation_recovers_stale_material_payload(conn, user, monkeypatch):
    from app.sync import intents
    from app.sync.processing import worker

    row = await durable(conn, user, "observed source")
    await conn.execute(
        "update materials set title='unobserved title' where id=%s", (row["material_id"],)
    )
    assert await intents.execute(conn, **intent_args(row)) == "unavailable"
    fresh = await durable(conn, user, "observed source")
    assert fresh["blocked_reason"] is None and fresh["payload_ciphertext"] is not None

    async def process(c, uid, mid, source):
        return await process_material(
            c, uid, mid, source=MaterialSource.model_validate(source), embeddings=FakeEmbeddings()
        )

    monkeypatch.setattr(worker, "run_process_material", process)
    assert await intents.execute(conn, **intent_args(fresh)) == "done"


async def test_s48_t03_refresh_placeholder_recovers_even_if_previous_status_done(conn, user):
    from uuid import uuid4

    from app.db.repositories import sync as connections
    from app.sync.recovery import recover_legacy_materials

    row = await durable(conn, user, "needs source metadata")
    await connections.upsert_connection_secret(conn, user, "canvas", b"synthetic", "canvas_token")
    await conn.execute(
        "update processing_intents set blocked_reason='source_refresh',payload_ciphertext=null "
        "where id=%s",
        (row["id"],),
    )
    await conn.execute(
        "update materials set processing_status='done' where id=%s", (row["material_id"],)
    )
    calls = []

    async def enqueue(*args):
        calls.append(True)
        return uuid4()

    assert await recover_legacy_materials(conn, user_id=user, enqueue=enqueue) == 1
    assert calls == [True]


async def test_s48_t08_migration_retires_unproven_payloads_preserving_stop_policy(
    conn, user, migration_sql
):
    from psycopg.sql import SQL

    cid = await setup_course(conn, user)
    states = [
        (None, 2),
        ("configuration", 2),
        ("permanent", 2),
        ("exhausted", 2),
        ("source_auth", 2),
        (None, 4),
    ]
    ids = []
    for n, (state, attempts) in enumerate(states):
        mid = await add_material(conn, user, cid, pid=f"migration-{n}")
        row = await (
            await conn.execute(
                "insert into processing_intents(user_id,material_id,source_hash,payload_ciphertext,"
                "blocked_reason,attempts) values (%s,%s,'h','unproven'::bytea,%s,%s) "
                "returning id,revision",
                (user, mid, state, attempts),
            )
        ).fetchone()
        ids.append(row)
    sql = migration_sql.split("-- Pending material payloads", 1)[1].split(
        "update public.processing_intents", 1
    )[1]
    sql = "update public.processing_intents" + sql.split(";", 1)[0]
    # Exercise the actual migration update, scoped to this fixture owner's rows only.
    sql = sql.replace(
        "where material_id is not null", "where user_id=%s and material_id is not null"
    )
    await conn.execute(SQL(sql), (user,))
    for original, (state, attempts) in zip(ids, states, strict=True):
        row = await (
            await conn.execute("select * from processing_intents where id=%s", (original["id"],))
        ).fetchone()
        assert row["blocked_reason"] == (
            state or ("exhausted" if attempts >= 4 else "source_refresh")
        )
        assert row["attempts"] == attempts and row["payload_ciphertext"] is None
        assert row["revision"] != original["revision"]


async def test_s48_t08_reconnect_payload_free_auth_work_requires_source_refresh(conn, user):
    from app.db.repositories import sync as connections

    row = await durable(conn, user, "source metadata missing")
    await conn.execute(
        "update processing_intents set payload_ciphertext=null,blocked_reason='source_auth' "
        "where id=%s",
        (row["id"],),
    )
    await connections.upsert_connection_secret(conn, user, "canvas", b"synthetic", "canvas_token")
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (row["id"],))
    ).fetchone()
    assert current["blocked_reason"] == "source_refresh"


@pytest.mark.parametrize("reason", ["configuration", "permanent", "exhausted", "source_auth"])
async def test_s48_t08_unchanged_observation_preserves_retired_payload_stop_policy(
    conn, user, reason
):
    row = await durable(conn, user, "unchanged source")
    await conn.execute(
        "update processing_intents set payload_ciphertext=null,blocked_reason=%s,"
        "last_error_code='processing_failed',attempts=4 where id=%s",
        (reason, row["id"]),
    )
    fresh = await durable(conn, user, "unchanged source")
    assert fresh["blocked_reason"] == reason and fresh["attempts"] == 4
    assert fresh["revision"] == row["revision"]


@pytest.mark.parametrize("kind", ["material", "post"])
async def test_s48_t07_factory_failure_cannot_poison_new_parent_generation(
    conn, user, monkeypatch, kind
):
    from app.sync import intents
    from app.sync.processing import worker
    from tests.integration.test_s10_sync_db import course, post
    from tests.integration.test_s44_intents import sync

    if kind == "material":
        row = await durable(conn, user, "original")
    else:
        await conn.execute(
            "insert into connections(user_id,platform) values (%s,'canvas')", (user,)
        )
        await sync(conn, user, [course(), post()])
        row = await (
            await conn.execute("select * from processing_intents where user_id=%s", (user,))
        ).fetchone()

    async def factory_failure(c, uid, parent, *args):
        if kind == "material":
            await c.execute(
                "update materials set title='new raw source',processing_status='pending' "
                "where id=%s",
                (parent,),
            )
        else:
            await c.execute("update posts set body='new raw source' where id=%s", (parent,))
        raise ProcessingFailure("configuration", "synthetic_factory_failure")

    monkeypatch.setattr(
        worker,
        "run_process_material" if kind == "material" else "run_process_post",
        factory_failure,
    )
    assert await intents.execute(conn, **intent_args(row)) == "superseded"
    current = await (
        await conn.execute("select * from processing_intents where id=%s", (row["id"],))
    ).fetchone()
    assert current["blocked_reason"] is None and current["dispatched_at"] is None
    if kind == "material":
        assert (await material_row(conn, row["material_id"]))["processing_status"] == "pending"


async def test_s48_t06_new_inline_content_does_not_point_to_old_binary(conn, user):
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid, mime="text/plain")
    storage = FakeStorage()

    async def download(ref):
        return b"old binary original"

    assert (
        await process_material(
            conn,
            user,
            mid,
            source=MaterialSource(download=DownloadRef(url="https://example.edu/f")),
            embeddings=FakeEmbeddings(),
            downloader=download,
            storage=storage,
        )
        == "done"
    )
    old_path = (await material_row(conn, mid))["storage_path"]
    await conn.execute("update materials set content_hash='inline replacement' where id=%s", (mid,))
    assert await text_process(conn, user, mid, text="new inline replacement") == "done"
    assert (await material_row(conn, mid))["storage_path"] is None
    assert old_path in storage.files


async def test_s48_t08_post_cutover_exhausted_attempt_remains_operator_recoverable(
    conn, user, migration_sql
):
    from psycopg.sql import SQL

    from app.db.repositories import processing
    from tests.integration.test_s10_sync_db import course, post
    from tests.integration.test_s44_intents import sync

    await conn.execute("insert into connections(user_id,platform) values (%s,'canvas')", (user,))
    await sync(conn, user, [course(), post()])
    await conn.execute(
        "update processing_intents set attempts=4,blocked_reason=null where user_id=%s", (user,)
    )
    sql = migration_sql.split("-- Posts read current owned DB text;", 1)[1]
    sql = (
        "update public.processing_intents"
        + sql.split("update public.processing_intents", 1)[1].split(";", 1)[0]
    )
    sql += " and i.user_id=%s"
    await conn.execute(SQL(sql), (user,))
    row = await (
        await conn.execute("select * from processing_intents where user_id=%s", (user,))
    ).fetchone()
    assert row["blocked_reason"] == "exhausted" and row["attempts"] == 4
    assert await processing.resume(conn, user) == 1
