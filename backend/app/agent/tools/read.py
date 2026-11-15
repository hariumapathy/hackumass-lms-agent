"""The six read tools (S21). Plain `async def tool(ctx, args) -> ToolResult`; no SDK imports.

They read only `ctx.data` (one student's data, see `data.py`), return local + relative times,
wrap post text as untrusted, and attach coverage so the model knows when to call fetch_latest.
"""

from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.agent.tools.args import (
    MAX_PAGES,
    MAX_SECONDS,
    FetchLatestArgs,
    GetChangesArgs,
    GetCourseOverviewArgs,
    GetItemsArgs,
    GetMaterialArgs,
    SearchMaterialsArgs,
)
from app.agent.tools.context import RunCtx
from app.agent.tools.courses import CourseRef, resolve_course
from app.agent.tools.coverage import PLATFORMS, compute_coverage
from app.agent.tools.data import ChunkRow, ItemRow, ToolData
from app.agent.tools.results import ToolResult, wrap_post_text
from app.agent.tools.timefmt import local_time, relative_time

MAX_ITEMS = 50
MAX_CHANGES = 30


def _data(ctx: RunCtx) -> ToolData:
    if ctx.data is None:
        raise RuntimeError("RunCtx.data is not set")
    return ctx.data


async def _course(ctx: RunCtx, query: str | None) -> tuple[CourseRef | None, str | None]:
    """(course, None) if resolved or not asked for; (None, note) if unknown/ambiguous."""
    if not query:
        return None, None
    resolved = resolve_course(await _data(ctx).courses(), query)
    return resolved.course, resolved.note


async def _result(
    ctx: RunCtx, results: list[dict], note: str | None = None, source: str | None = None
) -> ToolResult:
    coverage = compute_coverage(await _data(ctx).connections(), ctx.clock.now(), source)
    return ToolResult(results=results, coverage=coverage, note=note)


def _clock_s(seconds: int) -> str:
    return (
        f"{seconds // 60}:{seconds % 60:02d}"
        if seconds < 3600
        else (f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}")
    )


def _item(row: ItemRow, ctx: RunCtx) -> dict:
    now = ctx.clock.now()
    return {
        "item_id": str(row.id),
        "course": row.course_code,
        "type": row.type,
        "title": row.title,
        "due_local": local_time(row.due_at, ctx.timezone) if row.due_at else None,
        "due_in": relative_time(row.due_at, now) if row.due_at else "no due date",
        "points": row.points,
        "status": row.status,
        "submitted": row.submitted,
        "changed_fields": row.changed_fields,
        "sources": row.platforms,
    }


def _chunk(row: ChunkRow, ctx: RunCtx) -> dict:
    anchor = (
        f"p.{row.page}"
        if row.page is not None
        else (_clock_s(row.start_s) if row.start_s is not None else None)
    )
    header = " · ".join(x for x in (row.course_code, row.title, anchor) if x)
    body = wrap_post_text(row.post_kind or "", row.text) if row.kind == "post" else row.text
    out: dict = {
        "chunk_id": row.chunk_id,
        "course": row.course_code,
        "title": row.title,
        "kind": row.kind,
        "text": f"[{header}]\n{body}",
    }
    if row.page is not None:
        out["page"] = row.page
    if row.start_s is not None:
        out["time"] = _clock_s(row.start_s)
    if row.posted_or_recorded_at:
        out["posted_or_recorded_local"] = local_time(row.posted_or_recorded_at, ctx.timezone)
    if row.material_id:
        out["material_id"] = row.material_id
    return out


def _local_bound(day, tz: str, end: bool) -> datetime:  # noqa: ANN001
    return datetime.combine(day, time.max if end else time.min, ZoneInfo(tz))


async def get_items(ctx: RunCtx, args: GetItemsArgs) -> ToolResult:
    course, note = await _course(ctx, args.course)
    if note:
        return await _result(ctx, [], note)
    now = ctx.clock.now()
    rows = await _data(ctx).items(course.id if course else None, args.type)
    if args.from_date:
        start = _local_bound(args.from_date, ctx.timezone, end=False)
        rows = [r for r in rows if r.due_at and r.due_at >= start]
    if args.to_date:
        stop = _local_bound(args.to_date, ctx.timezone, end=True)
        rows = [r for r in rows if r.due_at and r.due_at <= stop]
    if not args.include_past:
        rows = [r for r in rows if r.due_at is None or r.due_at >= now]
    rows.sort(key=lambda r: (r.due_at is None, r.due_at or now))
    note = None if rows else "Nothing found. If you expected something, consider fetch_latest."
    return await _result(ctx, [_item(r, ctx) for r in rows[:MAX_ITEMS]], note)


