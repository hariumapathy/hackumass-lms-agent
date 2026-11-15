"""S16-lite: until cross-platform merge (S16) lands, every unmerged `item_sources` row gets its own
canonical `items` row, and items follow their single source. S16 replaces this module's logic.
"""

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

_TYPE_SQL = "coalesce((s.raw->'_normalized'->>'type')::public.item_type, 'other')"


async def merge_one_to_one(conn: AsyncConnection[Any], user_id: UUID) -> int:
    """Returns the number of items created. All SQL filtered by user_id."""
    async with conn.transaction():
        cur = await conn.execute(
            "select s.id, s.course_id, s.raw_title, s.raw_due_at, s.status, "
            f"{_TYPE_SQL} as type, (s.raw->'_normalized'->>'points')::numeric as points, "
            "s.raw->'_normalized'->>'description' as description "
            "from item_sources s where s.user_id = %s and s.item_id is null",
            (user_id,),
        )
        created = 0
        for s in await cur.fetchall():
            row = await (
                await conn.execute(
                    "insert into items (user_id, course_id, type, title, description, due_at, "
                    "points, status) values (%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                    (
                        user_id,
                        s["course_id"],
                        s["type"],
                        s["raw_title"],
                        s["description"],
                        s["raw_due_at"],
                        s["points"],
                        "active" if s["status"] == "changed" else s["status"],
                    ),
                )
            ).fetchone()
            assert row is not None
            await conn.execute(
                "update item_sources set item_id = %s where user_id = %s and id = %s",
                (row["id"], user_id, s["id"]),
            )
            created += 1
        # Single-source items follow their source (title/due/points/status).
        await conn.execute(
            "update items i set title = s.raw_title, due_at = s.raw_due_at, "
            "points = coalesce((s.raw->'_normalized'->>'points')::numeric, i.points), "
            "status = s.status, updated_at = now() from item_sources s "
            "where s.item_id = i.id and i.user_id = %s and s.user_id = %s "
            "and (i.title, i.due_at, i.status) is distinct from "
            "(s.raw_title, s.raw_due_at, s.status) "
            "and (select count(*) from item_sources x where x.item_id = i.id) = 1",
            (user_id, user_id),
        )
    return created
