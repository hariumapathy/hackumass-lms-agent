"""Pure Canvas JSON -> normalized record mapping (S11 mapping rules). No HTTP here."""

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from app.connectors.base import DownloadRef, NCourse, NItem, NMaterial, NPost
from app.db.models import ItemType

# Rule 2. "final" alone is checked after lab/project so "Final Project" stays a project.
_EXAM = re.compile(r"\b(midterm|exam)\b", re.IGNORECASE)
_FINAL = re.compile(r"\bfinal\b", re.IGNORECASE)
_LAB = re.compile(r"\blab\b", re.IGNORECASE)
_PROJECT = re.compile(r"\bproject\b", re.IGNORECASE)
_SECTION = re.compile(r"\s+(sec|section|lec|lecture|dis|lab)\b.*$", re.IGNORECASE)
SUPPORTED_EXTENSIONS = {"pdf", "pptx", "docx", "txt", "md", "html"}  # rule 6

# Raw assignment fields kept on `item_sources.raw` (not hashed; for debugging/merge).
_RAW_KEYS = (
    "id",
    "name",
    "title",
    "due_at",
    "lock_at",
    "unlock_at",
    "start_at",
    "end_at",
    "points_possible",
    "submission_types",
    "is_quiz_assignment",
    "quiz_id",
    "html_url",
    "updated_at",
)


def parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_course_code(code: str | None) -> str | None:
    """Rule 4: `COMPSCI 311 SEC 01` -> `COMPSCI 311` (sections dropped, spaces collapsed)."""
    if not code:
        return None
    text = " ".join(code.split())
    text = _SECTION.sub("", text).strip().upper()
    return text or None


def is_exam_title(title: str) -> bool:
    return bool(_EXAM.search(title) or _FINAL.search(title))


def item_type(assignment: dict[str, Any]) -> ItemType:
    """Rule 2: quiz, then exam/lab/project by title, else assignment."""
    if assignment.get("is_quiz_assignment") or assignment.get("is_quiz_lti_assignment"):
        return "quiz"
    title = assignment.get("name") or ""
    if _EXAM.search(title):
        return "exam"
    if _LAB.search(title):
        return "lab"
    if _PROJECT.search(title):
        return "project"
    if _FINAL.search(title):
        return "exam"
    return "assignment"


def supported_file(f: dict[str, Any]) -> bool:
    name = f.get("display_name") or f.get("filename") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return ext in SUPPORTED_EXTENSIONS


class _TextExtractor(HTMLParser):
    _BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
    _SKIP = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._href: list[str | None] = []
        self._link_text: list[int] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BLOCK:
            self.out.append("\n")
            if tag == "li":
                self.out.append("- ")
        elif tag == "a":
            self._href.append(dict(attrs).get("href"))
            self._link_text.append(len(self.out))

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK:
            self.out.append("\n")
        elif tag == "a" and self._href:
            href, start = self._href.pop(), self._link_text.pop()
            text = "".join(self.out[start:]).strip()
            if href and href.startswith(("http://", "https://", "mailto:")) and href != text:
                self.out.append(f" ({href})" if text else href)

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.out.append(data)


def html_to_text(html: str | None) -> str:
    """Rule 5: HTML -> plain text, one line per block, links kept as `text (url)`."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.out).replace("\xa0", " ")
    lines = (" ".join(line.split()) for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------------------------
def course_usable(c: dict[str, Any]) -> bool:
    return bool(c.get("name")) and not c.get("access_restricted_by_date")


def to_course(c: dict[str, Any], base: str) -> NCourse:
    term = c.get("term") or {}
    return NCourse(
        platform_id=str(c["id"]),
        name=c["name"],
        code=normalize_course_code(c.get("course_code")),
        term=term.get("name") or None,
        source_url=f"{base}/courses/{c['id']}",
    )


def _raw(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: obj[k] for k in _RAW_KEYS if k in obj}


def to_item(a: dict[str, Any], course_id: str, base: str) -> NItem:
    points = a.get("points_possible")
    return NItem(
        platform_id=str(a["id"]),
        course_platform_id=course_id,
        type=item_type(a),
        title=a.get("name") or "Untitled assignment",
        description=html_to_text(a.get("description")) or None,
        due_at=parse_dt(a.get("due_at")),  # rule 3: never guessed from lock_at
        points=float(points) if points is not None else None,
        source_url=a.get("html_url") or f"{base}/courses/{course_id}/assignments/{a['id']}",
        source_updated_at=parse_dt(a.get("updated_at")),
        raw=_raw(a),
    )


def event_to_item(e: dict[str, Any], course_id: str, base: str) -> NItem | None:
    """Calendar events become exam items only when the title says so (rule 2)."""
    title = e.get("title") or ""
    if not is_exam_title(title):
        return None
    return NItem(
        platform_id=f"event-{e['id']}",  # own namespace: event ids can collide with assignments
        course_platform_id=course_id,
        type="exam",
        title=title,
        description=html_to_text(e.get("description")) or None,
        due_at=parse_dt(e.get("start_at")),
        points=None,
        source_url=e.get("html_url") or f"{base}/calendar?event_id={e['id']}",
        source_updated_at=parse_dt(e.get("updated_at")),
        raw=_raw(e),
    )


def to_post(a: dict[str, Any], course_id: str, base: str) -> NPost | None:
    posted = parse_dt(a.get("posted_at")) or parse_dt(a.get("delayed_post_at"))
    if posted is None:
        return None
    author = (a.get("author") or {}).get("display_name") or a.get("user_name") or None
    return NPost(
        platform_id=str(a["id"]),
        course_platform_id=course_id,
        kind="announcement",
        title=a.get("title") or "Announcement",
        body=html_to_text(a.get("message")),
        author=author,
        posted_at=posted,
        source_url=a.get("html_url") or f"{base}/courses/{course_id}/discussion_topics/{a['id']}",
        source_updated_at=parse_dt(a.get("updated_at")) or parse_dt(a.get("last_reply_at")),
    )


def to_file_material(f: dict[str, Any], course_id: str, base: str) -> NMaterial | None:
    """Rule 6. The download URL carries no token and no `verifier`: the worker authenticates
    with the token in a header at download time (S12)."""
    if not supported_file(f) or f.get("locked_for_user") or f.get("hidden_for_user"):
        return None
    fid = f["id"]
    return NMaterial(
        platform_id=str(fid),
        course_platform_id=course_id,
        kind="file",
        title=f.get("display_name") or f.get("filename") or f"File {fid}",
        mime_type=f.get("content-type") or None,
        download=DownloadRef(
            url=f"{base}/files/{fid}/download?download_frd=1",
            size_bytes=f.get("size"),
            filename=f.get("filename") or f.get("display_name"),
        ),
        source_url=f"{base}/courses/{course_id}/files/{fid}",
        source_updated_at=parse_dt(f.get("updated_at")),
    )


def to_syllabus(c: dict[str, Any], base: str) -> NMaterial | None:
    text = html_to_text(c.get("syllabus_body"))
    if not text:
        return None
    cid = str(c["id"])
    return NMaterial(
        platform_id=f"syllabus-{cid}",
        course_platform_id=cid,
        kind="syllabus",
        title=f"{c.get('name') or 'Course'} syllabus",
        mime_type="text/html",
        text=text,
        source_url=f"{base}/courses/{cid}/assignments/syllabus",
    )
