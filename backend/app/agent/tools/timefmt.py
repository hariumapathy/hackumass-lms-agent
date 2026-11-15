"""Times for the model: local strings in the student's timezone + relative phrases (S21 rule 5),
so the model never does timezone math."""

from datetime import datetime
from zoneinfo import ZoneInfo


def local_time(dt: datetime, tz: str) -> str:
    """'Thu Nov 19, 7:00 PM' (portable: no platform-specific strftime flags)."""
    local = dt.astimezone(ZoneInfo(tz))
    hour = local.hour % 12 or 12
    return f"{local:%a %b} {local.day}, {hour}:{local:%M} {'AM' if local.hour < 12 else 'PM'}"


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}{'' if n == 1 else 's'}"


def _span(seconds: float) -> str:
    if seconds >= 86400:
        return _plural(int(seconds // 86400), "day")
    if seconds >= 3600:
        return _plural(int(seconds // 3600), "hour")
    return _plural(int(seconds // 60), "minute")


def relative_time(dt: datetime, now: datetime) -> str:
    """'in 6 days' / '2 hours ago' / 'now' (under a minute either way)."""
    seconds = (dt - now).total_seconds()
    if abs(seconds) < 60:
        return "now"
    return f"in {_span(seconds)}" if seconds > 0 else f"{_span(-seconds)} ago"


def ago(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "never"
    seconds = (now - dt).total_seconds()
    return "just now" if seconds < 60 else f"{_span(seconds)} ago"
