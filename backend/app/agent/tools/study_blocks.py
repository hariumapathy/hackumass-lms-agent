"""S25: propose a saved study session; only a student click can approve it."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import Field

from app.agent.tools.args import _Args
from app.agent.tools.context import RunCtx
from app.agent.tools.courses import resolve_course
from app.agent.tools.results import ToolResult
from app.agent.tools.runner import ToolRejected
from app.api.schemas import StudyBlock


class AddStudyBlockArgs(_Args):
    title: str = Field(min_length=1, max_length=80)
    start_local: datetime
    duration_min: int = Field(ge=15, le=240)
    course: str | None = None
    item_id: str | None = None


def local_start(value: datetime, timezone: str) -> datetime:
    if value.tzinfo is not None:
        raise ToolRejected("Use a local date and time without a UTC offset.")
    zone = ZoneInfo(timezone)
    first = value.replace(tzinfo=zone, fold=0)
    second = value.replace(tzinfo=zone, fold=1)
    if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != value:
        raise ToolRejected(
            "That local time does not exist during the daylight-saving change. Choose another time."
        )
    if first.utcoffset() != second.utcoffset():
        raise ToolRejected(
            "That local time occurs twice during the daylight-saving change. Choose another time."
        )
    return first.astimezone(UTC)


async def add_study_block(ctx: RunCtx, args: AddStudyBlockArgs) -> ToolResult:
    async with ctx.block_lock:
        if len(ctx.proposed_blocks) >= 10:
            raise ToolRejected("At most 10 study sessions can be proposed in one answer.")
        start = local_start(args.start_local, ctx.timezone)
        now = ctx.clock.now()
        if not now < start <= now + timedelta(days=30):
            raise ToolRejected("Study sessions must start in the future, within 30 days.")
        course_id = None
        if args.course:
            resolved = resolve_course(await ctx.data.courses(), args.course)
            if resolved.course is None:
                raise ToolRejected(resolved.note or "Course not found.")
            course_id = resolved.course.id
        try:
            item_id = UUID(args.item_id) if args.item_id else None
        except ValueError:
            raise ToolRejected("Assignment ID must be a valid ID from get_items.") from None
        block = StudyBlock(
            id=uuid4(),
            title=args.title,
            start_at=start,
            end_at=start + timedelta(minutes=args.duration_min),
            course_id=course_id,
            item_id=item_id,
            status="proposed",
        )
        if ctx.block_store is None:
            raise ToolRejected("Study sessions are unavailable right now. Try again later.")
        try:
            saved = await ctx.block_store.propose_block(ctx.user_id, block, now)
        except ValueError as exc:
            raise ToolRejected(str(exc)) from None
        if not saved:
            raise ToolRejected(
                "This session would overlap another proposed or approved session. "
                "Choose another time."
            )
        ctx.proposed_blocks.append(block)
        return ToolResult(
            results=[
                {
                    "block_id": str(block.id),
                    "title": block.title,
                    "start_at": block.start_at.isoformat(),
                    "end_at": block.end_at.isoformat(),
                    "status": "proposed; the student adds it with the Add button shown "
                    "under your answer (not in their calendar app)",
                }
            ]
        )
