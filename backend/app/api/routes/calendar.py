"""Calendar feed endpoints (S02 stubs; real feed in S25)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.core.settings import get_settings

router = APIRouter(tags=["calendar"])
User = Annotated[UserCtx, Depends(current_user)]


def _feed_url(token: str) -> str:
    return f"{get_settings().public_api_url}/calendar/{token}.ics"


@router.get("/calendar/feed", response_model=s.CalendarFeed)
async def calendar_feed(user: User) -> s.CalendarFeed:
    return s.CalendarFeed(url=_feed_url("demo-token"))


@router.post("/calendar/feed/rotate", response_model=s.CalendarFeed)
async def rotate_feed(user: User) -> s.CalendarFeed:
    return s.CalendarFeed(url=_feed_url("demo-token-rotated"))


def _ics_time(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


@router.get(
    "/calendar/{token}.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}, "description": "iCalendar feed"}},
)
async def ics_feed(token: str) -> Response:
    """No auth: the token in the URL is the secret (S25). Stub returns mock deadlines."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HackUMass LMS Agent//EN",
        "X-WR-CALNAME:Class deadlines",
    ]
    stamp = _ics_time(datetime.now(UTC))
    for item in mock.items():
        if item.due_at is None:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:item-{item.id}@hackumass-lms-agent",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_ics_time(item.due_at)}",
            f"DTEND:{_ics_time(item.due_at)}",
            f"SUMMARY:[{item.course_code}] {item.title}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar; charset=utf-8")
