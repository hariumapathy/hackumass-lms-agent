"""`course` argument resolver (S21): UUID, code ("CS 311"), bare number ("311") or name fragment."""

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from app.core.courses import normalize_course_code


class CourseRef(BaseModel):
    id: UUID
    code: str
    name: str


@dataclass
class Resolved:
    course: CourseRef | None
    note: str | None = None


def _known(courses: list[CourseRef]) -> str:
    return ", ".join(sorted(c.code for c in courses)) or "none yet"


def resolve_course(courses: list[CourseRef], query: str) -> Resolved:
    q = (query or "").strip()
    if not q:
        return Resolved(None, f"Unknown course ''. Known: {_known(courses)}")

    try:
        wanted = UUID(q)
        by_id = [c for c in courses if c.id == wanted]
        if by_id:
            return Resolved(by_id[0])
    except ValueError:
        pass

    candidates: list[CourseRef] = []
    code = normalize_course_code(q)
    if code:
        candidates = [c for c in courses if normalize_course_code(c.code) == code]
    if not candidates and q.isdigit():
        candidates = [c for c in courses if (n := normalize_course_code(c.code)) and n[1] == q]
    if not candidates and not code:
        low = q.lower()
        candidates = [c for c in courses if low in c.name.lower() or low in c.code.lower()]

    if len(candidates) == 1:
        return Resolved(candidates[0])
    if len(candidates) > 1:
        options = ", ".join(f"{c.code} ({c.name})" for c in candidates)
        return Resolved(None, f"'{q}' matches several courses: {options}. Which one?")
    return Resolved(None, f"Unknown course '{q}'. Known: {_known(courses)}")
