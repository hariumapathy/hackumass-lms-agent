"""S44 transactional-outbox dispatch and worker execution; no student source data in queue args."""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from psycopg import AsyncConnection

from app.core.crypto import decrypt
from app.core.errors import AppError
from app.db.deletion import user_work
from app.db.repositories import processing as repo

log = logging.getLogger(__name__)
Defer = Callable[[dict[str, str]], Awaitable[None]]


async def _defer(args: dict[str, str]) -> None:
    from app.sync.jobs import process_intent

    # At-least-once delivery: a shared queueing_lock can make a running job's framework
    # retry collide with a replayed todo row. Execution locks + completion CAS do the dedup.
    await process_intent.configure(lock=f"intent:{args['intent_id']}").defer_async(**args)


async def dispatch_one(
    conn: AsyncConnection[Any],
    user_id: UUID,
    intent_id: UUID,
    *,
    defer: Defer | None = None,
) -> bool:
    async with user_work(conn, user_id):
        row = await repo.get(conn, user_id, intent_id)
        if (
            row
            and not row["completed_at"]
            and row["parent_source_revision"] != row["current_source_revision"]
        ):
            await repo.repair_source_revision(conn, user_id, intent_id, row["revision"])
            row = await repo.get(conn, user_id, intent_id)
        if (
            not row
            or row["parent_status"] not in {"active", "changed"}
            or row["parent_hash"] != row["source_hash"]
            or row["parent_source_revision"] != row["current_source_revision"]
        ):
            return False
        token = uuid4()
        revision = row["revision"]
        if not await repo.reserve(conn, user_id, intent_id, revision, token):
            return False
        try:
            await (defer or _defer)(
                {"user_id": str(user_id), "intent_id": str(intent_id), "revision": str(revision)}
            )
            await repo.acknowledge(conn, user_id, intent_id, revision, token)
        except Exception as exc:
            try:
                await repo.release(conn, user_id, intent_id, revision, token)
            except Exception:
                pass  # a lost DB connection leaves an expiring lease, never lost work
            log.warning("index work could not be queued: %s", type(exc).__name__)
            return False
        return True


async def dispatch_pending(
    conn: AsyncConnection[Any],
    *,
    user_id: UUID | None = None,
    defer: Defer | None = None,
) -> int:
    dispatched = 0
    for row in await repo.pending(conn, user_id):
        try:
            dispatched += int(await dispatch_one(conn, row["user_id"], row["id"], defer=defer))
        except AppError:
            continue  # deletion owns this account; no bypass of its pending gate
    return dispatched


async def dispatch_parent(
    conn: AsyncConnection[Any],
    user_id: UUID,
    *,
    material_id: UUID | None = None,
    post_id: UUID | None = None,
) -> None:
    column, parent = ("material_id", material_id) if material_id else ("post_id", post_id)
    row = await (
        await conn.execute(
            f"select id from processing_intents where user_id=%s and {column}=%s",
            (user_id, parent),
        )
    ).fetchone()
    if row:
        await dispatch_one(conn, user_id, row["id"])


@asynccontextmanager
async def intent_lock(
    conn: AsyncConnection[Any], intent_id: UUID, *, wait: bool = True
) -> AsyncIterator[bool]:
    key = f"index-work:{intent_id}"
    try:
        if wait:
            await conn.execute("select pg_advisory_lock(hashtextextended(%s,0))", (key,))
        else:
            row = await (
                await conn.execute(
                    "select pg_try_advisory_lock(hashtextextended(%s,0)) as locked", (key,)
                )
            ).fetchone()
            if not row or not row["locked"]:
                yield False
                return
    except BaseException:
        await conn.close()  # acquisition may have completed just as cancellation arrived
        raise
    try:
        yield True
    finally:
        if not conn.closed:
            try:
                await conn.execute("select pg_advisory_unlock(hashtextextended(%s,0))", (key,))
            except BaseException:
                await conn.close()
                raise


async def execute(
    conn: AsyncConnection[Any], *, user_id: str, intent_id: str, revision: str
) -> str:
    from app.sync.processing import worker
    from app.sync.processing.failures import ProcessingFailure, RetryableProcessingError, classify
    from app.sync.processing.publication import bind_intent

    uid, iid, expected = UUID(user_id), UUID(intent_id), UUID(revision)
    async with user_work(conn, uid), intent_lock(conn, iid):
        row = await repo.get(conn, uid, iid)
        if not row:
            return "missing"
        if row["revision"] != expected:
            return "superseded"
        if row["completed_at"]:
            return "already_complete"
        if row["parent_status"] not in {"active", "changed"}:
            await repo.reset(conn, uid, iid, expected)
            return "unavailable"
        if row["blocked_reason"] or row["attempts"] >= 4:
            return "blocked"
        if row["parent_source_revision"] != row["current_source_revision"]:
            await repo.repair_source_revision(conn, uid, iid, expected)
            return "unavailable"
        if (
            row["parent_status"] not in {"active", "changed"}
            or row["parent_hash"] != row["source_hash"]
        ):
            await repo.reset(conn, uid, iid, expected)
            return "unavailable"
        if await repo.claim(conn, uid, iid, expected) is None:
            latest = await repo.get(conn, uid, iid)
            return "superseded" if latest and latest["revision"] != expected else "deferred"
        try:
            with bind_intent(row):
                if row["material_id"]:
                    payload = row["payload_ciphertext"]
                    if payload is None:
                        raise ProcessingFailure("configuration", "missing_source")
                    source = json.loads(decrypt(bytes(payload)))
                    result = await worker.run_process_material(
                        conn, uid, row["material_id"], source
                    )
                else:
                    result = await worker.run_process_post(conn, uid, row["post_id"])
            if result in {"done", "unchanged", "skipped", "empty"}:
                await repo.complete(conn, uid, iid, expected)
                return result
            if result == "needs_reconnect":
                raise ProcessingFailure("source_auth", "source_access")
            if result == "superseded":
                await repo.reset(conn, uid, iid, expected)
                return "superseded"
            if result == "missing":
                await repo.reset(conn, uid, iid, expected)
                return "unavailable"
            raise RetryableProcessingError("processing_failed")
        except Exception as error:
            failure = classify(error)
            applied = await repo.fail(conn, uid, iid, expected, failure.kind, failure.code)
            if not applied:
                await repo.reset(conn, uid, iid, expected)
                return "superseded"
            return "retry_scheduled" if failure.kind == "retry" else "blocked"


async def recover_stalled(conn: AsyncConnection[Any], *, user_id: UUID | None = None) -> int:
    from app.sync.recovery import recover_stalled as recover

    return await recover(conn, user_id=user_id)


async def resume(conn: AsyncConnection[Any], user_id: UUID) -> int:
    async with user_work(conn, user_id):
        return await repo.resume(conn, user_id)


async def recover_legacy_posts(conn: AsyncConnection[Any], *, user_id: UUID | None = None) -> int:
    from app.sync.recovery import recover_legacy_posts as recover

    return await recover(conn, user_id=user_id)
