"""Sync-run, connection and connection-secret queries (S10). Every function takes `(conn, user_id)`.

Secrets: `get_secret` returns ciphertext only; decryption happens in the worker (`app.sync`).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.db.models import Connection, SyncRun

_RUN_COLS = (
    "id, user_id, platform, scope, trigger, status, stats, error, queued_at, started_at, "
    "finished_at, created_at"
)


async def find_open_run(
    conn: AsyncConnection[Any], user_id: UUID, platform: str, scope: dict[str, Any]
) -> SyncRun | None:
    cur = await conn.execute(
        f"select {_RUN_COLS} from sync_runs where user_id = %s and platform = %s and scope = %s "
        "and status in ('queued', 'running') order by queued_at limit 1",
        (user_id, platform, Jsonb(scope)),
    )
    row = await cur.fetchone()
    return SyncRun.model_validate(row) if row else None


async def create_run(
    conn: AsyncConnection[Any],
    user_id: UUID,
    platform: str,
    scope: dict[str, Any],
    trigger: str,
    now: datetime,
) -> UUID:
    cur = await conn.execute(
        "insert into sync_runs (user_id, platform, scope, trigger, status, queued_at) "
        "values (%s, %s, %s, %s, 'queued', %s) returning id",
        (user_id, platform, Jsonb(scope), trigger, now),
    )
    row = await cur.fetchone()
    assert row is not None
    return row["id"]


async def get_run(conn: AsyncConnection[Any], user_id: UUID, run_id: UUID) -> SyncRun | None:
    cur = await conn.execute(
        f"select {_RUN_COLS} from sync_runs where user_id = %s and id = %s", (user_id, run_id)
    )
    row = await cur.fetchone()
    return SyncRun.model_validate(row) if row else None


async def mark_run(
    conn: AsyncConnection[Any],
    user_id: UUID,
    run_id: UUID,
    status: str,
    now: datetime,
    stats: dict[str, int] | None = None,
    error: str | None = None,
) -> None:
    started = "started_at = coalesce(started_at, %s)," if status == "running" else ""
    finished = "finished_at = %s," if status not in {"queued", "running"} else ""
    params: list[Any] = [status]
    if started:
        params.append(now)
    if finished:
        params.append(now)
    params += [Jsonb(stats) if stats is not None else None, error, user_id, run_id]
    await conn.execute(
        f"update sync_runs set status = %s, {started} {finished} "  # noqa: S608
        "stats = coalesce(%s, stats), error = %s where user_id = %s and id = %s "
        "and status in ('queued','running')",
        tuple(params),
    )


async def get_connection(
    conn: AsyncConnection[Any], user_id: UUID, platform: str
) -> Connection | None:
    cur = await conn.execute(
        "select id, user_id, platform, status, expires_at, last_sync_at, last_error, "
        "account_label, created_at from connections where user_id = %s and platform = %s",
        (user_id, platform),
    )
    row = await cur.fetchone()
    return Connection.model_validate(row) if row else None


async def list_connections(conn: AsyncConnection[Any], user_id: UUID) -> list[Connection]:
    cur = await conn.execute(
        "select id, user_id, platform, status, expires_at, last_sync_at, last_error, "
        "account_label, created_at from connections where user_id = %s order by platform",
        (user_id,),
    )
    return [Connection.model_validate(r) for r in await cur.fetchall()]


async def upsert_connection_secret(
    conn: AsyncConnection[Any],
    user_id: UUID,
    platform: str,
    ciphertext: bytes,
    kind: str,
    *,
    expires_at: datetime | None = None,
    account_label: str | None = None,
) -> UUID:
    """Create/replace the connection + its encrypted secret; status back to `active`."""
    async with conn.transaction():
        cur = await conn.execute(
            "insert into connections (user_id, platform, status, expires_at, account_label) "
            "values (%s, %s, 'active', %s, %s) on conflict (user_id, platform) do update set "
            "status = 'active', expires_at = excluded.expires_at, "
            "account_label = coalesce(excluded.account_label, connections.account_label), "
            "last_error = null returning id",
            (user_id, platform, expires_at, account_label),
        )
        row = await cur.fetchone()
        assert row is not None
        connection_id: UUID = row["id"]
        await conn.execute(
            "insert into connection_secrets (connection_id, ciphertext, kind) values (%s, %s, %s) "
            "on conflict (connection_id) do update set ciphertext = excluded.ciphertext, "
            "kind = excluded.kind",
            (connection_id, ciphertext, kind),
        )
        from app.db.repositories.processing import resume_source_auth

        await resume_source_auth(conn, user_id, platform)
        return connection_id


async def get_secret(conn: AsyncConnection[Any], user_id: UUID, platform: str) -> bytes | None:
    cur = await conn.execute(
        "select s.ciphertext from connection_secrets s join connections c "
        "on c.id = s.connection_id where c.user_id = %s and c.platform = %s",
        (user_id, platform),
    )
    row = await cur.fetchone()
    return bytes(row["ciphertext"]) if row else None


async def set_connection_status(
    conn: AsyncConnection[Any],
    user_id: UUID,
    platform: str,
    status: str,
    *,
    error: str | None = None,
    synced_at: datetime | None = None,
) -> None:
    await conn.execute(
        "update connections set status = %s, last_error = %s, "
        "last_sync_at = coalesce(%s, last_sync_at) where user_id = %s and platform = %s",
        (status, error, synced_at, user_id, platform),
    )


async def last_success_at(
    conn: AsyncConnection[Any], user_id: UUID, platform: str
) -> datetime | None:
    cur = await conn.execute(
        "select max(finished_at) as t from sync_runs where user_id = %s and platform = %s "
        "and status = 'succeeded'",
        (user_id, platform),
    )
    row = await cur.fetchone()
    return row["t"] if row else None


async def running_platforms(conn: AsyncConnection[Any], user_id: UUID) -> set[str]:
    cur = await conn.execute(
        "select distinct platform from sync_runs where user_id = %s "
        "and status in ('queued', 'running') "
        "union select platform from connections where user_id = %s and exists ("
        "select 1 from procrastinate_jobs where task_name = 'merge_user' "
        "and status in ('todo', 'doing') and args->>'user_id' = %s)",
        (user_id, user_id, str(user_id)),
    )
    return {r["platform"] for r in await cur.fetchall()}


async def disconnect(
    conn: AsyncConnection[Any], user_id: UUID, platform: str, now: datetime
) -> None:
    """S13-T06: forget credentials, stop queued syncs, retain already imported classes."""
    async with conn.transaction():
        # Match source publication and legacy-secret-trigger ordering before touching jobs/runs.
        row = await (
            await conn.execute(
                "select id from connections where user_id=%s and platform=%s for update",
                (user_id, platform),
            )
        ).fetchone()
        if row:
            await conn.execute(
                "select connection_id from connection_secrets where connection_id=%s for update",
                (row["id"],),
            )
        await conn.execute(
            "select procrastinate_cancel_job_v1(id, false, false) from procrastinate_jobs "
            "where task_name = 'sync_platform' and status = 'todo' "
            "and args->'job'->>'user_id' = %s and args->'job'->>'platform' = %s",
            (str(user_id), platform),
        )
        await conn.execute(
            "update sync_runs set status = 'failed', finished_at = %s, "
            "error = 'Account disconnected.' where user_id = %s and platform = %s "
            "and status in ('queued','running')",
            (now, user_id, platform),
        )
        # The secret cascades from this row. Scheduler only considers active connections.
        await conn.execute(
            "delete from connections where user_id = %s and platform = %s", (user_id, platform)
        )
