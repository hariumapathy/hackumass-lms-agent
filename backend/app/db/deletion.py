"""S40 durable clear-data checkpoint and cross-process user work barriers.

Session advisory locks require a direct/session-pooled DB URL, never transaction pooling.
Callers must hold the shared barrier through *all* owned writes/side effects, including SSE.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection, OperationalError

from app.core.errors import AppError
from app.db.repositories import profiles
from app.sync.processing.storage import Storage, delete_user_files

log = logging.getLogger(__name__)


def pending_error() -> AppError:
    return AppError(
        "internal",
        "Your saved data is being cleared. Open Settings and try clearing it again.",
        status=503,
        retryable=True,
    )


async def generation(conn: AsyncConnection[Any], user_id: UUID) -> int:
    row = await (
        await conn.execute(
            "select generation, state from account_data_state where user_id=%s", (user_id,)
        )
    ).fetchone()
    if row and row["state"] == "pending":
        raise pending_error()
    return row["generation"] if row else 0


@asynccontextmanager
async def user_work(conn: AsyncConnection[Any], user_id: UUID) -> AsyncIterator[int]:
    key = f"account-data:{user_id}"
    row = await (
        await conn.execute(
            "select pg_try_advisory_lock_shared(hashtextextended(%s,0)) as locked", (key,)
        )
    ).fetchone()
    if not row or not row["locked"]:
        raise pending_error()
    try:
        yield await generation(conn, user_id)
    finally:
        if not conn.closed:
            try:
                await conn.execute(
                    "select pg_advisory_unlock_shared(hashtextextended(%s,0))", (key,)
                )
            except OperationalError:
                await conn.close()  # lost session already released its lock; preserve body error
            except BaseException:
                await conn.close()  # never return a session with a leaked advisory lock
                raise


async def _scrub_jobs(conn: AsyncConnection[Any], user_id: UUID) -> None:
    # Includes both sync's nested job envelope and process/merge's flat args.
    owner = "(args->>'user_id'=%s or args->'job'->>'user_id'=%s or args->>'_deletion_owner'=%s)"
    params = (str(user_id),) * 3
    await conn.execute(
        f"delete from procrastinate_jobs where {owner} and status <> 'doing'", params
    )
    # Retain doing rows for Procrastinate's finish/retry acknowledgment. Remove source payloads.
    await conn.execute(
        f"update procrastinate_jobs set args=jsonb_build_object('_deletion_owner',%s::text), "
        f"abort_requested=true where {owner} and status='doing'",
        (str(user_id), *params),
    )


async def clear_user_data(
    conn: AsyncConnection[Any],
    user_id: UUID,
    *,
    storage: Storage | None = None,
    wait_ms: int = 5000,
    retry_pending_only: bool = False,
) -> None:
    """204 is safe only after this returns. Failure is durable and resumable, never success."""
    if not retry_pending_only:
        # Autocommit required: the gate must be visible before waiting for ongoing work.
        await conn.execute(
            "insert into account_data_state (user_id,generation,state) values (%s,1,'pending') "
            "on conflict(user_id) do update set state='pending', completed_at=null, "
            "requested_at=case when account_data_state.state='pending' then "
            "account_data_state.requested_at else now() end, "
            "generation=account_data_state.generation + "
            "case when account_data_state.state='pending' then 0 else 1 end",
            (user_id,),
        )
    key = f"account-data:{user_id}"
    locked = False
    try:
        # Poll with nonblocking acquisition: no global statement_timeout side effects.
        import asyncio

        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_ms / 1000
        while True:
            row = await (
                await conn.execute(
                    "select pg_try_advisory_lock(hashtextextended(%s,0)) as locked", (key,)
                )
            ).fetchone()
            if row and row["locked"]:
                locked = True
                break
            if loop.time() >= deadline:
                raise pending_error()
            await asyncio.sleep(min(0.05, max(0, deadline - loop.time())))
        row = await (
            await conn.execute("select state from account_data_state where user_id=%s", (user_id,))
        ).fetchone()
        if not row or row["state"] != "pending":
            return  # another cleanup completed while this caller waited
        async with conn.transaction():
            await _scrub_jobs(conn, user_id)
            await profiles.delete_user_data(conn, user_id)
        await delete_user_files(user_id, storage)
        await conn.execute(
            "update account_data_state set state='complete',completed_at=now() where user_id=%s",
            (user_id,),
        )
    except AppError:
        raise
    except Exception as exc:
        # Never include storage response text, payloads, cookies, SQL parameters or file paths.
        log.warning("saved-data cleanup incomplete: %s", type(exc).__name__)
        raise pending_error() from None
    finally:
        if locked:
            try:
                await conn.execute("select pg_advisory_unlock(hashtextextended(%s,0))", (key,))
            except BaseException:
                await conn.close()
                raise


async def retry_pending_deletions(
    conn: AsyncConnection[Any],
    *,
    storage: Storage | None = None,
) -> None:
    rows = await (
        await conn.execute(
            "select user_id from account_data_state where state='pending' "
            "order by requested_at limit 50"
        )
    ).fetchall()
    for row in rows:
        try:
            await clear_user_data(conn, row["user_id"], storage=storage, retry_pending_only=True)
        except AppError:
            pass  # checkpoint remains pending; next periodic pass retries
    # Framework acknowledgment has now completed; remove redacted terminal bookkeeping.
    await conn.execute(
        "delete from procrastinate_jobs where args ? '_deletion_owner' and status <> 'doing'"
    )


# Eight guarded requests/login completions leave two pool slots for cleanup/ordinary work.
_guarded_sessions = 0


@asynccontextmanager
async def user_session(user_id: UUID) -> AsyncIterator[int]:
    from app.db.pool import bind_connection, connection

    global _guarded_sessions
    if _guarded_sessions >= 8:
        raise AppError(
            "internal", "We're busy right now. Try again in a moment.", 503, retryable=True
        )
    _guarded_sessions += 1
    try:
        async with connection() as conn:
            async with user_work(conn, user_id) as epoch:
                async with bind_connection(conn):
                    yield epoch
    finally:
        _guarded_sessions -= 1
