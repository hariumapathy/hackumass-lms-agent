"""S03 seed data: unit tests (no database). docs/specs/S03-seed-data.md."""

import json
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.api import mock_data
from app.core.embeddings import (
    EmbeddingsConfigError,
    FakeEmbeddings,
    get_embeddings,
)
from app.core.hashing import content_hash
from app.core.settings import Settings
from app.db.seed import SEED_DIR, SeedError, load_fixtures, seed_id
from app.db.seed_dates import RelativeDateError, resolve

NY = "America/New_York"


# --- S03-T02: relative dates ------------------------------------------------------------------
def test_s03_t02_days_with_time_use_local_wall_time() -> None:
    now = datetime(2026, 11, 14, 23, 30, tzinfo=UTC)  # 18:30 EST on Nov 14
    assert resolve("+6d 19:00", now, NY) == datetime(2026, 11, 21, 0, 0, tzinfo=UTC)
    assert resolve("+0d 23:59", now, NY) == datetime(2026, 11, 15, 4, 59, tzinfo=UTC)


def test_s03_t02_local_date_not_utc_date() -> None:
    # 01:00 UTC Nov 15 is still Nov 14 in New York: "+0d 09:00" means Nov 14 09:00 local.
    now = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)
    assert resolve("+0d 09:00", now, NY) == datetime(2026, 11, 14, 14, 0, tzinfo=UTC)


def test_s03_t02_dst_boundary_keeps_wall_time() -> None:
    now = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)  # 12:00 EDT, DST ends Nov 1
    assert resolve("+2d 19:00", now, NY) == datetime(2026, 11, 3, 0, 0, tzinfo=UTC)  # 19:00 EST
    assert resolve("+0d 19:00", now, NY) == datetime(2026, 10, 31, 23, 0, tzinfo=UTC)  # EDT
    # Without a time, the local time of day is kept across the change (12:00 -> 12:00).
    assert resolve("+2d", now, NY) == datetime(2026, 11, 2, 17, 0, tzinfo=UTC)


def test_s03_t02_hours_and_minutes_are_exact_durations() -> None:
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    assert resolve("-20h", now, NY) == datetime(2026, 11, 13, 16, 0, tzinfo=UTC)
    assert resolve("+45m", now, NY) == datetime(2026, 11, 14, 12, 45, tzinfo=UTC)
    assert resolve("now", now, NY) == now


@pytest.mark.parametrize("bad", ["3d", "+3x", "+2h 10:00", "+1d 25:00", "tomorrow", ""])
def test_s03_t02_bad_expressions_rejected(bad: str) -> None:
    with pytest.raises(RelativeDateError):
        resolve(bad, datetime(2026, 11, 14, tzinfo=UTC), NY)


# --- S03-T03: fake embeddings -----------------------------------------------------------------
async def test_s03_t03_fake_embeddings_deterministic_and_normalized() -> None:
    fake = FakeEmbeddings()
    a1, a2, b = await fake.embed(["memoization", "memoization", "knapsack"])
    assert a1 == a2
    assert a1 != b
    assert len(a1) == 1536
    assert math.isclose(math.sqrt(sum(x * x for x in a1)), 1.0, rel_tol=1e-9)


def test_s03_gemini_without_key_fails_clearly() -> None:
    settings = Settings(embeddings_provider="gemini", gemini_api_key=None)
    with pytest.raises(EmbeddingsConfigError, match="GEMINI_API_KEY"):
        get_embeddings(settings)


# --- Fixtures ---------------------------------------------------------------------------------
def test_s03_fixtures_load_and_cover_ui_enums() -> None:
    fx = load_fixtures()
    items = [i for c in fx["content"].values() for i in c["items"]]
    posts = [p for c in fx["content"].values() for p in c["posts"]]
    mats = [m for c in fx["content"].values() for m in c["materials"]]
    assert {i["type"] for i in items} == {"assignment", "exam", "quiz", "lab", "project", "other"}
    assert {c["status"] for c in fx["connections"]} >= {"active", "needs_reconnect"}
    assert {p["kind"] for p in posts} >= {"announcement", "piazza"}
    assert {m["kind"] for m in mats} == {"file", "page", "syllabus", "transcript"}
    assert {b["status"] for b in fx["study_blocks"]} == {"proposed", "approved", "declined"}
    assert {s["type"] for s in fx["study_sets"]} >= {"quiz", "flashcards"}
    assert any(i.get("status") == "removed" for i in items)
    assert len(fx["courses"]) == 4


def test_s03_ids_match_s02_mock_data() -> None:
    """Mock mode (S02) and seeded mode show the same courses, items, posts and changes."""
    fx = load_fixtures()
    item_keys = {i["key"] for c in fx["content"].values() for i in c["items"]}
    post_keys = {p["key"] for c in fx["content"].values() for p in c["posts"]}
    for c in mock_data.course_summaries():
        key = next(k for k, *_ in mock_data.COURSES if mock_data.mid(f"course/{k}") == c.id)
        assert seed_id("hackumass-mock", f"course/{key}") == c.id
    for it in mock_data.items():
        assert any(seed_id("hackumass-mock", f"item/{k}") == it.id for k in item_keys), it.title
    for po in mock_data.posts():
        assert any(seed_id("hackumass-mock", f"post/{k}") == po.id for k in post_keys), po.title
    change_keys = {c["key"] for c in fx["changes"]}
    for ch in mock_data.changes():
        assert any(seed_id("hackumass-mock", f"change/{k}") == ch.id for k in change_keys)


def test_s03_unknown_course_reference_is_listed(tmp_path: Path) -> None:
    shutil.copytree(SEED_DIR, tmp_path / "seed")
    sem_path = tmp_path / "seed" / "semester.json"
    sem = json.loads(sem_path.read_text(encoding="utf-8"))
    sem["study_blocks"][0]["course"] = "cs999"
    sem["study_sets"][0]["payload"]["cards"][0]["refs"] = ["cs311/l7#99"]
    sem_path.write_text(json.dumps(sem), encoding="utf-8")
    with pytest.raises(SeedError) as err:
        load_fixtures(tmp_path / "seed")
    assert "cs999" in str(err.value) and "cs311/l7#99" in str(err.value)


def test_s10_t01_content_hash_stable_across_key_order() -> None:
    a = content_hash({"title": "HW 5", "points": 60, "due_at": datetime(2026, 11, 16, tzinfo=UTC)})
    b = content_hash({"due_at": datetime(2026, 11, 16, tzinfo=UTC), "points": 60, "title": "HW 5"})
    assert a == b
    assert a != content_hash({"title": "HW 5", "points": 50, "due_at": None})
