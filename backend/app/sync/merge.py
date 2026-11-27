"""Cross-platform merge and canonical change detection (S16).

`merge_user` runs after every successful sync (`merge_user` task in `jobs.py`):
1. Courses: canonical courses with the same normalized code + term and no platform in common are
   merged into one (the Canvas-linked one is kept, so Canvas names the course).
2. Items: every unattached `item_sources` row (and every item of a course merged in this run) is
   matched to an existing canonical item in the same course, else gets its own item.
3. Canonical fields are recomputed from the sources (precedence below); a change to `title`,
   `due_at` or `points` of an existing item writes one `changes` row per field and sets
   `items.status = 'changed'`. All sources removed -> item `removed`.

The pure rules (`match_course`, `match_item`, `canonical_fields`) have no DB access. All SQL is
filtered by `user_id`. Running twice in a row changes nothing (idempotent).
"""

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.clock import Clock, SystemClock
from app.core.courses import normalize_course_code

__all__ = [
    "CanonicalItem",
    "CourseRow",
    "ItemRow",
    "MergeStats",
    "SourceRow",
    "canonical_fields",
    "clean_title",
    "items_match",
    "match_course",
    "match_item",
    "merge_user",
    "normalize_course_code",
    "normalize_term",
]

PRECEDENCE = {"canvas": 0, "gradescope": 1}  # everything else: 2
TITLE_THRESHOLD = 75  # token_set_ratio / 100 >= 0.75
DUE_WINDOW = timedelta(hours=36)
CHANGE_FIELDS = ("title", "due_at", "points")


def _rank(platform: str) -> int:
    return PRECEDENCE.get(platform, 2)


# ---------------------------------------------------------------------------------------------
# Rows (plain data; built from the DB in `merge_user`, by hand in unit tests)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CourseRow:
    id: UUID
    code: str | None
    term: str | None
    platforms: frozenset[str]
    created_at: datetime


@dataclass
class SourceRow:
    id: UUID
    item_id: UUID | None
    course_id: UUID
    platform: str
    title: str
    due_at: datetime | None
    points: float | None
    type: str | None  # None: the source didn't say (e.g. seeded rows without `_normalized`)
    description: str | None
    status: str
    created_at: datetime


@dataclass
class ItemRow:
    id: UUID | None  # None for a not-yet-created item (an unattached source being matched)
    course_id: UUID
    type: str | None
    title: str
    due_at: datetime | None
    points: float | None
    status: str
    platforms: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CanonicalItem:
    title: str
    due_at: datetime | None
    points: float | None
    type: str | None
    description: str | None


class MergeStats(BaseModel):
    courses_merged: int = 0
    items_created: int = 0
    sources_attached: int = 0
    items_folded: int = 0
    items_updated: int = 0
    changes_written: int = 0
    items_removed: int = 0


# ---------------------------------------------------------------------------------------------
# Course matching (rule 1). Rule 2 (Echo360 via launching Canvas course) waits for S15.
# ---------------------------------------------------------------------------------------------
_SEASONS = {"fa": "fall", "sp": "spring", "su": "summer", "wi": "winter", "w": "winter"}
_TERM = re.compile(r"\b(fall|spring|summer|winter|fa|sp|su|wi|w)\s*'?(\d{4}|\d{2})\b")
_TERM_REV = re.compile(r"\b(\d{4})\s+(fall|spring|summer|winter)\b")


def normalize_term(raw: str | None) -> str | None:
    """ "Fall 2026" / "2026 Fall" / "FA26" -> "fall 2026"; anything else: casefolded text."""
    if raw is None or not raw.strip():
        return None
    text = " ".join(raw.casefold().split())
    if m := _TERM.search(text):
        season, year = m.group(1), m.group(2)
    elif m := _TERM_REV.search(text):
        year, season = m.group(1), m.group(2)
    else:
        return text
    season = _SEASONS.get(season, season)
    return f"{season} {year if len(year) == 4 else '20' + year}"


def _course_key(c: CourseRow) -> tuple[tuple[str, str], str | None] | None:
    code = normalize_course_code(c.code or "")
    return (code, normalize_term(c.term)) if code else None


