"""S44 worker-only processing intents. All individual operations bind the owning user."""

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.connectors.base import NMaterial, NPost, PlatformError
from app.core.crypto import encrypt
from app.sync.diff import record_hash


class IntentPersistenceError(PlatformError):
    """A source must not commit without its indexing intent; never include source/error text."""


_JOIN = """
from processing_intents i
left join materials m on m.id=i.material_id and m.user_id=i.user_id
left join posts p on p.id=i.post_id and p.user_id=i.user_id
"""
_ELIGIBLE = (
    "coalesce(m.status,p.status) <> 'removed' "
    "and coalesce(m.content_hash,p.content_hash)=i.source_hash"
)


async def capture(
    conn: AsyncConnection[Any],
    user_id: UUID,
    parent_id: UUID,
    record: NMaterial | NPost,
    outcome: str,
) -> UUID | None:
    try:
        column, table = (
            ("material_id", "materials") if isinstance(record, NMaterial) else ("post_id", "posts")
        )
        row = await (
            await conn.execute(
                f"select id,source_hash from processing_intents where user_id=%s and {column}=%s",
                (user_id, parent_id),
            )
        ).fetchone()
        source_hash = record_hash(record)
        if row and row["source_hash"] == source_hash:
            return row["id"]
        if row is None and outcome == "unchanged":
            if isinstance(record, NMaterial):
                pending = await (
                    await conn.execute(
                        "select id from materials where user_id=%s and id=%s and "
                        "processing_status='pending'",
                        (user_id, parent_id),
                    )
                ).fetchone()
                if not pending:
                    return None
            else:
                current = await (
                    await conn.execute(
                        "select id from chunks where user_id=%s and post_id=%s and "
                        "is_current limit 1",
                        (user_id, parent_id),
                    )
                ).fetchone()
                if current:
                    return None
        payload = (
            encrypt(record.model_dump_json(include={"download", "text", "cues"}))
            if isinstance(record, NMaterial)
            else None
        )
        result = await (
            await conn.execute(
                f"insert into processing_intents(user_id,{column},source_hash,payload_ciphertext) "
                f"select user_id,id,%s,%s from {table} where user_id=%s and id=%s "
                f"and content_hash=%s "
                f"on conflict({column}) do update set source_hash=excluded.source_hash, "
                "payload_ciphertext=excluded.payload_ciphertext,revision=gen_random_uuid(), "
                "dispatch_token=null,dispatch_started_at=null, "
                "dispatched_at=null,completed_at=null, "
                "updated_at=now() where processing_intents.user_id=excluded.user_id returning id",
                (source_hash, payload, user_id, parent_id, source_hash),
            )
        ).fetchone()
        if not result:
            raise IntentPersistenceError("Could not save course processing work.")
        return result["id"]
    except Exception:
        raise IntentPersistenceError("Could not save course processing work.") from None


async def get(conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID) -> dict[str, Any] | None:
    return await (
        await conn.execute(
            f"select i.*,coalesce(m.status,p.status)::text as parent_status, "
            f"coalesce(m.content_hash,p.content_hash) as parent_hash {_JOIN} "
            "where i.user_id=%s and i.id=%s",
            (user_id, intent_id),
        )
    ).fetchone()


async def pending(conn: AsyncConnection[Any], user_id: UUID | None = None) -> list[dict[str, Any]]:
    # The only cross-owner scan: trusted scheduler; each result is revalidated under its user guard.
    return list(
        await (
            await conn.execute(
                f"select i.user_id,i.id,i.revision {_JOIN} where {_ELIGIBLE} "
                "and (%s::uuid is null or i.user_id=%s) and i.completed_at is "
                "null and i.dispatched_at is null "
                "and (i.dispatch_token is null or i.dispatch_started_at < "
                "now()-interval '5 minutes') "
                "order by i.created_at,i.id limit 100",
                (user_id, user_id),
            )
        ).fetchall()
    )


async def reserve(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID, token: UUID
) -> bool:
    row = await (
        await conn.execute(
            "update processing_intents set dispatch_token=%s,dispatch_started_at=now() "
            "where user_id=%s and id=%s and revision=%s and dispatched_at is "
            "null and completed_at is null "
            "and (dispatch_token is null or dispatch_started_at < "
            "now()-interval '5 minutes') returning id",
            (token, user_id, intent_id, revision),
        )
    ).fetchone()
    return row is not None


async def acknowledge(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID, token: UUID
) -> None:
    await conn.execute(
        "update processing_intents set "
        "dispatched_at=now(),dispatch_token=null,dispatch_started_at=null "
        "where user_id=%s and id=%s and revision=%s and dispatch_token=%s and completed_at is null",
        (user_id, intent_id, revision, token),
    )


async def release(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID, token: UUID
) -> None:
    await conn.execute(
        "update processing_intents set dispatch_token=null,dispatch_started_at=null "
        "where user_id=%s and id=%s and revision=%s and dispatch_token=%s",
        (user_id, intent_id, revision, token),
    )


async def reset(conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID) -> None:
    await conn.execute(
        "update processing_intents set "
        "dispatched_at=null,dispatch_token=null,dispatch_started_at=null "
        "where user_id=%s and id=%s and revision=%s and completed_at is null",
        (user_id, intent_id, revision),
    )


async def complete(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID
) -> None:
    await conn.execute(
        "update processing_intents set completed_at=now(),payload_ciphertext=null, "
        "dispatch_token=null,dispatch_started_at=null where user_id=%s and id=%s and revision=%s",
        (user_id, intent_id, revision),
    )
