"""Today, courses, items, changes and citations (S02 stubs; real logic in S23, S32)."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.core.errors import AppError, not_found

router = APIRouter(tags=["dashboard"])
User = Annotated[UserCtx, Depends(current_user)]


@router.get("/today", response_model=s.Today)
async def today(user: User, day: Annotated[date | None, Query(alias="date")] = None) -> s.Today:
    tz = ZoneInfo(mock.TZ)
    now = datetime.now(UTC)
    local_today = day or now.astimezone(tz).date()
    end_of_day = datetime.combine(local_today + timedelta(days=1), datetime.min.time(), tz)
    week_end = end_of_day + timedelta(days=7)
    items = [i for i in mock.items() if i.due_at is not None]
    return s.Today(
        date=local_today,
        timezone=mock.TZ,
        overdue=[i for i in items if i.due_at and i.due_at < now],
        due_today=[i for i in items if i.due_at and now <= i.due_at < end_of_day],
        due_this_week=[i for i in items if i.due_at and end_of_day <= i.due_at < week_end],
        upcoming_exams=[i for i in items if i.type == "exam" and i.due_at and i.due_at >= now],
        changes=[c for c in mock.changes() if not c.seen],
        new_posts=mock.posts(),
        sources=mock.sources(),
    )


@router.get("/courses", response_model=list[s.CourseSummary])
async def courses(user: User) -> list[s.CourseSummary]:
    return mock.course_summaries()


@router.get("/courses/{course_id}", response_model=s.CourseDetail)
async def course(course_id: UUID, user: User) -> s.CourseDetail:
    detail = mock.course_detail(course_id)
    if detail is None:
        raise not_found("Course")
    return detail


@router.get("/items", response_model=list[s.Item])
async def list_items(
    user: User,
    course_id: UUID | None = None,
    type: s.ItemType | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[s.Item]:
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
    out = mock.changes()
    if since:
        out = [c for c in out if c.detected_at >= since]
    if unseen:
        out = [c for c in out if not c.seen]
    return out


@router.post("/changes/seen", status_code=204)
async def mark_changes_seen(body: s.ChangesSeenRequest, user: User) -> Response:
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
    return mock.citations(chunk_ids)