def match_course(course: CourseRow, courses: list[CourseRow]) -> CourseRow | None:
    """The one other course with the same normalized code and term and no platform in common
    (two Canvas courses with one code are two sections). Zero or several -> None."""
    key = _course_key(course)
    if key is None:
        return None
    hits = [
        c
        for c in courses
        if c.id != course.id and _course_key(c) == key and not (c.platforms & course.platforms)
    ]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------------------------------------
# Item matching (rules 2-4)
# ---------------------------------------------------------------------------------------------
_NOISE = {
    "submit",
    "submission",
    "submissions",
    "gradescope",
    "canvas",
    "pdf",
    "upload",
    "online",
    "on",
    "via",
    "here",
}
_ABBREV = {
    "hw": "homework",
    "hws": "homework",
    "pset": "problem set",
    "ps": "problem set",
    "proj": "project",
    "mt": "midterm",
    "qz": "quiz",
}
_EXAM_WORDS = re.compile(r"\b(midterm|exam|prelim)\b")
_WORK_WORDS = re.compile(r"\b(homework|review|practice|lab|project|quiz|problem set)\b")


def clean_title(title: str) -> str:
    """Lowercase, split "HW4" -> "hw 4", expand abbreviations, drop noise words/punctuation."""
    text = title.casefold()
    text = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", text)
    words: list[str] = re.findall(r"[a-z]+|\d+", text)
    out = [_ABBREV.get(w, w) for w in words if w not in _NOISE]
    return " ".join(out)


