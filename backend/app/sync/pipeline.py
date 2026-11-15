"""Sync pipeline (S10): connector.fetch(scope) -> normalize -> diff -> store, with run tracking.

Scheduled sync and `fetch_latest` share this code; only trigger, priority and scope differ.
Runs on an autocommit connection: each record is stored in its own transaction (one bad record is
skipped, S10 rule 10) and run/connection status updates are visible to `wait_for_sync` at once.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from pydantic import SecretStr

from app.connectors.base import (
    AuthExpired,
    Connector,
    ConnectorContext,
    NCourse,
    NItem,
    NMaterial,
    NPost,
    PlatformError,
    SyncScope,
)
from app.core.clock import Clock
from app.db.repositories import sync as repo
from app.sync.diff import changed_fields, classify, meaningful_fields, record_hash

log = logging.getLogger("app.sync")

SOURCE_TABLES = ("course_links", "item_sources", "materials", "posts")
# S16: once courses are merged, only Canvas (or a course with no Canvas link) renames it.
_RENAME_GUARD = (
    "and (%s = 'canvas' or not exists (select 1 from course_links l "
    "where l.user_id = courses.user_id and l.course_id = courses.id and l.platform = 'canvas'))"
)
# (user_id, material_id, source): source = the record's download/text/cues for S12 (not in the DB)
ProcessMaterial = Callable[[UUID, UUID, dict[str, Any]], Awaitable[None]]
ProcessPost = Callable[[UUID, UUID], Awaitable[None]]


@dataclass
class SyncOutcome:
    status: str  # succeeded | failed | needs_reconnect | retry
    stats: dict[str, int] = field(
        default_factory=lambda: {"new": 0, "changed": 0, "unchanged": 0, "removed": 0}
    )
    skipped: int = 0
    materials_to_process: list[UUID] = field(default_factory=list)
    material_sources: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    posts_to_process: list[UUID] = field(default_factory=list)
    error: str | None = None


class _Store:
    """Per-record upserts. All SQL filters by user_id."""

    def __init__(self, conn: AsyncConnection[Any], user_id: UUID, platform: str, now: datetime):
        self.conn, self.user_id, self.platform, self.now = conn, user_id, platform, now
        self.course_ids: dict[str, UUID] = {}

    async def one(self, sql: str, params: tuple[Any, ...]) -> Any:
        cur = await self.conn.execute(sql, params)  # type: ignore[arg-type]
        return await cur.fetchone()

    async def course_id(self, course_platform_id: str, rec: NCourse | None = None) -> UUID:
        """Canonical course for a platform course; created on first sight (S16 merges later)."""
        if course_platform_id in self.course_ids and rec is None:
            return self.course_ids[course_platform_id]
        row = await self.one(
            "select course_id from course_links where user_id = %s and platform = %s "
            "and platform_id = %s",
            (self.user_id, self.platform, course_platform_id),
        )
        if row:
            cid = row["course_id"]
        else:
            name = rec.name if rec else f"Course {course_platform_id}"
            row = await self.one(
                "insert into courses (user_id, name, code, term) values (%s, %s, %s, %s) "
                "returning id",
                (self.user_id, name, rec.code if rec else None, rec.term if rec else None),
            )
            cid = row["id"]
            await self.one(
                "insert into course_links (user_id, course_id, platform, platform_id, "
                "source_url, content_hash, last_synced_at) values (%s,%s,%s,%s,%s,%s,%s) "
                "returning id",
                (
                    self.user_id,
                    cid,
                    self.platform,
                    course_platform_id,
                    rec.source_url if rec else "",
                    "" if rec is None else "pending",
                    self.now,
                ),
            )
        self.course_ids[course_platform_id] = cid
        return cid

    async def existing(self, table: str, platform_id: str, cols: str) -> dict[str, Any] | None:
        return await self.one(
            f"select id, content_hash, status, {cols} from {table} "  # noqa: S608
            "where user_id = %s and platform = %s and platform_id = %s",
            (self.user_id, self.platform, platform_id),
        )

    async def change_rows(
        self, entity_type: str, entity_id: UUID, course_id: UUID, old: dict[str, Any], new: dict
    ) -> None:
        for ch in changed_fields(old, new):
            await self.one(
                "insert into changes (user_id, entity_type, entity_id, course_id, field, "
                "old_value, new_value, detected_at) values (%s,%s,%s,%s,%s,%s,%s,%s) "
                "returning id",
                (
                    self.user_id,
                    entity_type,
                    entity_id,
                    course_id,
                    ch.field,
                    Jsonb(ch.old),
                    Jsonb(ch.new),
                    self.now,
                ),
            )

    async def touch(self, table: str, row_id: UUID, extra: str = "", params: tuple = ()) -> None:
        await self.one(
            f"update {table} set last_synced_at = %s {extra} "  # noqa: S608
            "where user_id = %s and id = %s returning id",
            (self.now, *params, self.user_id, row_id),
        )

    # --- one method per record type; each returns (outcome, row id) ---------------------------
    async def course(self, rec: NCourse) -> tuple[str, UUID]:
        h = record_hash(rec)
        ex = await self.existing("course_links", rec.platform_id, "course_id")
        if ex is None or ex["content_hash"] == "":
            cid = await self.course_id(rec.platform_id, rec)
            row = await self.one(
                "update course_links set source_url = %s, content_hash = %s, last_synced_at = %s, "
                "status = 'active' where user_id = %s and platform = %s and platform_id = %s "
                "returning id",
                (rec.source_url, h, self.now, self.user_id, self.platform, rec.platform_id),
            )
            if ex is not None:  # placeholder link created by an earlier child record
                await self.one(
                    "update courses set name = %s, code = %s, term = %s "
                    "where user_id = %s and id = %s "
                    f"{_RENAME_GUARD} returning id",
                    (rec.name, rec.code, rec.term, self.user_id, cid, self.platform),
                )
            return "new", row["id"]
        self.course_ids[rec.platform_id] = ex["course_id"]
        outcome = classify(ex["content_hash"], h)
        if outcome == "changed":
            await self.touch("course_links", ex["id"], ", content_hash = %s", (h,))
            await self.one(
                "update courses set name = %s, code = coalesce(%s, code), "
                "term = coalesce(%s, term) where user_id = %s and id = %s "
                f"{_RENAME_GUARD} returning id",
                (rec.name, rec.code, rec.term, self.user_id, ex["course_id"], self.platform),
            )
        else:
            await self.touch("course_links", ex["id"], ", status = 'active'")
        return outcome, ex["id"]

    async def item(self, rec: NItem) -> tuple[str, UUID]:
        h = record_hash(rec)
        cid = await self.course_id(rec.course_platform_id)
        ex = await self.existing("item_sources", rec.platform_id, "item_id, raw")
        new_fields = meaningful_fields(rec)
        raw = {**rec.raw, "_normalized": new_fields}
        if ex is None:
            row = await self.one(
                "insert into item_sources (user_id, course_id, raw_title, raw_due_at, raw, "
                "platform, platform_id, source_url, content_hash, source_updated_at, "
                "last_synced_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                (
                    self.user_id,
                    cid,
                    rec.title,
                    rec.due_at,
                    Jsonb(_jsonable(raw)),
                    self.platform,
                    rec.platform_id,
                    rec.source_url,
                    h,
                    rec.source_updated_at,
                    self.now,
                ),
            )
            return "new", row["id"]
        outcome = classify(ex["content_hash"], h)
        if outcome == "unchanged":
            await self.touch("item_sources", ex["id"])
            return outcome, ex["id"]
        await self.one(
            "update item_sources set raw_title = %s, raw_due_at = %s, raw = %s, source_url = %s, "
            "content_hash = %s, source_updated_at = %s, last_synced_at = %s, status = 'changed' "
            "where user_id = %s and id = %s returning id",
            (
                rec.title,
                rec.due_at,
                Jsonb(_jsonable(raw)),
                rec.source_url,
                h,
                rec.source_updated_at,
                self.now,
                self.user_id,
                ex["id"],
            ),
        )
        # No `changes` row here: S16 `merge_user` compares canonical items and writes one row per
        # canonical field change (a non-canonical source moving must not alert the student).
        return outcome, ex["id"]

    async def post(self, rec: NPost) -> tuple[str, UUID]:
        h = record_hash(rec)
        cid = await self.course_id(rec.course_platform_id)
        ex = await self.existing("posts", rec.platform_id, "title, body")
        if ex is None:
            row = await self.one(
                "insert into posts (user_id, course_id, kind, title, body, author, posted_at, "
                "platform, platform_id, source_url, content_hash, source_updated_at, "
                "last_synced_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                (
                    self.user_id,
                    cid,
                    rec.kind,
                    rec.title,
                    rec.body,
                    rec.author,
                    rec.posted_at,
                    self.platform,
                    rec.platform_id,
                    rec.source_url,
                    h,
                    rec.source_updated_at,
                    self.now,
                ),
            )
            return "new", row["id"]
        outcome = classify(ex["content_hash"], h)
        if outcome == "unchanged":
            await self.touch("posts", ex["id"])
            return outcome, ex["id"]
        await self.one(
            "update posts set title = %s, body = %s, author = %s, posted_at = %s, "
            "source_url = %s, content_hash = %s, source_updated_at = %s, last_synced_at = %s, "
            "status = 'changed' where user_id = %s and id = %s returning id",
            (
                rec.title,
                rec.body,
                rec.author,
                rec.posted_at,
                rec.source_url,
                h,
                rec.source_updated_at,
                self.now,
                self.user_id,
                ex["id"],
            ),
        )
        await self.change_rows(
            "post",
            ex["id"],
            cid,
            {"title": ex["title"], "body": ex["body"]},
            {"title": rec.title, "body": rec.body},
        )
        return outcome, ex["id"]

    async def material(self, rec: NMaterial) -> tuple[str, UUID]:
        h = record_hash(rec)
        cid = await self.course_id(rec.course_platform_id)
        ex = await self.existing("materials", rec.platform_id, "title, version")
        if ex is None:
            row = await self.one(
                "insert into materials (user_id, course_id, kind, title, mime_type, recorded_at, "
                "platform, platform_id, source_url, content_hash, source_updated_at, "
                "last_synced_at, processing_status) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending') returning id",
                (
                    self.user_id,
                    cid,
                    rec.kind,
                    rec.title,
                    rec.mime_type,
                    rec.recorded_at,
                    self.platform,
                    rec.platform_id,
                    rec.source_url,
                    h,
                    rec.source_updated_at,
                    self.now,
                ),
            )
            return "new", row["id"]
        outcome = classify(ex["content_hash"], h)
        if outcome == "unchanged":
            await self.touch("materials", ex["id"])
            return outcome, ex["id"]
        # S12 bumps `version` when it stores the new file; here we only flag it for processing.
        await self.one(
            "update materials set title = %s, mime_type = %s, source_url = %s, content_hash = %s, "
            "source_updated_at = %s, last_synced_at = %s, status = 'changed', "
            "processing_status = 'pending' where user_id = %s and id = %s returning id",
            (
                rec.title,
                rec.mime_type,
                rec.source_url,
                h,
                rec.source_updated_at,
                self.now,
                self.user_id,
                ex["id"],
            ),
        )
        await self.change_rows(
            "material", ex["id"], cid, {"title": ex["title"]}, {"title": rec.title}
        )
        return outcome, ex["id"]

    async def mark_removed(
        self, seen: dict[str, set[UUID]], incomplete: set[tuple[str, str]] | None = None
    ) -> int:
        """Full scope only: rows of this platform not seen in this run -> removed (+ change).
        Courses/tables the connector reported as incompletely listed are left alone."""
        removed = 0
        # Removed item sources get no change row here: S16 marks the canonical item removed (and
        # writes its change) once all of its sources are gone.
        entity = {"materials": "material", "posts": "post"}
        skip: dict[str, list[UUID]] = {}
        for course_pid, table in incomplete or set():
            cid = await self.course_id(course_pid)
            skip.setdefault(table, []).append(cid)
        for table in SOURCE_TABLES:
            ids = list(seen.get(table, set()))
            cur = await self.conn.execute(
                f"update {table} set status = 'removed' where user_id = %s "  # noqa: S608
                "and platform = %s and status <> 'removed' and not (id = any(%s)) "
                "and not (course_id = any(%s)) returning id, course_id",
                (self.user_id, self.platform, ids, skip.get(table, [])),
            )
            rows = await cur.fetchall()
            removed += len(rows)
            if table in entity:
                for r in rows:
                    await self.one(
                        "insert into changes (user_id, entity_type, entity_id, course_id, field, "
                        "old_value, new_value, detected_at) values "
                        "(%s,%s,%s,%s,'status',%s,%s,%s) returning id",
                        (
                            self.user_id,
                            entity[table],
                            r["id"],
                            r["course_id"],
                            Jsonb("active"),
                            Jsonb("removed"),
                            self.now,
                        ),
                    )
        return removed


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


_TABLE = {NCourse: "course_links", NItem: "item_sources", NMaterial: "materials", NPost: "posts"}


async def run_sync(
    conn: AsyncConnection[Any],
    *,
    user_id: UUID,
    run_id: UUID,
    scope: SyncScope,
    connector: Connector,
    secret: str,
    clock: Clock,
    final_attempt: bool = True,
    process_material: ProcessMaterial | None = None,
    process_post: ProcessPost | None = None,
) -> SyncOutcome:
    """Run one sync. Never raises for platform problems: returns the outcome (`retry` means the
    caller should re-raise so the queue retries; only returned when `final_attempt` is False)."""
    platform = connector.platform
    now = clock.now()
    await repo.mark_run(conn, user_id, run_id, "running", now)
    out = SyncOutcome(status="succeeded")
    store = _Store(conn, user_id, platform, now)
    seen: dict[str, set[UUID]] = {t: set() for t in SOURCE_TABLES}
    ctx = ConnectorContext(
        user_id=user_id,
        platform=platform,
        secret=SecretStr(secret),
        last_success_at=await repo.last_success_at(conn, user_id, platform),
        clock=clock,
    )
    try:
        async for rec in connector.fetch(ctx, scope):
            try:
                async with conn.transaction():
                    outcome, row_id = await getattr(store, rec.record)(rec)
            except (AuthExpired, PlatformError):
                raise
            except Exception as exc:  # noqa: BLE001  (S10 rule 10: skip one bad record)
                out.skipped += 1
                log.warning(
                    "sync: skipped %s %s: %s", rec.record, rec.platform_id, type(exc).__name__
                )
                continue
            seen[_TABLE[type(rec)]].add(row_id)
            out.stats[outcome] += 1
            if isinstance(rec, NMaterial) and outcome in {"new", "changed"}:
                out.materials_to_process.append(row_id)
                out.material_sources[row_id] = rec.model_dump(
                    mode="json", include={"download", "text", "cues"}
                )
            if isinstance(rec, NPost) and outcome in {"new", "changed"}:
                out.posts_to_process.append(row_id)
        if scope.kind == "full":
            async with conn.transaction():
                out.stats["removed"] = await store.mark_removed(seen, ctx.incomplete)
    except AuthExpired:
        out.status, out.error = "needs_reconnect", "Your sign-in for this site expired."
        await repo.set_connection_status(
            conn, user_id, platform, "needs_reconnect", error=out.error
        )
    except PlatformError as exc:
        if not final_attempt:
            out.status, out.error = "retry", str(exc)[:500]
            await repo.mark_run(conn, user_id, run_id, "running", clock.now(), out.stats)
            return out
        out.status, out.error = "failed", str(exc)[:500]
        await repo.set_connection_status(conn, user_id, platform, "error", error=out.error)
    except Exception as exc:  # noqa: BLE001
        out.status, out.error = "failed", f"{type(exc).__name__}"
        log.exception("sync: run %s failed", run_id)
        await repo.set_connection_status(conn, user_id, platform, "error", error=out.error)
    finished = clock.now()
    if out.status == "succeeded":
        await repo.set_connection_status(conn, user_id, platform, "active", synced_at=finished)
        if process_material:
            for material_id in out.materials_to_process:
                await process_material(user_id, material_id, out.material_sources[material_id])
        if process_post:
            for post_id in out.posts_to_process:
                await process_post(user_id, post_id)
    await repo.mark_run(conn, user_id, run_id, out.status, finished, out.stats, out.error)
    return out
