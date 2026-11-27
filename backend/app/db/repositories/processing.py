"""S44 worker-only processing intents. All individual operations bind the owning user."""

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.sql import SQL, Identifier

from app.connectors.base import NMaterial, NPost, PlatformError
from app.core.crypto import decrypt, encrypt
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
    "and (coalesce(m.content_hash,p.content_hash)=i.source_hash "
    "or coalesce(m.source_revision,p.source_revision)<>i.parent_source_revision)"
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
                f"select "
                f"id,source_hash,blocked_reason,payload_ciphertext,completed_at,"
                f"parent_source_revision,last_error_code "
                f"from processing_intents where user_id=%s and {column}=%s",
                (user_id, parent_id),
            )
        ).fetchone()
        parent = await (
            await conn.execute(
                f"select source_revision from {table} where user_id=%s and id=%s",
                (user_id, parent_id),
            )
        ).fetchone()
        source_hash = record_hash(record)
        if row and row["source_hash"] == source_hash:
            needs_source = (
                isinstance(record, NMaterial)
                and row["payload_ciphertext"] is None
                and row["completed_at"] is None
            )
            fresh_access = False
            if (
                row["blocked_reason"] == "source_auth"
                and isinstance(record, NMaterial)
                and row["payload_ciphertext"]
            ):
                fresh_access = decrypt(bytes(row["payload_ciphertext"])) != record.model_dump_json(
                    include={"download", "text", "cues"}
                )
            # Refilling a retired payload is not permission to reopen a stopped processor.
            if row["blocked_reason"] in {"configuration", "permanent"} or (
                row["blocked_reason"] == "exhausted"
                and row["last_error_code"] != "source_refresh_exhausted"
            ):
                return row["id"]
            if row["blocked_reason"] == "source_auth" and not fresh_access:
                return row["id"]
            if (
                not fresh_access
                and not needs_source
                and (
                    row["completed_at"]
                    or (parent and row["parent_source_revision"] == parent["source_revision"])
                )
            ):
                return row["id"]
        if row is None and outcome == "unchanged":
            if isinstance(record, NMaterial):
                pending = await (
                    await conn.execute(
                        "select id from materials where user_id=%s and id=%s and "
                        "processing_status in ('pending','failed','processing')",
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
                f"insert into processing_intents(user_id,{column},source_hash,"
                f"payload_ciphertext,parent_source_revision) "
                f"select user_id,id,%s,%s,source_revision from {table} where user_id=%s and id=%s "
                f"and content_hash=%s "
                f"on conflict({column}) do update set source_hash=excluded.source_hash, "
                "payload_ciphertext=excluded.payload_ciphertext,revision=gen_random_uuid(), "
                "parent_source_revision=excluded.parent_source_revision, "
                "dispatch_token=null,dispatch_started_at=null, "
                "dispatched_at=null,completed_at=null, "
                "attempts=0,next_attempt_at=now(),last_started_at=null,"
                "blocked_reason=null,last_error_code=null, "
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
            f"coalesce(m.content_hash,p.content_hash) as parent_hash, "
            f"coalesce(m.source_revision,p.source_revision) as current_source_revision {_JOIN} "
            "where i.user_id=%s and i.id=%s",
            (user_id, intent_id),
        )
    ).fetchone()


