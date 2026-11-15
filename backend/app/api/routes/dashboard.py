"""Today, courses, items, changes and citations (S23/S32); mock backup is explicit."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.api.routes.connections import source_statuses
from app.core.errors import AppError, not_found
from app.core.settings import get_settings
from app.db.pool import connection
from app.db.repositories import dashboard as repo
from app.db.repositories import profiles

router = APIRouter(tags=["dashboard"])
User = Annotated[UserCtx, Depends(current_user)]


@router.get("/today", response_model=s.Today)
async def today(
    user: User, request: Request, day: Annotated[date | None, Query(alias="date")] = None
) -> s.Today:
    if get_settings().data_source == "db":
        now = request.app.state.clock.now()
        async with connection() as conn:
            profile = await profiles.ensure_profile(conn, user.user_id, user.email)
            tz = ZoneInfo(profile.timezone)
            local_today = day or now.astimezone(tz).date()
            start = datetime.combine(local_today, datetime.min.time(), tz)
            # Construct local midnights before converting to UTC: DST days aren't always 24h.
            end = datetime.combine(local_today + timedelta(days=1), datetime.min.time(), tz)
            week_end = datetime.combine(local_today + timedelta(days=8), datetime.min.time(), tz)
            at = now if day is None or day == now.astimezone(tz).date() else start.astimezone(UTC)
            items = await repo.items(conn, user.user_id, now)
            return s.Today(
                date=local_today,
                timezone=profile.timezone,
                overdue=[
                    i
                    for i in items
                    if i.due_at and at - timedelta(days=7) <= i.due_at < at and not i.submitted
                ],
                due_today=[i for i in items if i.due_at and at <= i.due_at < end],
                due_this_week=[i for i in items if i.due_at and end <= i.due_at < week_end],
                upcoming_exams=[
                    i
                    for i in items
                    if i.type == "exam" and i.due_at and at <= i.due_at <= at + timedelta(days=30)
                ],
                changes=await repo.changes(conn, user.user_id, now - timedelta(days=14), True),
                new_posts=await repo.posts(conn, user.user_id, since=now - timedelta(hours=72)),
                sources=await source_statuses(conn, user.user_id, now),
            )
    tz = ZoneInfo(mock.TZ)
    now = datetime.now(UTC)
    local_today = day or now.astimezone(tz).date()
    end_of_day = datetime.combine(local_today + timedelta(days=1), datetime.min.time(), tz)
    week_end = end_of_day + timedelta(days=7)
    items = [i for i in mock.items() if i.due_at is not None]
    return s.Today(
        date=local_today,
        timezone=mock.TZ,
        overdue=[i for i in items if i.due_at and i.due_at < now and not i.submitted],
        due_today=[i for i in items if i.due_at and now <= i.due_at < end_of_day],
        due_this_week=[i for i in items if i.due_at and end_of_day <= i.due_at < week_end],
        upcoming_exams=[i for i in items if i.type == "exam" and i.due_at and i.due_at >= now],
        changes=[c for c in mock.changes() if not c.seen],
        new_posts=mock.posts(),
        sources=mock.sources(),
    )


@router.get("/courses", response_model=list[s.CourseSummary])
async def courses(user: User, request: Request) -> list[s.CourseSummary]:
    if get_settings().data_source == "db":
        async with connection() as conn:
            return await repo.courses(conn, user.user_id, request.app.state.clock.now())
    return mock.course_summaries()


@router.get("/courses/{course_id}", response_model=s.CourseDetail)
async def course(course_id: UUID, user: User, request: Request) -> s.CourseDetail:
    if get_settings().data_source == "db":
        now = request.app.state.clock.now()
        async with connection() as conn:
            summary = next(
                (c for c in await repo.courses(conn, user.user_id, now) if c.id == course_id), None
            )
            if summary is None:
                raise not_found("Course")
            return s.CourseDetail(
                **summary.model_dump(),
                items=await repo.items(conn, user.user_id, now, course_id),
                recent_posts=await repo.posts(conn, user.user_id, course_id),
                materials=await repo.materials(conn, user.user_id, course_id),
                syllabus_excerpt=await repo.syllabus_excerpt(conn, user.user_id, course_id),
            )
    detail = mock.course_detail(course_id)
    if detail is None:
        raise not_found("Course")
    return detail


@router.get("/items", response_model=list[s.Item])
async def list_items(
    user: User,
    request: Request,
    course_id: UUID | None = None,
    type: s.ItemType | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[s.Item]:
    if get_settings().data_source == "db":
        async with connection() as conn:
            return (
                await repo.items(
                    conn, user.user_id, request.app.state.clock.now(), course_id, type, from_, to
                )
            )[:200]
    out = mock.items()
    if course_id:
        out = [i for i in out if i.course_id == course_id]
    if type:
        out = [i for i in out if i.type == type]
    if from_:
        out = [i for i in out if i.due_at and i.due_at >= from_]
    if to:
        out = [i for i in out if i.due_at and i.due_at <= to]
    return out[:200]


@router.get("/changes", response_model=list[s.Change])
async def list_changes(
    user: User, since: datetime | None = None, unseen: bool = False
) -> list[s.Change]:
    if get_settings().data_source == "db":
        async with connection() as conn:
            return await repo.changes(conn, user.user_id, since, unseen)
    out = mock.changes()
    if since:
        out = [c for c in out if c.detected_at >= since]
    if unseen:
        out = [c for c in out if not c.seen]
    return out


@router.post("/changes/seen", status_code=204)
async def mark_changes_seen(body: s.ChangesSeenRequest, user: User, request: Request) -> Response:
    if get_settings().data_source == "db":
        async with connection() as conn:
            await repo.mark_seen(conn, user.user_id, body.ids, request.app.state.clock.now())
    return Response(status_code=204)


@router.get("/citations", response_model=list[s.Citation])
async def citations(
    user: User, ids: str = Query(description="Comma-separated chunk IDs")
) -> list[s.Citation]:
    try:
        chunk_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError as exc:
        raise AppError(
            "validation_error", "ids must be comma-separated integers", status=422
        ) from exc
    if get_settings().data_source == "db":
        from app.agent.citations import resolve_rows
        from app.agent.tools.data import ChunkRow
        from app.db.repositories.agent import chunks_by_id

        async with connection() as conn:
            rows = await chunks_by_id(conn, user.user_id, chunk_ids)
        return resolve_rows(
            [ChunkRow.model_validate(r) for r in rows], list(dict.fromkeys(chunk_ids))
        )
    return mock.citations(chunk_ids)
