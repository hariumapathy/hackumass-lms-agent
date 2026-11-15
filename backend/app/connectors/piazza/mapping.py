"""S17 mapping: piazza-api dicts → vendored piazza-mcp models → NCourse / NPost.

Pure functions. Authors become a role ("Instructor" / "Student" / "Anonymous"), never a name.
Text is stored as-is (plain text from the normalizer); S21 tools wrap it as untrusted.
"""

import re
from datetime import datetime
from typing import Any

from app.connectors.base import NCourse, NPost
from app.connectors.piazza._vendored.models import PiazzaThread
from app.connectors.piazza.login import PIAZZA_BASE_URL

INSTRUCTOR, STUDENT, ANONYMOUS = "Instructor", "Student", "Anonymous"
_INSTRUCTOR_TAGS = {"instructor-note", "instructor-question", "instructor"}
_BODY_LABEL = {"question": "Q", "note": "Note", "poll": "Poll", "unknown": "Post"}

_TERM_RE = re.compile(r"\b(spring|summer|fall|autumn|winter)\s*'?\s*(\d{4}|\d{2})\b", re.I)


def post_platform_id(nid: str, number: int) -> str:
    """Unique per user + platform (the `posts` lookup key has no course in it)."""
    return f"{nid}:{number}"


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def feed_updated(raw: dict[str, Any]) -> datetime | None:
    value = raw.get("updated") or raw.get("modified")
    parsed = parse_ts(value) if isinstance(value, str) else None
    return parsed if parsed is None or parsed.tzinfo is not None else None


def _term_window(term: str | None) -> tuple[datetime, datetime] | None:
    """Rough dates of a "Fall 2026"-style term; None when the term can't be read."""
    m = _TERM_RE.search(term or "")
    if not m:
        return None
    season, year = m.group(1).lower(), int(m.group(2))
    year = year + 2000 if year < 100 else year
    windows = {
        "spring": ((year, 1, 1), (year, 5, 31)),
        "summer": ((year, 5, 15), (year, 8, 31)),
        "fall": ((year, 8, 15), (year, 12, 31)),
        "autumn": ((year, 8, 15), (year, 12, 31)),
        "winter": ((year - 1, 12, 15), (year, 1, 31)),
    }
    (y1, m1, d1), (y2, m2, d2) = windows[season]
    return datetime(y1, m1, d1), datetime(y2, m2, d2, 23, 59, 59)


def is_current_term(term: str | None, now: datetime) -> bool:
    """Current-term filter (S17 rule 2). Unreadable terms are kept rather than dropped."""
    window = _term_window(term)
    if window is None:
        return True
    naive = now.replace(tzinfo=None)
    return window[0] <= naive <= window[1]


def to_ncourse(raw: dict[str, Any]) -> NCourse:
    nid = str(raw["nid"])
    name = str(raw.get("name") or "").strip() or nid
    code = str(raw.get("num") or "").strip() or None
    term = str(raw.get("term") or "").strip() or None
    url = f"{PIAZZA_BASE_URL}/class/{nid}"
    return NCourse(platform_id=nid, name=name, code=code, term=term, source_url=url)


def author_role(raw_post: dict[str, Any]) -> str:
    """Role of the original poster. Piazza lists revisions newest first; the last one is the
    original. `anon` is "no" for named posts, "stud"/"full" when hidden from classmates/everyone."""
    history = raw_post.get("history")
    original = history[-1] if isinstance(history, list) and history else {}
    anon = original.get("anon") if isinstance(original, dict) else None
    if anon not in (None, "no"):
        return ANONYMOUS
    tags = raw_post.get("tags")
    if isinstance(tags, list) and _INSTRUCTOR_TAGS & {str(t).lower() for t in tags}:
        return INSTRUCTOR
    return STUDENT


def thread_body(thread: PiazzaThread) -> str:
    """'Q: ... \\n\\nA (instructor): ... \\n\\nA (student): ...' (seed style, labelled)."""
    parts = [f"{_BODY_LABEL.get(thread.kind, 'Post')}: {thread.body or thread.subject}"]
    if thread.instructor_answer is not None:
        parts.append(f"A (instructor): {thread.instructor_answer.body}")
    if thread.student_answer is not None:
        parts.append(f"A (student): {thread.student_answer.body}")
    return "\n\n".join(parts)


def to_npost(thread: PiazzaThread, raw_post: dict[str, Any], fallback: datetime) -> NPost:
    updated = parse_ts(thread.updated_at)
    posted = parse_ts(thread.created_at) or updated or fallback
    return NPost(
        platform_id=post_platform_id(thread.course_id, thread.post_number),
        course_platform_id=thread.course_id,
        kind="piazza",
        title=thread.subject,
        body=thread_body(thread),
        author=author_role(raw_post),
        posted_at=posted,
        source_url=thread.source_url,
        source_updated_at=updated,
    )