async def repair_source_revision(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID
) -> bool:
    """Retire unbound material payloads; posts can rebuild from owned current DB text."""
    async with conn.transaction():
        initial = await get(conn, user_id, intent_id)
        if not initial:
            return False
        table, parent = (
            ("materials", initial["material_id"])
            if initial["material_id"]
            else ("posts", initial["post_id"])
        )
        await conn.execute(
            f"select id from {table} where user_id=%s and id=%s for update", (user_id, parent)
        )
        await conn.execute(
            "select id from processing_intents where user_id=%s and id=%s for update",
            (user_id, intent_id),
        )
        row = await get(conn, user_id, intent_id)
        if (
            not row
            or row["revision"] != revision
            or row["completed_at"]
            or row["blocked_reason"]
            or row["attempts"] >= 4
            or row["parent_status"] not in {"active", "changed"}
            or row["parent_source_revision"] == row["current_source_revision"]
        ):
            return False
        material = row["material_id"] is not None
        await conn.execute(
            "update processing_intents set revision=gen_random_uuid(),dispatched_at=null,"
            "dispatch_token=null,dispatch_started_at=null,last_started_at=null, "
            "parent_source_revision=%s,source_hash=%s,payload_ciphertext=null, "
            "blocked_reason=%s,last_error_code=%s where user_id=%s and id=%s and revision=%s",
            (
                row["parent_source_revision"] if material else row["current_source_revision"],
                row["source_hash"] if material else row["parent_hash"],
                "source_refresh" if material else None,
                "missing_source" if material else None,
                user_id,
                intent_id,
                revision,
            ),
        )
        if material:
            await conn.execute(
                "update materials set processing_status='failed',processing_error="
                "'This file changed. Try updating your classes.' where user_id=%s and id=%s",
                (user_id, parent),
            )
        return True


async def rebind_course_parents(
    conn: AsyncConnection[Any], user_id: UUID, table: str, parents: list[tuple[UUID, UUID]]
) -> None:
    """Only the trusted course-only merge calls this, after locking/reparenting source rows."""
    if table not in {"materials", "posts"}:
        raise ValueError("unsupported processing parent")
    column = "material_id" if table == "materials" else "post_id"
    await conn.execute(
        SQL(
            "update processing_intents i set parent_source_revision=p.source_revision, "
            "revision=gen_random_uuid(),dispatched_at=null,dispatch_token=null,dispatch_started_at=null,"
            "last_started_at=null from {} p, "
            "unnest(%s::uuid[],%s::uuid[]) previous(id,revision) "
            "where i.user_id=%s and p.user_id=i.user_id "
            "and i.{}=p.id and p.id=previous.id and i.parent_source_revision=previous.revision "
            "and i.completed_at is null "
            "and i.source_hash=p.content_hash"
        ).format(Identifier(table), Identifier(column)),
        ([p[0] for p in parents], [p[1] for p in parents], user_id),
    )


