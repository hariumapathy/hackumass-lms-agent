"""Realistic mock data for S02 stubs, relative to "now" so it always looks current.

Replaced endpoint by endpoint as real implementations land (S20+). Mirrors the seed
semester in S03 (same course codes and IDs) so the frontend sees consistent data.
"""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from app.api import schemas as s

TZ = "America/New_York"


def mid(name: str) -> UUID:
    """Deterministic UUID for a mock entity name."""
    return uuid5(NAMESPACE_URL, f"hackumass-mock/{name}")


COURSES: list[tuple[str, str, str, str, list[s.Platform]]] = [
    (
        "cs311",
        "COMPSCI 311",
        "Introduction to Algorithms",
        "#7c3aed",
        ["canvas", "gradescope", "echo360"],
    ),
    ("cs320", "COMPSCI 320", "Intro to Software Engineering", "#0891b2", ["canvas", "gradescope"]),
    ("math235", "MATH 235", "Introduction to Linear Algebra", "#16a34a", ["canvas"]),
    ("stats315", "STATS 315", "Statistics I", "#ea580c", ["canvas"]),
]
CODE = {key: code for key, code, *_ in COURSES}


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _src(platform: s.Platform, path: str, ago_min: int = 12) -> s.SourceRef:
    host = "example.instructure.com" if platform == "canvas" else f"example.{platform}.com"
    return s.SourceRef(
        platform=platform,
        source_url=f"https://{host}/{path}",
        last_synced_at=_now() - timedelta(minutes=ago_min),
    )


def items() -> list[s.Item]:
    n = _now()
    spec = [  # key, course, type, title, due offset, points, sources, changed
        ("hw6", "stats315", "assignment", "HW 6", timedelta(hours=-20), 20, ["canvas"], []),
        (
            "lab4",
            "cs320",
            "lab",
            "Lab 4: Testing",
            timedelta(hours=5),
            10,
            ["canvas", "gradescope"],
            [],
        ),
        (
            "hw5",
            "cs311",
            "assignment",
            "HW 5: Dynamic Programming",
            timedelta(days=2),
            60,
            ["canvas", "gradescope"],
            ["points"],
        ),
        ("quiz7", "math235", "quiz", "Quiz 7: Eigenvalues", timedelta(days=3), 10, ["canvas"], []),
        (
            "proj2",
            "cs320",
            "project",
            "Project 2: Milestone 1",
            timedelta(days=5),
            50,
            ["canvas"],
            [],
        ),
        ("mid1", "cs311", "exam", "Midterm 1", timedelta(days=6), 100, ["canvas"], ["due_at"]),
        ("final", "math235", "exam", "Final Exam", timedelta(days=24), 200, ["canvas"], []),
    ]
    out = []
    for key, course, typ, title, offset, points, platforms, changed in spec:
        out.append(
            s.Item(
                id=mid(f"item/{key}"),
                course_id=mid(f"course/{course}"),
                course_code=CODE[course],
                type=cast(s.ItemType, typ),
                title=title,
                due_at=n + offset,
                points=points,
                status="changed" if changed else "active",
                sources=[
                    _src(cast(s.Platform, p), f"courses/{course}/assignments/{key}")
                    for p in platforms
                ],
                changed_fields=changed,
            )
        )
    return out


def posts() -> list[s.Post]:
    n = _now()
    return [
        s.Post(
            id=mid("post/a1"),
            course_id=mid("course/cs311"),
            kind="announcement",
            title="Midterm 1 moved to Thursday",
            excerpt="Midterm 1 moved two days later. Same time and room (Thompson 104).",
            posted_at=n - timedelta(hours=30),
            status="active",
            source_url="https://example.instructure.com/courses/cs311/discussion_topics/a1",
        ),
        s.Post(
            id=mid("post/p398"),
            course_id=mid("course/cs311"),
            kind="piazza",
            title="Midterm coverage",
            excerpt="The midterm covers material through dynamic programming, not graphs.",
            posted_at=n - timedelta(hours=20),
            status="active",
            source_url="https://example.piazza.com/class/cs311/post/398",
        ),
        s.Post(
            id=mid("post/a2"),
            course_id=mid("course/math235"),
            kind="announcement",
            title="Office hours moved",
            excerpt="Wednesday office hours move to 3-4 PM.",
            posted_at=n - timedelta(hours=2),
            status="active",
            source_url="https://example.instructure.com/courses/math235/discussion_topics/a2",
        ),
    ]


