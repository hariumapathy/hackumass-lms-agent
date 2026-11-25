"""S45 bounded recovery; never assume a still-active worker has relinquished its work."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.core.clock import SystemClock
from app.core.errors import AppError
from app.db.deletion import user_work
from app.db.repositories import processing as repo
from app.sync.intents import intent_lock


async def recover_stalled(conn: AsyncConnection[Any], *, user_id: UUID | None = None) -> int:
    rows = await (
        await conn.execute(
            "select id,user_id,revision from processing_intents where completed_at is null "
            "and blocked_reason is null and dispatched_at is not null "
            "and coalesce(last_started_at,dispatched_at)<now()-interval '10 minutes' "
            "and (%s::uuid is null or user_id=%s) order by created_at limit 100",
            (user_id, user_id),
        )
    ).fetchall()
    count = 0
    for row in rows:
        uid, iid, rev = row["user_id"], row["id"], row["revision"]
        try:
            async with user_work(conn, uid), intent_lock(conn, iid, wait=False) as locked:
                if not locked:
                    continue
                current = await repo.get(conn, uid, iid)
                if (
                    not current
                    or current["revision"] != rev
                    or current["completed_at"]
                    or current["blocked_reason"]
                    or current["dispatched_at"] is None
                ):
                    continue
                started = current["last_started_at"] or current["dispatched_at"]
                if started >= SystemClock().now() - timedelta(minutes=10):
                    continue
                if await repo.active_job(conn, uid, iid, rev):
                    continue
                if current["last_started_at"] is None:
                    if await repo.claim(conn, uid, iid, rev) is None:
                        continue
                count += int(await repo.fail(conn, uid, iid, rev, "retry", "worker_interrupted"))
        except AppError:
            continue
    return count


async def recover_legacy_posts(conn: AsyncConnection[Any], *, user_id: UUID | None = None) -> int:
    rows = await (
        await conn.execute(
            "select p.user_id,p.id from posts p where p.status<>'removed' "
            "and (%s::uuid is null or p.user_id=%s) "
            "and not exists(select 1 from chunks ch where "
            "ch.user_id=p.user_id and ch.post_id=p.id and ch.is_current) "
            "and not exists(select 1 from processing_intents i where "
            "i.user_id=p.user_id and i.post_id=p.id) "
            "order by p.created_at limit 100",
            (user_id, user_id),
        )
    ).fetchall()
    count = 0
    for row in rows:
        uid, pid = row["user_id"], row["id"]
        try:
            async with user_work(conn, uid):
                active = await (
                    await conn.execute(
                        "select id from procrastinate_jobs where task_name='process_post' "
                        "and status in ('todo','doing') and args->>'user_id'=%s and "
                        "args->>'post_id'=%s limit 1",
                        (str(uid), str(pid)),
                    )
                ).fetchone()
                if active:
                    continue
                inserted = await (
                    await conn.execute(
                        "insert into processing_intents(user_id,post_id,source_hash) "
                        "select user_id,id,content_hash from posts p where user_id=%s and "
                        "id=%s and status<>'removed' "
                        "and not exists(select 1 from chunks ch where "
                        "ch.user_id=p.user_id and ch.post_id=p.id and ch.is_current) "
                        "on conflict(post_id) do nothing returning id",
                        (uid, pid),
                    )
                ).fetchone()
                count += int(inserted is not None)
        except AppError:
            continue
    return count


async def recover_legacy_materials(
    conn: AsyncConnection[Any], *, user_id: UUID | None = None, enqueue=None
) -> int:
    from app.connectors.base import SyncScope
    from app.db.repositories import sync as sync_repo
    from app.sync.jobs import enqueue_sync

    rows = await (
        await conn.execute(
            "select m.user_id,m.id from materials m left join "
            "processing_intents i on i.material_id=m.id "
            "and i.user_id=m.user_id where m.platform='canvas' and m.kind in ('file','syllabus') "
            "and m.status<>'removed' and m.processing_status in ('pending','failed','processing') "
            "and (%s::uuid is null or m.user_id=%s) and (i.id is null or "
            "(i.blocked_reason='source_refresh' "
            "and i.attempts<4 and i.next_attempt_at<=now())) order by m.created_at limit 20",
            (user_id, user_id),
        )
    ).fetchall()
    count = 0
    for row in rows:
        uid, mid = row["user_id"], row["id"]
        try:
            async with user_work(conn, uid):
                material = await (
                    await conn.execute(
                        "select m.id,m.platform_id,m.content_hash,l.platform_id as "
                        "course_pid from materials m "
                        "join course_links l on l.course_id=m.course_id and l.user_id=m.user_id "
                        "and l.platform=m.platform and l.status<>'removed' join "
                        "connections c on c.user_id=m.user_id "
                        "and c.platform=m.platform join connection_secrets s on "
                        "s.connection_id=c.id "
                        "where m.user_id=%s and m.id=%s and m.status<>'removed' and "
                        "c.status in ('active','error') "
                        "order by l.created_at limit 1",
                        (uid, mid),
                    )
                ).fetchone()
                if not material:
                    continue
                active = await (
                    await conn.execute(
                        "select id from procrastinate_jobs where task_name='process_material' "
                        "and status in ('todo','doing') and args->>'user_id'=%s and "
                        "args->>'material_id'=%s limit 1",
                        (str(uid), str(mid)),
                    )
                ).fetchone()
                if active:
                    continue
                # A payload-free placeholder waits for real metadata;
                # it cannot be processed using a guessed file reference.
                await conn.execute(
                    "insert into "
                    "processing_intents(user_id,material_id,source_hash,"
                    "blocked_reason,last_error_code) "
                    "select user_id,id,content_hash,'source_refresh','missing_source' "
                    "from materials "
                    "where user_id=%s and id=%s on conflict(material_id) do nothing",
                    (uid, mid),
                )
                existing = await (
                    await conn.execute(
                        "select id from processing_intents where user_id=%s and material_id=%s",
                        (uid, mid),
                    )
                ).fetchone()
                if not existing:
                    continue
                iid = existing["id"]
                async with intent_lock(conn, iid, wait=False) as locked:
                    if not locked:
                        continue
                    scope = SyncScope(
                        kind="material",
                        course_platform_id=material["course_pid"],
                        platform_id=material["platform_id"],
                    )
                    if await sync_repo.find_open_run(
                        conn, uid, "canvas", scope.model_dump(mode="json")
                    ):
                        continue
                    claimed = await (
                        await conn.execute(
                            "update processing_intents set "
                            "attempts=attempts+1,last_started_at=now(), "
                            "next_attempt_at=now()+(case attempts when 0 then 30 when 1 then "
                            "120 else 600 end)*interval '1 second', "
                            "blocked_reason=case when attempts+1>=4 then 'exhausted' else "
                            "'source_refresh' end, "
                            "last_error_code=case when attempts+1>=4 then "
                            "'source_refresh_exhausted' else 'source_refresh_pending' end "
                            "where user_id=%s and id=%s and blocked_reason='source_refresh' "
                            "and attempts<4 and next_attempt_at<=now() returning id",
                            (uid, iid),
                        )
                    ).fetchone()
                    if not claimed:
                        continue
                    try:
                        await (enqueue or enqueue_sync)(conn, uid, "canvas", scope, "schedule")
                        count += 1
                    except Exception:
                        # Persisted counter/backoff bounds even failed/no-record refresh outcomes.
                        pass
        except AppError:
            continue
    return count
