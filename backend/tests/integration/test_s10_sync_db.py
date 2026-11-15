# pyright: reportArgumentType=false, reportIndexIssue=false, reportCallIssue=false, reportOptionalSubscript=false
"""S10 sync framework: integration tests against the local DB with a fake connector."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from procrastinate import PsycopgConnector

from app.connectors.base import (
    AccountInfo,
    AuthExpired,
    ConnectorContext,
    NCourse,
    NItem,
    NMaterial,
    NormalizedRecord,
    NPost,
    PlatformError,
    SyncScope,
)
from app.core.clock import FixedClock
from app.core.settings import get_settings
from app.db.repositories import sync as repo
from app.sync import jobs
from app.sync.merge import merge_one_to_one
from app.sync.pipeline import run_sync
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)
C = "https://example.instructure.com/courses/12345"


class FakeConnector:
    platform = "canvas"

    def __init__(self, records: list[Any], error: Exception | None = None) -> None:
        self.records, self.error, self.calls = records, error, 0

    async def validate(self, ctx: ConnectorContext) -> AccountInfo:
        return AccountInfo(account_label="Test")

    async def fetch(
        self, ctx: ConnectorContext, scope: SyncScope
    ) -> AsyncIterator[NormalizedRecord]:
        self.calls += 1
        for r in self.records:
            yield r
        if self.error:
            raise self.error


def course() -> NCourse:
    return NCourse(
        platform_id="12345",
        name="Intro to Algorithms",
        code="COMPSCI 311",
        term="Fall 2026",
        source_url=C,
    )


def item(**kw: Any) -> NItem:
    base: dict[str, Any] = dict(
        platform_id="99812",
        course_platform_id="12345",
        type="exam",
        title="Midterm 1",
        due_at=NOW + timedelta(days=4),
        points=100,
        source_url=f"{C}/assignments/99812",
    )
    return NItem(**{**base, **kw})


def material(**kw: Any) -> NMaterial:
    base: dict[str, Any] = dict(
        platform_id="f7",
        course_platform_id="12345",
        kind="file",
        title="Lecture 7 slides",
        mime_type="application/pdf",
        source_url=f"{C}/files/7",
        source_updated_at=NOW - timedelta(days=2),
    )
    return NMaterial(**{**base, **kw})


def post() -> NPost:
    return NPost(
        platform_id="a1",
        course_platform_id="12345",
        kind="announcement",
        title="Welcome",
        body="Hi",
        posted_at=NOW - timedelta(days=1),
        source_url=f"{C}/discussion_topics/a1",
    )


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    await conn.execute("insert into connections (user_id, platform) values (%s, 'canvas')", (uid,))
    yield uid
    await delete_auth_user(conn, uid)


async def _sync(
    conn: Any, uid: UUID, connector: Any, scope: SyncScope | None = None, **kw: Any
) -> Any:
    scope = scope or SyncScope()
    run_id = await repo.create_run(
        conn, uid, "canvas", scope.model_dump(mode="json"), "manual", NOW
    )
    out = await run_sync(
        conn,
        user_id=uid,
        run_id=run_id,
        scope=scope,
        connector=connector,
        secret="tok",
        clock=FixedClock(NOW),
        **kw,
    )
    return out, run_id


async def _count(conn: Any, sql: str, *params: Any) -> int:
    cur = await conn.execute(f"select count(*) as n from {sql}", params)  # noqa: S608
    row = await cur.fetchone()
    return row["n"]


async def test_s10_fake_connector_end_to_end_then_rerun_unchanged(conn, user) -> None:  # noqa: ANN001
    recs = [course(), item(), material(), post()]
    out, run_id = await _sync(conn, user, FakeConnector(recs))
    assert out.status == "succeeded"
    assert out.stats == {"new": 4, "changed": 0, "unchanged": 0, "removed": 0}
    run = await repo.get_run(conn, user, run_id)
    assert run and run.status == "succeeded" and run.finished_at is not None
    assert await _count(conn, "courses where user_id = %s and code = 'COMPSCI 311'", user) == 1
    out2, _ = await _sync(conn, user, FakeConnector(recs))
    assert out2.stats == {"new": 0, "changed": 0, "unchanged": 4, "removed": 0}
    cx = await repo.get_connection(conn, user, "canvas")
    assert cx and cx.status == "active" and cx.last_sync_at == NOW


async def test_s10_t03_changed_due_at_writes_one_change_row(conn, user) -> None:  # noqa: ANN001
    await _sync(conn, user, FakeConnector([course(), item()]))
    await merge_one_to_one(conn, user)
    moved = NOW + timedelta(days=6)
    out, _ = await _sync(conn, user, FakeConnector([course(), item(due_at=moved)]))
    assert out.stats["changed"] == 1
    cur = await conn.execute(
        "select field, old_value, new_value, entity_type, entity_id from changes "
        "where user_id = %s",
        (user,),
    )
    rows = await cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["field"] == "due_at" and rows[0]["entity_type"] == "item"
    assert rows[0]["old_value"] == (NOW + timedelta(days=4)).isoformat()
    assert rows[0]["new_value"] == moved.isoformat()
    # Change points at the canonical item, which follows its source after merge.
    await merge_one_to_one(conn, user)
    cur = await conn.execute("select id, due_at from items where user_id = %s", (user,))
    it = await cur.fetchone()
    assert it["id"] == rows[0]["entity_id"] and it["due_at"] == moved


async def test_s10_t04_full_scope_removes_unseen_narrow_never(conn, user) -> None:  # noqa: ANN001
    await _sync(conn, user, FakeConnector([course(), item(), post()]))
    narrow = SyncScope(kind="course", course_platform_id="12345")
    out, _ = await _sync(conn, user, FakeConnector([course()]), scope=narrow)
    assert out.stats["removed"] == 0
    assert await _count(conn, "posts where user_id = %s and status = 'removed'", user) == 0
    out, _ = await _sync(conn, user, FakeConnector([course(), item()]))
    assert out.stats["removed"] == 1
    assert await _count(conn, "posts where user_id = %s and status = 'removed'", user) == 1
    assert await _count(conn, "changes where user_id = %s and field = 'status'", user) == 1


async def test_s10_t05_duplicate_enqueue_returns_same_run(conn, user) -> None:  # noqa: ANN001
    deferred: list[Any] = []

    async def fake_defer(job: Any, priority: int) -> None:
        deferred.append((job, priority))

    scope = SyncScope(kind="course", course_platform_id="12345")
    a = await jobs.enqueue_sync(conn, user, "canvas", scope, "agent", defer=fake_defer)
    b = await jobs.enqueue_sync(conn, user, "canvas", scope, "agent", defer=fake_defer)
    c = await jobs.enqueue_sync(conn, user, "canvas", SyncScope(), "schedule", defer=fake_defer)
    assert a == b and a != c
    assert len(deferred) == 2
    assert deferred[0][1] > deferred[1][1]  # agent priority > schedule priority


async def test_s10_t06_agent_job_runs_before_queued_schedule_job(conn, user) -> None:  # noqa: ANN001
    jobs.app.replace_connector(PsycopgConnector(conninfo=get_settings().database_url))
    async with jobs.app.open_async():
        await conn.execute("delete from procrastinate_jobs where queue_name = 'sync'")
        sched = await jobs.enqueue_sync(conn, user, "canvas", SyncScope(), "schedule")
        agent = await jobs.enqueue_sync(
            conn, user, "canvas", SyncScope(kind="course", course_platform_id="12345"), "agent"
        )
        job = await jobs.app.job_manager.fetch_job(queues=["sync"], worker_id=None)
        assert job is not None
        assert job.task_kwargs["job"]["sync_run_id"] == str(agent)
        assert sched != agent
        await conn.execute("delete from procrastinate_jobs where queue_name = 'sync'")


async def test_s10_t07_auth_expired_needs_reconnect_no_retry(conn, user) -> None:  # noqa: ANN001
    out, run_id = await _sync(
        conn, user, FakeConnector([course()], AuthExpired()), final_attempt=False
    )
    assert out.status == "needs_reconnect"
    run = await repo.get_run(conn, user, run_id)
    cx = await repo.get_connection(conn, user, "canvas")
    assert run and run.status == "needs_reconnect"
    assert cx and cx.status == "needs_reconnect" and cx.last_error


async def test_s10_t08_platform_error_retries_then_fails(conn, user) -> None:  # noqa: ANN001
    connector = FakeConnector([], PlatformError("503"))
    run_id = await repo.create_run(conn, user, "canvas", {"kind": "full"}, "manual", NOW)
    statuses = []
    for attempt in range(jobs.MAX_RETRIES + 1):
        out = await run_sync(
            conn,
            user_id=user,
            run_id=run_id,
            scope=SyncScope(),
            connector=connector,
            secret="t",
            clock=FixedClock(NOW),
            final_attempt=attempt >= jobs.MAX_RETRIES,
        )
        statuses.append(out.status)
    assert statuses == ["retry", "retry", "failed"]
    assert connector.calls == 3
    run = await repo.get_run(conn, user, run_id)
    assert run and run.status == "failed"


async def test_s10_t09_wait_for_sync_times_out_cleanly(conn, user) -> None:  # noqa: ANN001
    run_id = await repo.create_run(conn, user, "canvas", {"kind": "full"}, "agent", NOW)
    await repo.mark_run(conn, user, run_id, "running", NOW)
    slept: list[float] = []

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    res = await jobs.wait_for_sync(conn, user, run_id, timeout_s=2, poll_s=0.5, sleep=fake_sleep)
    assert res.timed_out and res.status == "running" and sum(slept) == 2
    await repo.mark_run(conn, user, run_id, "succeeded", NOW, {"new": 1})
    res = await jobs.wait_for_sync(conn, user, run_id, sleep=fake_sleep)
    assert not res.timed_out and res.status == "succeeded" and res.stats["new"] == 1


async def test_s10_t11_one_malformed_record_is_skipped(conn, user) -> None:  # noqa: ANN001
    bad = item(platform_id="bad")
    bad.__dict__["raw"] = {"oops": object()}  # bypass validation: can't be stored as JSON
    out, run_id = await _sync(conn, user, FakeConnector([course(), bad, item()]))
    assert out.status == "succeeded" and out.skipped == 1 and out.stats["new"] == 2
    run = await repo.get_run(conn, user, run_id)
    assert run and run.status == "succeeded"


async def test_s10_t12_new_or_changed_material_queues_processing(conn, user) -> None:  # noqa: ANN001
    queued: list[UUID] = []

    async def pm(uid: UUID, material_id: UUID, source: dict) -> None:
        queued.append(material_id)

    await _sync(conn, user, FakeConnector([course(), material()]), process_material=pm)
    assert len(queued) == 1
    await _sync(conn, user, FakeConnector([course(), material()]), process_material=pm)
    assert len(queued) == 1  # unchanged -> not requeued
    newer = material(source_updated_at=NOW)
    await _sync(conn, user, FakeConnector([course(), newer]), process_material=pm)
    assert len(queued) == 2


async def test_s10_secret_stored_encrypted_and_scheduler_finds_due(conn, user) -> None:  # noqa: ANN001
    await repo.upsert_connection_secret(conn, user, "canvas", b"ciphertext", "canvas_token")
    assert await repo.get_secret(conn, user, "canvas") == b"ciphertext"
    due = await jobs.due_connections(conn, NOW)
    assert (user, "canvas") in due
    run_id = await repo.create_run(conn, user, "canvas", {"kind": "full"}, "schedule", NOW)
    await repo.mark_run(conn, user, run_id, "succeeded", NOW - timedelta(minutes=5))
    assert (user, "canvas") not in await jobs.due_connections(conn, NOW)
    assert (user, "canvas") in await jobs.due_connections(conn, NOW + timedelta(minutes=30))


class WindowedConnector(FakeConnector):
    """Like Canvas: posts are listed for a time window only, so unseen posts aren't removed."""

    async def fetch(
        self, ctx: ConnectorContext, scope: SyncScope
    ) -> AsyncIterator[NormalizedRecord]:
        ctx.incomplete.add(("12345", "posts"))
        async for r in super().fetch(ctx, scope):
            yield r


async def test_s10_t04b_incomplete_listing_is_never_removed(conn, user) -> None:  # noqa: ANN001
    await _sync(conn, user, FakeConnector([course(), item(), post()]))
    out, _ = await _sync(conn, user, WindowedConnector([course()]))
    assert await _count(conn, "posts where user_id = %s and status = 'removed'", user) == 0
    assert out.stats["removed"] == 1  # the unseen item is still removed (its listing was complete)
