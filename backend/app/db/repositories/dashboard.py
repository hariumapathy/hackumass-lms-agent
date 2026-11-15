"""Deterministic dashboard queries (S32). All data is scoped to the authenticated student."""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.api import schemas as s
from app.core.change_text import change_summary


async def items(
    conn: AsyncConnection[Any],
    user_id: UUID,
    now: datetime,
    course_id: UUID | None = None,
    item_type: str | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
) -> list[s.Item]:
    cur = await conn.execute(
        """
        select i.id, i.course_id, coalesce(c.code, c.name) as course_code,
               i.type, i.title, i.due_at, i.points,
               case when i.status = 'changed' and not exists (
                   select 1 from changes ch where ch.user_id = i.user_id
                   and ch.entity_type = 'item' and ch.entity_id = i.id
                   and ch.seen_at is null and ch.detected_at >= %s - interval '14 days'
               ) then 'active' else i.status::text end as status,
               coalesce((select jsonb_agg(jsonb_build_object(
                   'platform', src.platform, 'source_url', src.source_url,
                   'last_synced_at', src.last_synced_at) order by src.platform, src.id)
                   from item_sources src where src.user_id = i.user_id
                   and src.item_id = i.id and src.status <> 'removed'), '[]') as sources,
               array(select distinct ch.field from changes ch
                   where ch.user_id = i.user_id and ch.entity_id = i.id
                   and ch.entity_type = 'item' and ch.seen_at is null
                   and ch.detected_at >= %s - interval '14 days'
                   order by ch.field) as changed_fields
        from items i join courses c on c.id = i.course_id and c.user_id = i.user_id
        where i.user_id = %s and i.status <> 'removed'
          and (%s::uuid is null or i.course_id = %s)
          and (%s::text is null or i.type::text = %s)
          and (%s::timestamptz is null or i.due_at >= %s)
          and (%s::timestamptz is null or i.due_at <= %s)
        order by i.due_at nulls last, i.id
        """,
        (now, now, user_id, course_id, course_id, item_type, item_type, from_, from_, to, to),
    )
    return [s.Item.model_validate(r) for r in await cur.fetchall()]


async def courses(
    conn: AsyncConnection[Any],
    user_id: UUID,
    now: datetime,
) -> list[s.CourseSummary]:
    cur = await conn.execute(
        """
        select c.id, coalesce(c.code, c.name) as code, c.name, c.term, c.color,
               (select count(*) from items i where i.user_id = c.user_id
                and i.course_id = c.id and i.status <> 'removed' and i.due_at >= %s)
                as upcoming_count,
               array(select distinct l.platform::text from course_links l
                     where l.user_id = c.user_id and l.course_id = c.id
                     and l.status <> 'removed' order by l.platform::text) as platforms
        from courses c where c.user_id = %s order by code, c.id
        """,
        (now, user_id),
    )
    return [s.CourseSummary.model_validate(r) for r in await cur.fetchall()]


async def posts(
    conn: AsyncConnection[Any],
    user_id: UUID,
    course_id: UUID | None = None,
    since: datetime | None = None,
) -> list[s.Post]:
    cur = await conn.execute(
        """
        select id, course_id, kind, title, left(body, 240) as excerpt,
               posted_at, source_url, status
        from posts where user_id = %s and status <> 'removed'
          and (%s::uuid is null or course_id = %s)
          and (%s::timestamptz is null or posted_at >= %s)
        order by posted_at desc, id limit 100
        """,
        (user_id, course_id, course_id, since, since),
    )
    return [s.Post.model_validate(r) for r in await cur.fetchall()]


async def materials(
    conn: AsyncConnection[Any],
    user_id: UUID,
    course_id: UUID,
) -> list[s.MaterialSummary]:
    cur = await conn.execute(
        "select id, title, kind, processing_status, source_url from materials "
        "where user_id = %s and course_id = %s and status <> 'removed' order by title, id",
        (user_id, course_id),
    )
    return [s.MaterialSummary.model_validate(r) for r in await cur.fetchall()]


async def syllabus_excerpt(
    conn: AsyncConnection[Any],
    user_id: UUID,
    course_id: UUID,
) -> str | None:
    cur = await conn.execute(
        "select left(ch.text, 1000) as excerpt from chunks ch join materials m "
        "on m.id = ch.material_id and m.user_id = ch.user_id "
        "where ch.user_id = %s and ch.course_id = %s and ch.is_current "
        "and m.kind = 'syllabus' and m.status <> 'removed' order by ch.id limit 1",
        (user_id, course_id),
    )
    row = await cur.fetchone()
    return row["excerpt"] if row else None


async def changes(
    conn: AsyncConnection[Any],
    user_id: UUID,
    since: datetime | None = None,
    unseen: bool = False,
) -> list[s.Change]:
    cur = await conn.execute(
        """
        select ch.id, ch.entity_type, ch.entity_id, coalesce(c.code, c.name, '') as course_code,
               ch.field, ch.old_value, ch.new_value, ch.detected_at,
               ch.seen_at is not null as seen, coalesce(i.title, p.title, m.title, '') as title
        from changes ch
        left join courses c on c.id = ch.course_id and c.user_id = ch.user_id
        left join items i on ch.entity_type = 'item' and i.id = ch.entity_id
             and i.user_id = ch.user_id
        left join posts p on ch.entity_type = 'post' and p.id = ch.entity_id
             and p.user_id = ch.user_id
        left join materials m on ch.entity_type = 'material' and m.id = ch.entity_id
             and m.user_id = ch.user_id
        where ch.user_id = %s and (%s::timestamptz is null or ch.detected_at >= %s)
          and (not %s or ch.seen_at is null)
        order by ch.detected_at desc, ch.id limit 100
        """,
        (user_id, since, since, unseen),
    )
    out = []
    for row in await cur.fetchall():
        row["summary"] = change_summary(
            row["course_code"], row.pop("title"), row["field"], row["new_value"]
        )
        out.append(s.Change.model_validate(row))
    return out


async def mark_seen(
    conn: AsyncConnection[Any],
    user_id: UUID,
    ids: list[UUID],
    now: datetime,
) -> None:
    await conn.execute(
        "update changes set seen_at = coalesce(seen_at, %s) where user_id = %s and id = any(%s)",
        (now, user_id, ids),
    )
    await conn.execute(
        "update items i set status = 'active' where i.user_id = %s and i.status = 'changed' "
        "and i.id in (select entity_id from changes where user_id = %s "
        "and entity_type = 'item' and id = any(%s)) "
        "and not exists (select 1 from changes ch where ch.user_id = i.user_id "
        "and ch.entity_type = 'item' and ch.entity_id = i.id and ch.seen_at is null)",
        (user_id, user_id, ids),
    )
