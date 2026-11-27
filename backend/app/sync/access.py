"""Private source grant checks and session-level import serialization (S46).

Session locks require a direct/session-pooled connection. Row locks are short-lived and
always connection -> secret -> runs/jobs. Never hold row locks across platform I/O.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.connectors.base import SourceSuperseded


@dataclass(frozen=True)
class Grant:
    connection_id: UUID
    revision: UUID | None


@dataclass(frozen=True)
class StoredCredential:
    grant: Grant
    ciphertext: bytes = field(repr=False)


async def snapshot(conn: AsyncConnection[Any], user_id: UUID, platform: str) -> Grant:
    row = await (
        await conn.execute(
            "select c.id,s.revision from connections c left join connection_secrets s "
            "on s.connection_id=c.id where c.user_id=%s and c.platform=%s "
            "and c.status in ('active','error')",
            (user_id, platform),
        )
    ).fetchone()
    if not row:
        raise SourceSuperseded()
    return Grant(row["id"], row["revision"])


async def stored_credentials(
    conn: AsyncConnection[Any], user_id: UUID, platform: str
) -> StoredCredential:
    row = await (
        await conn.execute(
            "select c.id,s.revision,s.ciphertext from connections c join connection_secrets s "
            "on s.connection_id=c.id where c.user_id=%s and c.platform=%s "
            "and c.status in ('active','error')",
            (user_id, platform),
        )
    ).fetchone()
    if not row:
        raise SourceSuperseded()
    return StoredCredential(Grant(row["id"], row["revision"]), bytes(row["ciphertext"]))


async def require_current(
    conn: AsyncConnection[Any],
    user_id: UUID,
    platform: str,
    grant: Grant,
    *,
    locked: bool = False,
    update: bool = False,
) -> None:
    if not locked:
        if await snapshot(conn, user_id, platform) != grant:
            raise SourceSuperseded()
        return
    # Caller owns a transaction. Separate statements avoid FOR SHARE on a nullable join side.
    lock = " for update" if update else " for share"
    row = await (
        await conn.execute(
            "select id,status from connections where user_id=%s and platform=%s" + lock,
            (user_id, platform),
        )
    ).fetchone()
    if not row or row["id"] != grant.connection_id or row["status"] not in {"active", "error"}:
        raise SourceSuperseded()
    secret = await (
        await conn.execute(
            "select revision from connection_secrets where connection_id=%s for share",
            (grant.connection_id,),
        )
    ).fetchone()
    if (secret["revision"] if secret else None) != grant.revision:
        raise SourceSuperseded()


@asynccontextmanager
async def source_lock(
    conn: AsyncConnection[Any], user_id: UUID, platform: str
) -> AsyncIterator[None]:
    async with session_lock(conn, f"source-execution:{user_id}:{platform}"):
        yield


@asynccontextmanager
async def session_lock(conn: AsyncConnection[Any], key: str) -> AsyncIterator[None]:
    """Hold one worker session lock; close on ambiguous acquisition/canceled release."""
    try:
        await conn.execute("select pg_advisory_lock(hashtextextended(%s,0))", (key,))
    except BaseException:
        # Cancellation can arrive after PostgreSQL acquired the lock but before acknowledgment.
        await conn.close()
        raise
    try:
        yield
    finally:
        if not conn.closed:
            try:
                await conn.execute("select pg_advisory_unlock(hashtextextended(%s,0))", (key,))
            except BaseException:
                await conn.close()
                raise