async def pending(conn: AsyncConnection[Any], user_id: UUID | None = None) -> list[dict[str, Any]]:
    # The only cross-owner scan: trusted scheduler; each result is revalidated under its user guard.
    return list(
        await (
            await conn.execute(
                f"select i.user_id,i.id,i.revision {_JOIN} where {_ELIGIBLE} "
                "and (%s::uuid is null or i.user_id=%s) and i.completed_at is "
                "null and i.dispatched_at is null and i.blocked_reason is null and i.attempts<4 "
                "and i.next_attempt_at<=now() "
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
            "update processing_intents set dispatch_token=%s,dispatch_started_at=now(), "
            "last_started_at=null "
            "where user_id=%s and id=%s and revision=%s and dispatched_at is "
            "null and completed_at is null and blocked_reason is null and attempts<4 "
            "and next_attempt_at<=now() "
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
        "dispatch_token=null,dispatch_started_at=null where user_id=%s and id=%s and revision=%s "
        "and completed_at is null",
        (user_id, intent_id, revision),
    )


async def claim(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID
) -> int | None:
    row = await (
        await conn.execute(
            "update processing_intents set attempts=attempts+1,last_started_at=now() "
            "where user_id=%s and id=%s and revision=%s and completed_at is null "
            "and blocked_reason is null and attempts<4 and "
            "next_attempt_at<=now() returning attempts",
            (user_id, intent_id, revision),
        )
    ).fetchone()
    return row["attempts"] if row else None


async def fail(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID, kind: str, code: str
) -> bool:
    # Lock parent before intent, matching capture's parent->intent order and avoiding deadlocks.
    async with conn.transaction():
        current = await get(conn, user_id, intent_id)
        if not current or current["revision"] != revision or current["completed_at"]:
            return False
        table, parent = (
            ("materials", current["material_id"])
            if current["material_id"]
            else ("posts", current["post_id"])
        )
        await conn.execute(
            f"select id from {table} where user_id=%s and id=%s for update", (user_id, parent)
        )
        current = await get(conn, user_id, intent_id)
        if (
            not current
            or current["revision"] != revision
            or current["completed_at"]
            or current["parent_status"] not in {"active", "changed"}
            or current["parent_hash"] != current["source_hash"]
            or current["parent_source_revision"] != current["current_source_revision"]
        ):
            return False
        attempts = current["attempts"]
        reason = ("exhausted" if attempts >= 4 else None) if kind == "retry" else kind
        delay = (30, 120, 600)[min(max(attempts - 1, 0), 2)]
        row = await (
            await conn.execute(
                "update processing_intents set blocked_reason=%s,last_error_code=%s, "
                "next_attempt_at=now()+%s*interval '1 second',dispatched_at=null, "
                "dispatch_token=null,dispatch_started_at=null where user_id=%s "
                "and id=%s and revision=%s "
                "and completed_at is null returning material_id,source_hash",
                (reason, code, delay, user_id, intent_id, revision),
            )
        ).fetchone()
        if row and row["material_id"]:
            message = (
                "This file is unavailable. Try updating your classes."
                if kind == "source_auth"
                else "This file couldn't be prepared. Open the original course page for now."
            )
            await conn.execute(
                "update materials set processing_status='failed',processing_error=%s "
                "where user_id=%s and id=%s and content_hash=%s",
                (message, user_id, row["material_id"], row["source_hash"]),
            )
        return row is not None


async def active_job(
    conn: AsyncConnection[Any], user_id: UUID, intent_id: UUID, revision: UUID
) -> bool:
    row = await (
        await conn.execute(
            "select id from procrastinate_jobs where task_name='process_intent' "
            "and status in ('todo','doing') and args->>'user_id'=%s and args->>'intent_id'=%s "
            "and args->>'revision'=%s limit 1",
            (str(user_id), str(intent_id), str(revision)),
        )
    ).fetchone()
    return row is not None


async def resume(conn: AsyncConnection[Any], user_id: UUID) -> int:
    rows = await (
        await conn.execute(
            "update processing_intents set attempts=0,next_attempt_at=now(),last_started_at=null, "
            "blocked_reason=case when material_id is not null and payload_ciphertext is null "
            "then 'source_refresh' else null end,last_error_code=null,revision=gen_random_uuid(), "
            "dispatched_at=null,dispatch_token=null,dispatch_started_at=null "
            "where user_id=%s and completed_at is null and blocked_reason in "
            "('configuration','exhausted') returning id",
            (user_id,),
        )
    ).fetchall()
    return len(rows)


async def resume_source_auth(conn: AsyncConnection[Any], user_id: UUID, platform: str) -> None:
    # A newly validated credential is a separate, explicit authorization signal.
    await conn.execute(
        "update processing_intents i set blocked_reason=case when material_id is not null "
        "and payload_ciphertext is null then 'source_refresh' else null end, "
        "last_error_code=null,attempts=0, "
        "next_attempt_at=now(),last_started_at=null,revision=gen_random_uuid(),dispatched_at=null, "
        "dispatch_token=null,dispatch_started_at=null where i.user_id=%s "
        "and i.blocked_reason='source_auth' "
        "and i.completed_at is null and (exists(select 1 from materials m "
        "where m.user_id=i.user_id "
        "and m.id=i.material_id and m.platform=%s) or exists(select 1 "
        "from posts p where p.user_id=i.user_id "
        "and p.id=i.post_id and p.platform=%s))",
        (user_id, platform, platform),
    )
