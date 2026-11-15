"""Relative dates for seed fixtures (S03 rule 1), so the demo semester is always current.

Syntax: `<sign><n><unit>[ HH:MM]`, e.g. `+3d 23:59`, `-20h`, `+45m`, `+0d 09:00`, `now`.
- `d` moves the **local calendar date** in the profile's timezone. With `HH:MM`, the local wall
  time is set (so "19:00" stays 19:00 across a DST change); without it, the local time is kept.
- `h` / `m` are exact durations from now (`HH:MM` not allowed).
Results are UTC.
"""

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

_PATTERN = re.compile(
    r"^(?P<sign>[+-])(?P<n>\d+)(?P<unit>[dhm])(?: (?P<hh>\d{1,2}):(?P<mm>\d{2}))?$"
)


class RelativeDateError(ValueError):
    pass


def resolve(expr: str, now: datetime, tz: str) -> datetime:
    expr = expr.strip()
    if expr == "now":
        return now.astimezone(UTC)
    m = _PATTERN.match(expr)
    if not m:
        raise RelativeDateError(f"bad relative date {expr!r} (expected e.g. '+3d 23:59' or '-20h')")
    n = int(m["n"]) * (1 if m["sign"] == "+" else -1)
    unit = m["unit"]
    if unit in "hm":
        if m["hh"] is not None:
            raise RelativeDateError(f"{expr!r}: a time of day only goes with days ('d')")
        delta = timedelta(hours=n) if unit == "h" else timedelta(minutes=n)
        return (now + delta).astimezone(UTC)
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    day = local.date() + timedelta(days=n)
    if m["hh"] is not None:
        hh, mm = int(m["hh"]), int(m["mm"])
        if hh > 23 or mm > 59:
            raise RelativeDateError(f"{expr!r}: bad time of day")
    else:
        hh, mm = local.hour, local.minute
    # Build the wall time in the zone (zoneinfo applies the right UTC offset for that date).
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=zone).astimezone(UTC)
