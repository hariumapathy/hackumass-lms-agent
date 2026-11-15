"""Disconnect a platform (S13 rule 6, S13-T06): delete the connection and its secret (cascade),
cancel the platform's queued/running sync runs, and drop its queued sync jobs.

Already-synced course data stays (the student can still ask about it; "Delete my data" in S20
removes everything). Called by `DELETE /connections/{platform}`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.core.clock import Clock, SystemClock

DISCONNECTED = "Disconnected by the student."


async def disconnect_platform(
    conn: AsyncConnection[Any], user_id: UUID, platform: str, *, clock: Clock | None = None
) -> bool:
    """Returns True if a connection existed. Idempotent."""
    now: datetime = (clock or SystemClock()).now()
    async with conn.transaction():
        cur = await conn.execute(
            "delete from connections where user_id = %s and platform = %s returning id",
            (user_id, platform),
        )
        existed = await cur.fetchone() is not None
        await conn.execute(
            "update sync_runs set status = 'failed', error = %s, finished_at = %s "
            "where user_id = %s and platform = %s and status in ('queued', 'running')",
            (DISCONNECTED, now, user_id, platform),
        )
        # Queued (not yet started) sync jobs for this user + platform. A job already running
        # finds no secret and ends as failed.
        await conn.execute(
            "delete from procrastinate_jobs where status = 'todo' and task_name = 'sync_platform' "
            "and args->'job'->>'user_id' = %s and args->'job'->>'platform' = %s",
            (str(user_id), platform),
        )
    return existed
