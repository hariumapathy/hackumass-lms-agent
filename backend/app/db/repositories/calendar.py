"""S25 user-scoped calendar queries; only private token resolution precedes a user ID."""

import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.api.schemas import StudyBlock


async def feed_token(conn: AsyncConnection[Any], user_id: UUID, rotate: bool = False) -> str:
    token = secrets.token_urlsafe(32)
    if rotate:
        query = (
            "insert into calendar_feeds (user_id,secret_token) values (%s,%s) on conflict "
            "(user_id) do update set secret_token=excluded.secret_token,rotated_at=now() "
            "returning secret_token"
        )
    else:
        query = (
            "insert into calendar_feeds (user_id,secret_token) values (%s,%s) on conflict "
            "(user_id) do update set user_id=excluded.user_id returning secret_token"
        )
    cur = await conn.execute(query, (user_id, token))
    row = await cur.fetchone()
    assert row is not None
    return row["secret_token"]


async def _feed_owner(conn: AsyncConnection[Any], token: str) -> UUID | None:
    cur = await conn.execute("select user_id from calendar_feeds where secret_token=%s", (token,))
    row = await cur.fetchone()
    return row["user_id"] if row else None


async def feed_items(
    conn: AsyncConnection[Any], user_id: UUID, now: datetime
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        """
        select i.id,i.title,i.due_at,i.updated_at,coalesce(c.code,c.name) as course_code,
          (select count(*) from changes ch where ch.user_id=i.user_id and ch.entity_type='item'
           and ch.entity_id=i.id and ch.field='due_at') as sequence,
          coalesce((select jsonb_agg(jsonb_build_object('platform',s.platform,'url',s.source_url)
           order by s.platform,s.id) from item_sources s where s.user_id=i.user_id
           and s.item_id=i.id and s.status<>'removed'),'[]') as sources
        from items i join courses c on c.id=i.course_id and c.user_id=i.user_id
        where i.user_id=%s and i.status<>'removed' and i.due_at between %s and %s
        order by i.due_at,i.id
    """,
        (user_id, now - timedelta(days=7), now + timedelta(days=120)),
    )
    return list(await cur.fetchall())


async def approved_blocks(conn: AsyncConnection[Any], user_id: UUID) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "select id,title,start_at,end_at,coalesce(decided_at,created_at) as modified "
        "from study_blocks where user_id=%s and status='approved' order by "
        "start_at,id",
        (user_id,),
    )
    return list(await cur.fetchall())


async def decide(
    conn: AsyncConnection[Any], user_id: UUID, ids: list[UUID], approve: bool, now: datetime
) -> list[StudyBlock]:
    async with conn.transaction():
        await conn.execute(
            "update study_blocks set status=case when created_at < %s then "
            "'declined'::study_block_status else %s::study_block_status end,decided_at=%s "
            "where user_id=%s and id=any(%s) and status='proposed'",
            (now - timedelta(hours=24), "approved" if approve else "declined", now, user_id, ids),
        )
        cur = await conn.execute(
            "select id,title,start_at,end_at,course_id,item_id,status from study_blocks "
            "where user_id=%s and id=any(%s) order by start_at,id",
            (user_id, ids),
        )
        return [StudyBlock.model_validate(r) for r in await cur.fetchall()]


async def propose(
    conn: AsyncConnection[Any], user_id: UUID, block: StudyBlock, now: datetime
) -> bool:
    async with conn.transaction():
        await conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s,0))", (f"blocks:{user_id}",)
        )
        if block.course_id:
            cur = await conn.execute(
                "select 1 from courses where user_id=%s and id=%s", (user_id, block.course_id)
            )
            if await cur.fetchone() is None:
                raise ValueError("Course not found.")
        if block.item_id:
            cur = await conn.execute(
                "select 1 from items where user_id=%s and id=%s", (user_id, block.item_id)
            )
            if await cur.fetchone() is None:
                raise ValueError("Assignment not found.")
        cur = await conn.execute(
            "select 1 from study_blocks where user_id=%s and start_at<%s and end_at>%s "
            "and (status='approved' or (status='proposed' and created_at>=%s)) limit 1",
            (user_id, block.end_at, block.start_at, now - timedelta(hours=24)),
        )
        if await cur.fetchone():
            return False
        await conn.execute(
            "insert into study_blocks "
            "(id,user_id,course_id,item_id,title,start_at,end_at,created_at) values "
            "(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                block.id,
                user_id,
                block.course_id,
                block.item_id,
                block.title,
                block.start_at,
                block.end_at,
                now,
            ),
        )
        return True
