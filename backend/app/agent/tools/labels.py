"""Plain-language status labels for SSE `status` events (S21 rule 10). No jargon (no "sync")."""

from pydantic import BaseModel

_ITEM_TYPES = {
    "assignment": "assignments",
    "exam": "exams",
    "quiz": "quizzes",
    "lab": "labs",
    "project": "projects",
}
_KINDS = {
    "slides": "slides",
    "transcript": "lecture recordings",
    "post": "announcements and posts",
    "syllabus": "syllabus",
    "any": "slides and lectures",
}
_PLATFORMS = {
    "canvas": "Canvas",
    "gradescope": "Gradescope",
    "echo360": "Echo360",
    "piazza": "Piazza",
}


def status_label(tool: str, args: BaseModel) -> str:
    a = args.model_dump()
    course = a.get("course")
    if tool == "get_items":
        what = _ITEM_TYPES.get(a.get("type") or "", "deadlines")
        return f"Checking your {course + ' ' if course else ''}{what}…"
    if tool == "get_changes":
        return f"Looking for recent changes{' in ' + course if course else ''}…"
    if tool == "search_materials":
        return f"Searching {course + ' ' if course else ''}{_KINDS[a.get('kind') or 'any']}…"
    if tool == "get_material":
        return f"Reading pages {a['pages']}…" if a.get("pages") else "Reading the material…"
    if tool == "get_course_overview":
        return f"Opening the {course} overview…"
    if tool == "fetch_latest":
        source = _PLATFORMS.get(a.get("source") or "")
        return f"Checking {source or 'your classes'} for updates…"
    return "Working on it…"
