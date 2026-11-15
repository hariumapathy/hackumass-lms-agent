"""Read queries for the agent tools (S21) on the S01 schema. Every function is
`fn(conn, user_id, ...)` and filters by user_id (the backend bypasses RLS)."""

from datetime import datetime
from typing import Any, LiteralString, cast
from uuid import UUID

from psycopg import AsyncConnection

RRF_K = 60
CANDIDATES = 30
SIMILARITY_FLOOR = 0.2

# tool `kind` -> SQL condition on the joined row (m = materials, p = posts)
_KIND_SQL = {
    "slides": "m.kind in ('file', 'page')",
    "transcript": "m.kind = 'transcript'",
    "syllabus": "m.kind = 'syllabus'",
    "post": "ch.post_id is not null",
    "any": "true",
}

_CHUNK_COLUMNS = """
ch.id as chunk_id, ch.course_id, coalesce(c.code, c.name) as course_code,
       ch.material_id::text as material_id, coalesce(m.title, p.title) as title,
       case when ch.post_id is not null then 'post'
            when m.kind = 'transcript' then 'transcript'
            when m.kind = 'syllabus' then 'syllabus'
            when m.kind = 'page' then 'page'
            else 'slides' end as kind,
       coalesce(m.platform, p.platform)::text as platform, p.kind::text as post_kind,
       ch.page, ch.start_s, ch.end_s, ch.text,
       coalesce(m.recorded_at, p.posted_at) as posted_or_recorded_at,
       coalesce(m.source_url, p.source_url) as source_url,
       coalesce(m.last_synced_at, p.last_synced_at) as last_synced_at,
       case when coalesce(m.status, p.status) = 'removed' then 'removed'
            when not ch.is_current or coalesce(m.status, p.status) = 'changed' then 'changed'
            else 'current' end as status
"""
_CHUNK_FROM = """
from chunks ch
join courses c on c.id = ch.course_id and c.user_id = ch.user_id
left join materials m on m.id = ch.material_id and m.user_id = ch.user_id
left join posts p on p.id = ch.post_id and p.user_id = ch.user_id
"""
_CHUNK_SELECT = f"select {_CHUNK_COLUMNS} {_CHUNK_FROM}"


async def list_courses(conn: AsyncConnection[Any], user_id: UUID) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "select id, coalesce(code, name) as code, name from courses where user_id = %s "
        "order by code",
        (user_id,),
    )
    return list(await cur.fetchall())


async def list_items(
    conn: AsyncConnection[Any], user_id: UUID, course_id: UUID | None, item_type: str | None
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        """
        select i.id, i.course_id, coalesce(c.code, c.name) as course_code, i.type::text as type,
               i.title, i.due_at, i.points, i.status::text as status,
               coalesce(array_agg(distinct s.platform::text)
                        filter (where s.platform is not null), '{}') as platforms,
               coalesce(array_agg(distinct ch.field)
                        filter (where ch.field is not null), '{}') as changed_fields
        from items i
        join courses c on c.id = i.course_id and c.user_id = i.user_id
        left join item_sources s on s.item_id = i.id and s.user_id = i.user_id
        left join changes ch on ch.entity_id = i.id and ch.user_id = i.user_id
             and ch.entity_type = 'item' and ch.detected_at > now() - interval '14 days'
        where i.user_id = %s and i.status <> 'removed'
          and (%s::uuid is null or i.course_id = %s::uuid)
          and (%s::text is null or i.type::text = %s::text)
        group by i.id, c.code, c.name
        """,
        (user_id, course_id, course_id, item_type, item_type),
    )
    return list(await cur.fetchall())


async def list_changes(
    conn: AsyncConnection[Any], user_id: UUID, since: datetime, course_id: UUID | None
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        """
        select ch.course_id, coalesce(c.code, c.name, '') as course_code, ch.entity_type,
               ch.field, ch.old_value, ch.new_value, ch.detected_at,
               coalesce(i.title, p.title, m.title) as entity_title
        from changes ch
        left join courses c on c.id = ch.course_id and c.user_id = ch.user_id
        left join items i on ch.entity_type = 'item' and i.id = ch.entity_id
             and i.user_id = ch.user_id
        left join posts p on ch.entity_type = 'post' and p.id = ch.entity_id
             and p.user_id = ch.user_id
        left join materials m on ch.entity_type = 'material' and m.id = ch.entity_id
             and m.user_id = ch.user_id
        where ch.user_id = %s and ch.detected_at >= %s
          and (%s::uuid is null or ch.course_id = %s::uuid)
        order by ch.detected_at desc
        limit 100
        """,
        (user_id, since, course_id, course_id),
    )
    return list(await cur.fetchall())