def changes() -> list[s.Change]:
    n = _now()
    return [
        s.Change(
            id=mid("change/mid1"),
            entity_type="item",
            entity_id=mid("item/mid1"),
            course_code="COMPSCI 311",
            field="due_at",
            old_value=(n + timedelta(days=4)).isoformat(),
            new_value=(n + timedelta(days=6)).isoformat(),
            detected_at=n - timedelta(hours=30),
            seen=False,
            summary="COMPSCI 311 Midterm 1 moved 2 days later",
        ),
        s.Change(
            id=mid("change/hw5"),
            entity_type="item",
            entity_id=mid("item/hw5"),
            course_code="COMPSCI 311",
            field="points",
            old_value=50,
            new_value=60,
            detected_at=n - timedelta(hours=10),
            seen=False,
            summary="COMPSCI 311 HW 5 now worth 60 points (was 50)",
        ),
    ]


def connections() -> list[s.Connection]:
    n = _now()
    return [
        s.Connection(
            platform="canvas",
            status="active",
            expires_at=n + timedelta(days=60),
            last_sync_at=n - timedelta(minutes=12),
            account_label="Demo Student",
        ),
        s.Connection(
            platform="gradescope", status="active", last_sync_at=n - timedelta(minutes=40)
        ),
        s.Connection(
            platform="echo360",
            status="needs_reconnect",
            last_sync_at=n - timedelta(days=3),
            last_error="Session expired",
        ),
    ]


def sources() -> list[s.SourceStatus]:
    return [
        s.SourceStatus(
            platform=c.platform,
            connection_status=c.status,
            last_sync_at=c.last_sync_at,
            stale=c.platform == "echo360",
        )
        for c in connections()
    ]


def course_summaries() -> list[s.CourseSummary]:
    upcoming = {}
    for it in items():
        upcoming[it.course_id] = upcoming.get(it.course_id, 0) + 1
    return [
        s.CourseSummary(
            id=mid(f"course/{key}"),
            code=code,
            name=name,
            term="Fall 2026",
            color=color,
            upcoming_count=upcoming.get(mid(f"course/{key}"), 0),
            platforms=platforms,
        )
        for key, code, name, color, platforms in COURSES
    ]


def course_detail(course_id: UUID) -> s.CourseDetail | None:
    for summary in course_summaries():
        if summary.id == course_id:
            key = next(k for k, *_ in COURSES if mid(f"course/{k}") == course_id)
            return s.CourseDetail(
                **summary.model_dump(),
                items=[i for i in items() if i.course_id == course_id],
                recent_posts=[p for p in posts() if p.course_id == course_id],
                materials=[
                    s.MaterialSummary(
                        id=mid(f"material/{key}/l7"),
                        title="Lecture 7 slides",
                        kind="file",
                        processing_status="done",
                        source_url=f"https://example.instructure.com/courses/{key}/files/7",
                    )
                ],
                syllabus_excerpt="Midterm 1 covers Lectures 1-9. Final is cumulative.",
            )
    return None


def citations(ids: list[int]) -> list[s.Citation]:
    n = _now()
    known = {
        8812: s.Citation(
            chunk_id=8812,
            title="Lecture 7 slides",
            kind="slides",
            platform="canvas",
            course_code="COMPSCI 311",
            page=12,
            url="https://example.instructure.com/courses/cs311/files/7",
            deep_link="https://example.instructure.com/courses/cs311/files/7",
            quote="Memoization stores solutions to subproblems so each is solved once.",
            last_synced_at=n - timedelta(minutes=12),
            status="current",
        ),
        9930: s.Citation(
            chunk_id=9930,
            title="Lecture Nov 11",
            kind="transcript",
            platform="echo360",
            course_code="COMPSCI 311",
            start_s=1421,
            end_s=1481,
            url="https://example.echo360.com/lesson/nov11",
            deep_link="https://example.echo360.com/lesson/nov11?time=1421",
            quote="...so when we memoize, we're trading memory for time...",
            last_synced_at=n - timedelta(days=3),
            status="current",
        ),
    }
    return [known[i] for i in ids if i in known]


def study_set() -> s.StudySet:
    return s.StudySet(
        id=mid("studyset/fc1"),
        type="flashcards",
        title="COMPSCI 311 DP flashcards",
        course_id=mid("course/cs311"),
        created_at=_now() - timedelta(hours=1),
        payload={
            "cards": [
                {
                    "front": "What does memoization store?",
                    "back": "Solutions to subproblems, so each is computed once.",
                    "chunk_ids": [8812],
                },
                {
                    "front": "Memoization trades what for what?",
                    "back": "Memory for time.",
                    "chunk_ids": [9930],
                },
            ]
        },
    )


def study_blocks() -> list[s.StudyBlock]:
    start = (_now() + timedelta(days=1)).replace(minute=0, second=0)
    return [
        s.StudyBlock(
            id=mid(f"block/{i}"),
            title=f"CS 311 midterm prep ({i + 1}/2)",
            start_at=start + timedelta(days=i),
            end_at=start + timedelta(days=i, hours=1),
            course_id=mid("course/cs311"),
            item_id=mid("item/mid1"),
            status="proposed",
        )
        for i in range(2)
    ]