def _ordinals(cleaned: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", cleaned)]


def _family(type_: str | None, cleaned: str) -> str | None:
    """ "exam", "work" (assignment-like) or None (unknown: compatible with both)."""
    if type_ == "exam":
        return "exam"
    if type_ in (None, "other", "assignment") and _EXAM_WORDS.search(cleaned):
        if not _WORK_WORDS.search(cleaned):
            return "exam"  # Gradescope lists exams as assignments; calendar exams are "other"
    if type_ in (None, "other"):
        return None
    return "work"


def _as_item(x: "SourceRow | ItemRow") -> ItemRow:
    if isinstance(x, ItemRow):
        return x
    return ItemRow(
        id=None,
        course_id=x.course_id,
        type=x.type,
        title=x.title,
        due_at=x.due_at,
        points=x.points,
        status=x.status,
        platforms=frozenset({x.platform}),
    )


def items_match(a: "SourceRow | ItemRow", b: ItemRow) -> bool:
    """Rules 2-3: no platform in common, compatible type, titles >= 0.75 similar with equal
    ordinals, due dates within 36 h (or one missing)."""
    a = _as_item(a)
    if a.platforms & b.platforms:
        return False
    ta, tb = clean_title(a.title), clean_title(b.title)
    fa, fb = _family(a.type, ta), _family(b.type, tb)
    if fa and fb and fa != fb:
        return False
    oa, ob = _ordinals(ta), _ordinals(tb)
    if oa and ob and oa != ob:
        return False
    if fuzz.token_set_ratio(ta, tb) < TITLE_THRESHOLD:
        return False
    return a.due_at is None or b.due_at is None or abs(a.due_at - b.due_at) <= DUE_WINDOW


def match_item(src: "SourceRow | ItemRow", candidates: list[ItemRow]) -> ItemRow | None:
    """The single matching candidate; none or several (ambiguous, rule 4) -> None."""
    hits = [c for c in candidates if items_match(src, c)]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------------------------------------
# Canonical fields
# ---------------------------------------------------------------------------------------------
def canonical_fields(sources: list[SourceRow]) -> CanonicalItem:
    """Canvas > Gradescope > others for title/due_at/points (first non-null, so Gradescope fills
    a missing Canvas due date); `type`: exam wins, else the first known non-"other" type."""
    ordered = sorted(sources, key=lambda s: (_rank(s.platform), s.created_at, str(s.id)))

    def first(attr: str) -> Any:
        return next((getattr(s, attr) for s in ordered if getattr(s, attr) is not None), None)

    types = [s.type for s in ordered if s.type is not None]
    if "exam" in types:
        type_: str | None = "exam"
    else:
        type_ = next((t for t in types if t != "other"), "other" if types else None)
    return CanonicalItem(
        title=ordered[0].title,
        due_at=first("due_at"),
        points=first("points"),
        type=type_,
        description=first("description"),
    )


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        return float(a) == float(b)
    return a == b


def _json(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.astimezone(UTC).isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------------------------
# DB pass
# ---------------------------------------------------------------------------------------------
_COURSE_CHILDREN = (
    "course_links",
    "item_sources",
    "materials",
    "posts",
    "chunks",
    "changes",
    "study_sets",
    "study_blocks",
    "misses",
)


class _Merger:
    def __init__(self, conn: AsyncConnection[Any], user_id: UUID, now: datetime) -> None:
        self.conn, self.user_id, self.now = conn, user_id, now
        self.stats = MergeStats()

    async def rows(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        cur = await self.conn.execute(sql, params)  # type: ignore[arg-type]
        return await cur.fetchall()

    async def exec(self, sql: str, params: tuple[Any, ...]) -> None:
        await self.conn.execute(sql, params)  # type: ignore[arg-type]

    # --- 1. courses ----------------------------------------------------------------------------
    async def merge_courses(self) -> set[UUID]:
        """Returns ids of the items that moved course in this run (to match them again)."""
        rows = await self.rows(
            "select c.id, c.code, c.term, c.created_at, coalesce(array_agg(distinct "
            "l.platform::text) filter (where l.id is not null), '{}') as platforms "
            "from courses c left join course_links l on l.course_id = c.id and l.user_id = %s "
            "where c.user_id = %s group by c.id",
            (self.user_id, self.user_id),
        )
        courses = [
            CourseRow(r["id"], r["code"], r["term"], frozenset(r["platforms"]), r["created_at"])
            for r in rows
        ]
        courses.sort(key=lambda c: (min(map(_rank, c.platforms), default=3), c.created_at))
        kept: list[CourseRow] = []
        absorbed: set[UUID] = set()
        for c in courses:
            target = match_course(c, kept)
            if target is None:
                kept.append(c)
                continue
            absorbed |= await self.absorb_course(c, target)
            kept[kept.index(target)] = replace(target, platforms=target.platforms | c.platforms)
        return absorbed

    async def absorb_course(self, other: CourseRow, keep: CourseRow) -> set[UUID]:
        moved = await self.rows(
            "update items set course_id = %s where user_id = %s and course_id = %s returning id",
            (keep.id, self.user_id, other.id),
        )
        for table in _COURSE_CHILDREN:
            previous = []
            if table in {"materials", "posts"}:
                previous = await self.rows(
                    f"select id,source_revision from {table} "
                    "where user_id=%s and course_id=%s for update",
                    (self.user_id, other.id),
                )
            await self.rows(
                f"update {table} set course_id = %s "  # noqa: S608
                "where user_id = %s and course_id = %s returning id",
                (keep.id, self.user_id, other.id),
            )
            if table in {"materials", "posts"}:
                from app.db.repositories.processing import rebind_course_parents

                await rebind_course_parents(
                    self.conn,
                    self.user_id,
                    table,
                    [(r["id"], r["source_revision"]) for r in previous],
                )
        await self.exec(
            "update courses k set code = coalesce(k.code, o.code), "
            "term = coalesce(k.term, o.term), color = coalesce(k.color, o.color) "
            "from courses o where k.user_id = %s and k.id = %s and o.user_id = %s and o.id = %s",
            (self.user_id, keep.id, self.user_id, other.id),
        )
        await self.exec(
            "delete from courses where user_id = %s and id = %s", (self.user_id, other.id)
        )
        self.stats.courses_merged += 1
        return {r["id"] for r in moved}

    # --- 2. items ------------------------------------------------------------------------------
    async def load(self) -> tuple[dict[UUID, ItemRow], list[SourceRow], dict[UUID, Any]]:
        item_rows = await self.rows(
            "select id, course_id, type::text as type, title, description, due_at, points, "
            "status::text as status from items where user_id = %s",
            (self.user_id,),
        )
        items = {
            r["id"]: ItemRow(
                r["id"],
                r["course_id"],
                r["type"],
                r["title"],
                r["due_at"],
                _num(r["points"]),
                r["status"],
            )
            for r in item_rows
        }
        raw_items = {r["id"]: r for r in item_rows}
        sources = []
        for r in await self.rows(
            "select id, item_id, course_id, platform::text as platform, raw_title, raw_due_at, "
            "raw, status::text as status, created_at from item_sources where user_id = %s "
            "order by created_at, id",
            (self.user_id,),
        ):
            raw = r["raw"] or {}
            norm = raw.get("_normalized")
            known = isinstance(norm, dict)
            sources.append(
                SourceRow(
                    id=r["id"],
                    item_id=r["item_id"],
                    course_id=r["course_id"],
                    platform=r["platform"],
                    title=r["raw_title"],
                    due_at=r["raw_due_at"],
                    points=_num((norm if known else raw).get("points")),
                    type=norm.get("type") if known else None,
                    description=norm.get("description") if known else None,
                    status=r["status"],
                    created_at=r["created_at"],
                )
            )
        return items, sources, raw_items

    async def merge_items(self, absorbed: set[UUID]) -> None:
        items, sources, raw_items = await self.load()
        by_item: dict[UUID, list[SourceRow]] = {}
        for s in sources:
            if s.item_id in items:
                by_item.setdefault(s.item_id, []).append(s)  # type: ignore[arg-type]
        for it_id, srcs in by_item.items():
            items[it_id].platforms = frozenset(s.platform for s in srcs)

        # Units to match: unattached sources, and items whose course was absorbed this run.
        units: list[tuple[ItemRow, list[SourceRow]]] = [
            (_as_item(s), [s]) for s in sources if s.item_id not in items
        ]
        units += [(it, by_item[i]) for i, it in items.items() if i in absorbed and by_item.get(i)]
        units.sort(
            key=lambda u: (
                min(_rank(p) for p in u[0].platforms),
                min(s.created_at for s in u[1]),
            )
        )
        created: set[UUID] = set()
        grew: set[UUID] = set()
        for unit, srcs in units:
            pool = [
                it
                for it in items.values()
                if it.course_id == unit.course_id and it.id != unit.id and it.status != "removed"
            ]
            active = any(s.status != "removed" for s in srcs)
            target = match_item(unit, pool) if active else None
            if target is not None and any(
                other is not unit
                and other.platforms & unit.platforms
                and items_match(other, target)
                for other, _ in units
            ):
                target = None  # two same-platform records want one item: ambiguous (rule 4)
            if target is None:
                if unit.id is None:
                    new = await self.create_item(srcs[0])
                    items[new.id] = new  # type: ignore[index]
                    by_item[new.id] = srcs  # type: ignore[index]
                    created.add(new.id)  # type: ignore[arg-type]
                continue
            assert target.id is not None
            if unit.id is None:
                await self.exec(
                    "update item_sources set item_id = %s where user_id = %s and id = %s",
                    (target.id, self.user_id, srcs[0].id),
                )
                self.stats.sources_attached += 1
            else:
                await self.fold_item(unit.id, target.id)
                del items[unit.id]
                by_item.pop(unit.id, None)
            for s in srcs:
                s.item_id = target.id
            by_item.setdefault(target.id, []).extend(srcs)
            grew.add(target.id)
            target.platforms = target.platforms | unit.platforms
            live = [s for s in by_item[target.id] if s.status != "removed"]
            if live:
                c = canonical_fields(live)
                target.title, target.due_at, target.type = c.title, c.due_at, c.type or target.type

        for it_id, srcs in by_item.items():
            await self.reconcile(raw_items.get(it_id), it_id, srcs, quiet=it_id in created | grew)

    async def create_item(self, s: SourceRow) -> ItemRow:
        c = canonical_fields([s])
        row = (
            await self.rows(
                "insert into items (user_id, course_id, type, title, description, due_at, "
                "points, status, updated_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
                (
                    self.user_id,
                    s.course_id,
                    c.type or "other",
                    c.title,
                    c.description,
                    c.due_at,
                    c.points,
                    "removed" if s.status == "removed" else "active",
                    self.now,
                ),
            )
        )[0]
        await self.exec(
            "update item_sources set item_id = %s where user_id = %s and id = %s",
            (row["id"], self.user_id, s.id),
        )
        s.item_id = row["id"]
        self.stats.items_created += 1
        return ItemRow(
            row["id"],
            s.course_id,
            c.type or "other",
            c.title,
            c.due_at,
            c.points,
            "removed" if s.status == "removed" else "active",
            frozenset({s.platform}),
        )

    async def fold_item(self, loser: UUID, keep: UUID) -> None:
        """Move everything that points at `loser` to `keep`, then delete `loser`."""
        uid = self.user_id
        await self.exec(
            "update item_sources set item_id = %s where user_id = %s and item_id = %s",
            (keep, uid, loser),
        )
        await self.exec(
            "update study_blocks set item_id = %s where user_id = %s and item_id = %s",
            (keep, uid, loser),
        )
        await self.exec(
            "update changes set entity_id = %s where user_id = %s and entity_type = 'item' "
            "and entity_id = %s",
            (keep, uid, loser),
        )
        await self.exec("delete from items where user_id = %s and id = %s", (uid, loser))
        self.stats.items_folded += 1

    # --- 3. canonical fields + change rows -----------------------------------------------------
    async def reconcile(
        self, row: dict[str, Any] | None, item_id: UUID, srcs: list[SourceRow], *, quiet: bool
    ) -> None:
        """Bring one item in line with its sources. `quiet`: created or given new sources in
        this run, so field differences are a merge, not a change the student should see."""
        if row is None:  # created in this run: already canonical
            return
        live = [s for s in srcs if s.status != "removed"]
        if not live:
            if row["status"] != "removed":
                await self.exec(
                    "update items set status = 'removed', updated_at = %s "
                    "where user_id = %s and id = %s",
                    (self.now, self.user_id, item_id),
                )
                await self.change(item_id, row["course_id"], "status", row["status"], "removed")
                self.stats.items_removed += 1
            return
        c = canonical_fields(live)
        new = {"title": c.title, "due_at": c.due_at, "points": c.points}
        diffs = [f for f in CHANGE_FIELDS if not _same(row[f], new[f])]
        type_ = c.type or row["type"]
        desc = c.description if c.description is not None else row["description"]
        if row["status"] == "removed":
            await self.change(item_id, row["course_id"], "status", "removed", "active")
        status = "active" if row["status"] == "removed" else row["status"]
        if diffs and not quiet:
            for f in diffs:
                await self.change(item_id, row["course_id"], f, row[f], new[f])
            status = "changed"
        if not diffs and type_ == row["type"] and desc == row["description"]:
            if status == row["status"]:
                return
        await self.exec(
            "update items set title = %s, due_at = %s, points = %s, type = %s, "
            "description = %s, status = %s, updated_at = %s where user_id = %s and id = %s",
            (c.title, c.due_at, c.points, type_, desc, status, self.now, self.user_id, item_id),
        )
        self.stats.items_updated += 1

    async def change(self, item_id: UUID, course_id: UUID, f: str, old: Any, new: Any) -> None:
        await self.exec(
            "insert into changes (user_id, entity_type, entity_id, course_id, field, old_value, "
            "new_value, detected_at) values (%s, 'item', %s, %s, %s, %s, %s, %s)",
            (
                self.user_id,
                item_id,
                course_id,
                f,
                Jsonb(_json(old)),
                Jsonb(_json(new)),
                self.now,
            ),
        )
        self.stats.changes_written += 1


async def merge_user(
    conn: AsyncConnection[Any], user_id: UUID, *, clock: Clock | None = None
) -> MergeStats:
    """Merge one student's courses and items (S16). One transaction, serialized per user."""
    m = _Merger(conn, user_id, (clock or SystemClock()).now())
    async with conn.transaction():
        await conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"merge:{user_id}",)
        )
        absorbed = await m.merge_courses()
        await m.merge_items(absorbed)
    return m.stats