async def get_changes(ctx: RunCtx, args: GetChangesArgs) -> ToolResult:
    course, note = await _course(ctx, args.course)
    if note:
        return await _result(ctx, [], note)
    since = ctx.clock.now() - timedelta(days=args.since_days)
    rows = await _data(ctx).changes(since, course.id if course else None)
    rows.sort(key=lambda r: r.detected_at, reverse=True)
    results = [
        {
            "course": r.course_code,
            "entity": r.entity_type,
            "field": r.field,
            "old": _fmt_value(r.old_value, ctx),
            "new": _fmt_value(r.new_value, ctx),
            "detected_local": local_time(r.detected_at, ctx.timezone),
            "summary": r.summary,
        }
        for r in rows[:MAX_CHANGES]
    ]
    return await _result(ctx, results)


def _fmt_value(value: object, ctx: RunCtx) -> object:
    """Datetimes (as ISO strings) become local times so the model never converts zones."""
    if isinstance(value, str):
        try:
            return local_time(datetime.fromisoformat(value), ctx.timezone)
        except ValueError:
            return value
    return value


async def search_materials(ctx: RunCtx, args: SearchMaterialsArgs) -> ToolResult:
    course, note = await _course(ctx, args.course)
    if note:
        return await _result(ctx, [], note, args.source)
    data = _data(ctx)
    rows = await data.search(
        args.query, course.id if course else None, args.kind, args.source, args.k
    )
    if not rows:
        await data.record_miss("search_materials", args.query, course.id if course else None)
        hint = f"fetch_latest(course='{course.code}')" if course else "fetch_latest()"
        return await _result(
            ctx, [], f"No results. Consider {hint}, then search again.", args.source
        )
    return await _result(ctx, [_chunk(r, ctx) for r in rows], source=args.source)


async def get_material(ctx: RunCtx, args: GetMaterialArgs) -> ToolResult:
    rows = await _data(ctx).material_chunks(args.material_id)
    if not rows:
        return await _result(
            ctx,
            [],
            f"Unknown material '{args.material_id}'. Use an id from search_materials results.",
        )
    if args.pages:
        first, _, last = args.pages.partition("-")
        lo, hi = int(first), int(last or first)
        rows = [r for r in rows if r.page is not None and lo <= r.page <= hi]
    elif args.start_s is not None or args.end_s is not None:
        lo = args.start_s or 0
        hi = args.end_s if args.end_s is not None else lo + MAX_SECONDS
        rows = [r for r in rows if r.start_s is not None and lo <= r.start_s <= hi]
    else:
        rows = rows[:MAX_PAGES]
    return await _result(ctx, [_chunk(r, ctx) for r in rows])


async def get_course_overview(ctx: RunCtx, args: GetCourseOverviewArgs) -> ToolResult:
    course, note = await _course(ctx, args.course)
    if course is None:
        return await _result(ctx, [], note)
    data = _data(ctx)
    now = ctx.clock.now()
    syllabus = await data.search("syllabus grading exam policy", course.id, "syllabus", None, 4)
    items = [r for r in await data.items(course.id, None) if r.due_at and r.due_at >= now]
    items.sort(key=lambda r: r.due_at or now)
    platforms = sorted({p for r in await data.items(course.id, None) for p in r.platforms})
    overview = {
        "course_id": str(course.id),
        "code": course.code,
        "name": course.name,
        "platforms": platforms,
        "syllabus_chunks": [
            {"chunk_id": r.chunk_id, "text": _chunk(r, ctx)["text"]} for r in syllabus
        ],
        "upcoming": [_item(r, ctx) for r in items[:5]],
        "counts": {"upcoming_items": len(items)},
    }
    return await _result(ctx, [overview])


async def fetch_latest(ctx: RunCtx, args: FetchLatestArgs) -> ToolResult:
    course, note = await _course(ctx, args.course)
    if note:
        return await _result(ctx, [], note, args.source)
    data = _data(ctx)
    by_platform = {c.platform: c for c in await data.connections() if c.status != "disconnected"}
    wanted = [args.source] if args.source else list(PLATFORMS)
    if args.source and args.source not in by_platform:
        return await _result(ctx, [{"status": "not_connected"}], source=args.source)
    usable = [p for p in wanted if p in by_platform and by_platform[p].status != "needs_reconnect"]
    if not usable:
        status = "needs_reconnect" if any(p in by_platform for p in wanted) else "not_connected"
        return await _result(ctx, [{"status": status}], source=args.source)
    course_id: UUID | None = course.id if course and args.what == "course" else None
    outcome = await data.request_sync(usable, course_id, timeout_s=15)
    return await _result(
        ctx,
        [
            {
                "status": outcome.status,
                "added": outcome.added,
                "updated": outcome.updated,
                "sync_run_ids": outcome.sync_run_ids,
            }
        ],
        source=args.source,
    )