def _filters(kind: str, source: str | None, course_id: UUID | None) -> tuple[str, list[Any]]:
    sql = f" and ({_KIND_SQL.get(kind, 'true')})"
    params: list[Any] = []
    if course_id:
        sql += " and ch.course_id = %s"
        params.append(course_id)
    if source:
        sql += " and coalesce(m.platform, p.platform)::text = %s"
        params.append(source)
    return sql, params


async def search_chunks(
    conn: AsyncConnection[Any],
    user_id: UUID,
    query: str,
    query_vec: str | None,
    course_id: UUID | None,
    kind: str,
    source: str | None,
    k: int,
) -> list[dict[str, Any]]:
    """Hybrid search (S21 rule 2): vector top 30 + full-text top 30 -> RRF (k=60) -> top k.
    Vector hits under the similarity floor are ignored (rule 8). SQL text is built only from the
    fixed fragments in this module; every value is a bound parameter."""
    where, params = _filters(kind, source, course_id)
    base = f"where ch.user_id = %s and ch.is_current{where}"
    ranks: dict[int, float] = {}
    rows: dict[int, dict[str, Any]] = {}
    if query_vec is not None:
        vector_sql = (
            f"select 1 - (ch.embedding <=> %s::extensions.vector) as sim, {_CHUNK_COLUMNS} "
            f"{_CHUNK_FROM} {base} "
            f"order by ch.embedding <=> %s::extensions.vector limit {CANDIDATES}"
        )
        cur = await conn.execute(
            cast(LiteralString, vector_sql), (query_vec, user_id, *params, query_vec)
        )
        for rank, row in enumerate(r for r in await cur.fetchall() if r["sim"] >= SIMILARITY_FLOOR):
            ranks[row["chunk_id"]] = ranks.get(row["chunk_id"], 0) + 1 / (RRF_K + rank + 1)
            rows[row["chunk_id"]] = row
    text_sql = (
        f"{_CHUNK_SELECT} {base} and ch.tsv @@ websearch_to_tsquery('english', %s) "
        f"order by ts_rank(ch.tsv, websearch_to_tsquery('english', %s)) desc limit {CANDIDATES}"
    )
    cur = await conn.execute(cast(LiteralString, text_sql), (user_id, *params, query, query))
    for rank, row in enumerate(await cur.fetchall()):
        ranks[row["chunk_id"]] = ranks.get(row["chunk_id"], 0) + 1 / (RRF_K + rank + 1)
        rows.setdefault(row["chunk_id"], row)
    best = sorted(ranks, key=lambda cid: -ranks[cid])[:k]
    return [rows[cid] for cid in best]


async def material_chunks(
    conn: AsyncConnection[Any], user_id: UUID, material_id: UUID
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        f"{_CHUNK_SELECT} where ch.user_id = %s and ch.is_current and ch.material_id = %s "
        "order by ch.page nulls last, ch.start_s nulls last, ch.id",
        (user_id, material_id),
    )
    return list(await cur.fetchall())


async def chunks_by_id(
    conn: AsyncConnection[Any], user_id: UUID, ids: list[int]
) -> list[dict[str, Any]]:
    """Only this student's chunks resolve (S23-T02): other users' IDs simply don't come back."""
    if not ids:
        return []
    cur = await conn.execute(
        f"{_CHUNK_SELECT} where ch.user_id = %s and ch.id = any(%s)", (user_id, ids)
    )
    return list(await cur.fetchall())


async def record_miss(
    conn: AsyncConnection[Any], user_id: UUID, tool: str, query: str, course_id: UUID | None
) -> None:
    await conn.execute(
        "insert into misses (user_id, tool, query, course_id) values (%s, %s, %s, %s)",
        (user_id, tool, query[:500], course_id),
    )


async def course_platform_id(
    conn: AsyncConnection[Any], user_id: UUID, course_id: UUID, platform: str
) -> str | None:
    cur = await conn.execute(
        "select platform_id from course_links where user_id = %s and course_id = %s "
        "and platform = %s and status <> 'removed' limit 1",
        (user_id, course_id, platform),
    )
    row = await cur.fetchone()
    return row["platform_id"] if row else None
