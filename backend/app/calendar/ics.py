"""S25 ICS rendering. icalendar escapes text and folds UTF-8 lines safely."""

from datetime import datetime, timedelta
from typing import Any

from icalendar import Calendar, Event


def render_feed(items: list[dict[str, Any]], blocks: list[dict[str, Any]], now: datetime) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//HackUMass LMS Agent//EN")
    calendar.add("version", "2.0")
    calendar.add("x-wr-calname", "Class deadlines and study sessions")
    for row in items:
        event = Event()
        event.add("uid", f"item-{row['id']}@hackumass-lms-agent")
        event.add("dtstamp", now)
        event.add("dtstart", row["due_at"] - timedelta(minutes=15))
        event.add("dtend", row["due_at"])
        event.add("summary", f"[{row['course_code']}] {row['title']}")
        event.add("sequence", row["sequence"])
        event.add("last-modified", row["updated_at"])
        sources = row["sources"]
        if sources:
            event.add("url", sources[0]["url"])
            event.add("description", "\n".join(f"{s['platform']}: {s['url']}" for s in sources))
        calendar.add_component(event)
    for row in blocks:
        event = Event()
        event.add("uid", f"block-{row['id']}@hackumass-lms-agent")
        event.add("dtstamp", now)
        event.add("dtstart", row["start_at"])
        event.add("dtend", row["end_at"])
        event.add("summary", row["title"])
        event.add("sequence", 0)
        event.add("last-modified", row["modified"])
        calendar.add_component(event)
    return calendar.to_ical()
