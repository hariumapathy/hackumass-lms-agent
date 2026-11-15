"""Conversations, messages, agent runs, study sets and study blocks (S22/S24/S25) on S01 tables.
Every function is `fn(conn, user_id, ...)` and filters by user_id."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection


async def get_conversation(
    conn: AsyncConnection[Any], user_id: UUID, conversation_id: UUID
) -> dict[str, Any] | None:
    cur = await conn.execute(
        "select id, title, updated_at from conversations where user_id = %s and id = %s",
        (user_id, conversation_id),
    )
    return await cur.fetchone()


async def create_conversation(
    conn: AsyncConnection[Any], user_id: UUID, title: str, now: datetime
) -> UUID:
    cur = await conn.execute(
        "insert into conversations (user_id, title, updated_at) values (%s, %s, %s) returning id",
        (user_id, title, now),
    )
    row = await cur.fetchone()
    assert row is not None
    return row["id"]


async def touch_conversation(
    conn: AsyncConnection[Any], user_id: UUID, conversation_id: UUID, now: datetime
) -> None:
    await conn.execute(
        "update conversations set updated_at = %s where user_id = %s and id = %s",
        (now, user_id, conversation_id),
    )


async def list_conversations(conn: AsyncConnection[Any], user_id: UUID) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "select id, title, updated_at from conversations where user_id = %s "
        "order by updated_at desc limit 100",
        (user_id,),
    )
    return list(await cur.fetchall())


async def list_messages(
    conn: AsyncConnection[Any], user_id: UUID, conversation_id: UUID
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "select id, role, content, created_at from messages "
        "where user_id = %s and conversation_id = %s order by created_at, id",
        (user_id, conversation_id),
    )
    return list(await cur.fetchall())


async def insert_message(
    conn: AsyncConnection[Any],
    user_id: UUID,
    conversation_id: UUID,
    message_id: UUID,
    role: str,
    content: dict[str, Any],
    created_at: datetime,
) -> None:
    await conn.execute(
        "insert into messages (id, user_id, conversation_id, role, content, created_at) "
        "values (%s, %s, %s, %s, %s::jsonb, %s)",
        (message_id, user_id, conversation_id, role, json.dumps(content, default=str), created_at),
    )


async def insert_run(
    conn: AsyncConnection[Any], user_id: UUID, run_id: UUID, conversation_id: UUID, model: str
) -> None:
    await conn.execute(
        "insert into agent_runs (id, user_id, conversation_id, model) values (%s, %s, %s, %s)",
        (run_id, user_id, conversation_id, model),
    )


async def finish_run(
    conn: AsyncConnection[Any],
    user_id: UUID,
    run_id: UUID,
    status: str,
    turns: int,
    tool_calls: list[dict[str, Any]],
    allowed_chunk_ids: list[int],
    error: str | None,
) -> None:
    await conn.execute(
        "update agent_runs set status = %s, turns = %s, tool_calls = %s::jsonb, "
        "allowed_chunk_ids = %s, error = %s, finished_at = now() where user_id = %s and id = %s",
        (status, turns, json.dumps(tool_calls), allowed_chunk_ids, error, user_id, run_id),
    )


async def insert_study_set(
    conn: AsyncConnection[Any], user_id: UUID, study_set: dict[str, Any]
) -> None:
    await conn.execute(
        "insert into study_sets (id, user_id, course_id, conversation_id, type, title, payload, "
        "created_at) values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
        (
            study_set["id"],
            user_id,
            study_set.get("course_id"),
            study_set.get("conversation_id"),
            study_set["type"],
            study_set["title"],
            json.dumps(study_set["payload"], default=str),
            study_set["created_at"],
        ),
    )


async def list_study_sets(conn: AsyncConnection[Any], user_id: UUID) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "select id, type::text as type, title, course_id, created_at, payload from study_sets "
        "where user_id = %s order by created_at desc limit 200",
        (user_id,),
    )
    return list(await cur.fetchall())


async def insert_blocks(
    conn: AsyncConnection[Any],
    user_id: UUID,
    blocks: list[dict[str, Any]],
    run_id: UUID | None = None,
) -> None:
    for b in blocks:
        await conn.execute(
            "insert into study_blocks (id, user_id, run_id, course_id, item_id, title, start_at, "
            "end_at, status) values (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "on conflict (id) do nothing",
            (
                b["id"],
                user_id,
                run_id,
                b.get("course_id"),
                b.get("item_id"),
                b["title"],
                b["start_at"],
                b["end_at"],
                b.get("status", "proposed"),
            ),
        )


async def list_blocks(conn: AsyncConnection[Any], user_id: UUID) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "select id, title, start_at, end_at, course_id, item_id, status::text as status "
        "from study_blocks where user_id = %s order by start_at",
        (user_id,),
    )
    return list(await cur.fetchall())


async def decide_blocks(
    conn: AsyncConnection[Any], user_id: UUID, block_ids: list[UUID], approve: bool
) -> list[dict[str, Any]]:
    """Only `proposed` blocks owned by the student change (S25)."""
    cur = await conn.execute(
        "update study_blocks set status = %s, decided_at = now() "
        "where user_id = %s and id = any(%s) and status = 'proposed' "
        "returning id, title, start_at, end_at, course_id, item_id, status::text as status",
        ("approved" if approve else "declined", user_id, block_ids),
    )
    return list(await cur.fetchall())
