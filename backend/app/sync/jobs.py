"""Job queue (S10): Procrastinate app, tasks, enqueue_sync / wait_for_sync, periodic schedule.

Run the worker with `uv run app worker` (`make worker`). Queues: `sync` (platform syncs, merge)
and `process` (S12 file processing).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from procrastinate import App, JobContext, PsycopgConnector, RetryStrategy
from procrastinate.exceptions import AlreadyEnqueued
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.connectors.base import PlatformError, SyncScope, get_connector
from app.core.clock import Clock, SystemClock
from app.core.crypto import CryptoError, decrypt, get_fernet
from app.core.settings import get_settings
from app.db.deletion import generation, retry_pending_deletions, user_work
from app.db.repositories import sync as repo
from app.sync.pipeline import run_sync

log = logging.getLogger("app.sync")

MAX_RETRIES = 2  # S10 rule 7: PlatformError -> 2 retries with backoff
PRIORITY = {"agent": 10, "manual": 10, "connect": 0, "schedule": 0}  # S10 rule 2
INTERVAL = {  # S10 rule 3
    "canvas": timedelta(minutes=20),
    "gradescope": timedelta(minutes=60),
    "echo360": timedelta(days=1),
    "piazza": timedelta(minutes=60),
}

app = App(connector=PsycopgConnector(conninfo=get_settings().database_url))


class SyncJob(BaseModel):
    user_id: UUID
    platform: str
    scope: SyncScope
    trigger: str
    sync_run_id: UUID


class SyncRunResult(BaseModel):
    sync_run_id: UUID
    status: str
    stats: dict[str, int] = {}
    error: str | None = None
    timed_out: bool = False


async def _connect() -> AsyncConnection[Any]:
    return await psycopg.AsyncConnection.connect(
        get_settings().database_url,
        autocommit=True,
        row_factory=dict_row,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------------------------
@app.task(
    name="sync_platform",
    queue="sync",
    pass_context=True,
    retry=RetryStrategy(
        max_attempts=MAX_RETRIES, exponential_wait=5, retry_exceptions={PlatformError}
    ),
)
async def sync_platform(context: JobContext, job: dict[str, Any]) -> None:
    sj = SyncJob.model_validate(job)
    attempts = context.job.attempts if context.job else 0
    async with await _connect() as conn:
        async with user_work(conn, sj.user_id):
            await execute_sync(conn, sj, final_attempt=attempts >= MAX_RETRIES)


async def execute_sync(
    conn: AsyncConnection[Any], sj: SyncJob, *, final_attempt: bool, clock: Clock | None = None
) -> str:
    """Decrypt the secret, run the pipeline, queue follow-up jobs. Raises PlatformError to retry."""
    clock = clock or SystemClock()
    if await repo.get_run(conn, sj.user_id, sj.sync_run_id) is None:
        return "deleted"
    epoch = await generation(conn, sj.user_id)
    ciphertext = await repo.get_secret(conn, sj.user_id, sj.platform)
    if ciphertext is None:
        await repo.mark_run(
            conn, sj.user_id, sj.sync_run_id, "failed", clock.now(), error="Not connected."
        )
        return "failed"
    try:
        secret = decrypt(ciphertext, get_fernet())
    except CryptoError:
        message = "Please reconnect this account so we can update your classes."
        await repo.set_connection_status(
            conn, sj.user_id, sj.platform, "needs_reconnect", error=message
        )
        await repo.mark_run(
            conn, sj.user_id, sj.sync_run_id, "needs_reconnect", clock.now(), error=message
        )
        return "needs_reconnect"
    outcome = await run_sync(
        conn,
        user_id=sj.user_id,
        run_id=sj.sync_run_id,
        scope=sj.scope,
        connector=get_connector(sj.platform),
        secret=secret,
        clock=clock,
        final_attempt=final_attempt,
        process_material=_defer_process_material,
        process_post=_defer_process_post,
    )
    if outcome.status == "retry":
        raise PlatformError(outcome.error or "platform error")
    if outcome.status == "succeeded":
        await _defer(
            merge_user,
            {"user_id": str(sj.user_id), "expected_generation": epoch},
            lock=f"merge:{sj.user_id}",
            priority=PRIORITY["manual"],
        )
    return outcome.status


@app.task(
    name="process_material",
    queue="process",
    retry=RetryStrategy(
        max_attempts=MAX_RETRIES, exponential_wait=5, retry_exceptions={PlatformError}
    ),
)
async def process_material(
    user_id: str, material_id: str, source: dict[str, Any] | None = None
) -> None:
    """S12: download/extract/chunk/embed (`app.sync.processing`). `source` = download/text/cues."""
    from app.sync.processing.worker import run_process_material

    async with await _connect() as conn:
        async with user_work(conn, UUID(user_id)):
            await run_process_material(conn, UUID(user_id), UUID(material_id), source)


@app.task(
    name="process_post",
    queue="process",
    retry=RetryStrategy(
        max_attempts=MAX_RETRIES,
        exponential_wait=5,
        retry_exceptions={PlatformError},
    ),
)
async def process_post(user_id: str, post_id: str) -> None:
    """S12: chunk + embed a new/changed post (announcement, Piazza, email)."""
    from app.sync.processing.worker import run_process_post

    async with await _connect() as conn:
        async with user_work(conn, UUID(user_id)):
            await run_process_post(conn, UUID(user_id), UUID(post_id))


@app.task(name="merge_user", queue="sync")
async def merge_user(user_id: str, expected_generation: int = 0) -> None:
    """S16: merge courses/items across platforms and write canonical item changes."""
    from app.sync import merge

    async with await _connect() as conn:
        async with user_work(conn, UUID(user_id)) as epoch:
            if epoch != expected_generation:
                return
            stats = await merge.merge_user(conn, UUID(user_id))
    log.info("merge_user %s: %s", user_id, stats.model_dump())


async def _defer(task: Any, kwargs: dict[str, Any], lock: str | None = None, priority: int = 0):
    try:
        await task.configure(queueing_lock=lock, priority=priority).defer_async(**kwargs)
    except AlreadyEnqueued:
        pass


async def _defer_process_material(user_id: UUID, material_id: UUID, source: dict[str, Any]) -> None:
    from app.sync.intents import dispatch_parent

    async with await _connect() as conn:
        await dispatch_parent(conn, user_id, material_id=material_id)


async def _defer_process_post(user_id: UUID, post_id: UUID) -> None:
    from app.sync.intents import dispatch_parent

    async with await _connect() as conn:
        await dispatch_parent(conn, user_id, post_id=post_id)


@app.task(name="process_intent", queue="process")
async def process_intent(user_id: str, intent_id: str, revision: str) -> None:
    from app.sync.intents import execute

    async with await _connect() as conn:
        await execute(conn, user_id=user_id, intent_id=intent_id, revision=revision)


# ---------------------------------------------------------------------------------------------
# Enqueue / wait (used by POST /sync, connect flows, and the fetch_latest tool)
# ---------------------------------------------------------------------------------------------
Defer = Callable[[SyncJob, int], Awaitable[None]]


async def _defer_sync(job: SyncJob, priority: int) -> None:
    await sync_platform.configure(priority=priority).defer_async(job=job.model_dump(mode="json"))


async def enqueue_sync(
    conn: AsyncConnection[Any],
    user_id: UUID,
    platform: str,
    scope: SyncScope,
    trigger: str,
    *,
    clock: Clock | None = None,
    defer: Defer | None = None,
) -> UUID:
    """Queue a sync and return its `sync_run_id`. S10 rule 1: an identical queued/running job
    (same user, platform, scope) returns the existing run instead of adding another."""
    clock = clock or SystemClock()
    scope_json = scope.model_dump(mode="json")
    async with conn.transaction():
        await conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"sync:{user_id}:{platform}:{scope.key()}",),
        )
        existing = await repo.find_open_run(conn, user_id, platform, scope_json)
        if existing:
            return existing.id
        run_id = await repo.create_run(conn, user_id, platform, scope_json, trigger, clock.now())
    job = SyncJob(
        user_id=user_id, platform=platform, scope=scope, trigger=trigger, sync_run_id=run_id
    )
    try:
        await (defer or _defer_sync)(job, PRIORITY.get(trigger, 0))
    except Exception:
        await repo.mark_run(
            conn, user_id, run_id, "failed", clock.now(), error="Could not queue the sync."
        )
        raise
    return run_id


async def wait_for_sync(
    conn: AsyncConnection[Any],
    user_id: UUID,
    sync_run_id: UUID,
    timeout_s: float = 15,
    poll_s: float = 0.5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> SyncRunResult:
    """Poll until the run finishes or `timeout_s` passes (then `timed_out=True`, current status)."""
    waited = 0.0
    while True:
        run = await repo.get_run(conn, user_id, sync_run_id)
        if run is None:
            return SyncRunResult(sync_run_id=sync_run_id, status="failed", error="Unknown sync.")
        done = run.status not in {"queued", "running"}
        if done or waited >= timeout_s:
            return SyncRunResult(
                sync_run_id=run.id,
                status=run.status,
                stats=run.stats,
                error=run.error,
                timed_out=not done,
            )
        await sleep(poll_s)
        waited += poll_s


# ---------------------------------------------------------------------------------------------
# Schedule (S10 rule 3): every 5 min, queue syncs that are due for each active connection
# ---------------------------------------------------------------------------------------------
async def due_connections(conn: AsyncConnection[Any], now: datetime) -> list[tuple[UUID, str]]:
    """Active connections whose last successful sync is older than the platform interval.
    Cross-user scan for the scheduler only (not a repository function)."""
    cur = await conn.execute(
        "select c.user_id, c.platform, max(r.finished_at) filter (where r.status = 'succeeded') "
        "as last_ok from connections c join connection_secrets s on s.connection_id = c.id "
        "left join sync_runs r on r.user_id = c.user_id and r.platform = c.platform "
        "where c.status = 'active' group by c.user_id, c.platform"
    )
    due = []
    for row in await cur.fetchall():
        interval = INTERVAL.get(row["platform"])
        if interval and (row["last_ok"] is None or now - row["last_ok"] >= interval):
            due.append((row["user_id"], row["platform"]))
    return due


@app.periodic(cron="*/5 * * * *", periodic_id="schedule_syncs")
@app.task(name="schedule_syncs", queue="sync", queueing_lock="schedule_syncs")
async def schedule_syncs(timestamp: int) -> None:
    async with await _connect() as conn:
        await retry_pending_deletions(conn)
        from app.sync.intents import dispatch_pending
        from app.sync.recovery import (
            recover_legacy_materials,
            recover_legacy_posts,
            recover_stalled,
        )

        await recover_stalled(conn)
        await recover_legacy_posts(conn)
        await recover_legacy_materials(conn)
        await dispatch_pending(conn)
        now = SystemClock().now()
        for user_id, platform in await due_connections(conn, now):
            from app.core.errors import AppError

            try:
                async with user_work(conn, user_id):
                    # The due snapshot can predate deletion/disconnect; re-read inside the gate.
                    connection = await repo.get_connection(conn, user_id, platform)
                    if (
                        connection
                        and connection.status == "active"
                        and await repo.get_secret(conn, user_id, platform)
                    ):
                        await enqueue_sync(
                            conn, user_id, platform, SyncScope(kind="full"), "schedule"
                        )
            except AppError:
                continue


def check_worker_config() -> None:
    """S10 edge case: the worker refuses to start without an encryption key."""
    get_fernet()
