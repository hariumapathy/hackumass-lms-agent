"""Profile + account-level queries (S20). Table shapes from S01 (`profiles`, and every user table
for "delete my data")."""

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.sql import SQL, Identifier

from app.db.models import Profile

# Children before parents. `connection_secrets` has no user_id: it cascades from `connections`.
USER_TABLES = (
    "misses",
    "sync_runs",
    "calendar_feeds",
    "study_blocks",
    "study_sets",
    "agent_runs",
    "messages",
    "conversations",
    "changes",
    "chunks",
    "posts",
    "materials",
    "item_sources",
    "items",
    "course_links",
    "courses",
    "connections",
    "profiles",
)

INTERNAL_USER_TABLES = ("processing_intents",)

_PROFILE_COLS = "user_id, display_name, timezone, model_choice, created_at"


async def get_profile(conn: AsyncConnection, user_id: UUID) -> Profile | None:
    cur = await conn.execute(
        f"select {_PROFILE_COLS} from profiles where user_id = %s",
        (user_id,),
    )
    row = await cur.fetchone()
    return Profile.model_validate(row) if row else None


async def ensure_profile(conn: AsyncConnection, user_id: UUID, email: str | None) -> Profile:
    """Create the profile with defaults on first request; return the existing one otherwise."""
    display_name = email.split("@")[0] if email else None
    await conn.execute(
        "insert into profiles (user_id, display_name) values (%s, %s) "
        "on conflict (user_id) do nothing",
        (user_id, display_name),
    )
    profile = await get_profile(conn, user_id)
    assert profile is not None
    return profile


async def update_profile(conn: AsyncConnection, user_id: UUID, **fields: Any) -> Profile | None:
    allowed = {k: v for k, v in fields.items() if k in {"display_name", "timezone", "model_choice"}}
    if allowed:
        assignments = SQL(", ").join(SQL("{} = %s").format(Identifier(k)) for k in allowed)
        await conn.execute(
            SQL("update profiles set {} where user_id = %s").format(assignments),
            (*allowed.values(), user_id),
        )
    return await get_profile(conn, user_id)


async def delete_user_data(conn: AsyncConnection, user_id: UUID) -> None:
    """Delete every row the student owns (S20 rule 9). Storage objects and queued jobs are
    removed by the caller (S12 storage helper / S10 job queue)."""
    async with conn.transaction():
        for table in (*INTERNAL_USER_TABLES, *USER_TABLES):
            await conn.execute(
                SQL("delete from {} where user_id = %s").format(Identifier(table)), (user_id,)
            )
