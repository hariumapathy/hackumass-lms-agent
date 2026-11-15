"""S21 read tools against the mock semester (`MockToolData`). The DB-backed versions of these
tests (S21-T02, T04-T06, T09-T11 on the S03 seed) come with DbToolData after S01/S03."""

import json
from datetime import UTC, date, datetime, timedelta

from app.agent.tools import READ_TOOLS
from app.agent.tools.args import (
    FetchLatestArgs,
    GetChangesArgs,
    GetCourseOverviewArgs,
    GetItemsArgs,
    GetMaterialArgs,
    SearchMaterialsArgs,
)
from app.agent.tools.context import RunCtx
from app.agent.tools.mock_source import MockToolData
from app.agent.tools.read import (
    fetch_latest,
    get_changes,
    get_course_overview,
    get_items,
    get_material,
    search_materials,
)
from app.agent.tools.runner import invoke
from app.api import mock_data as mock
from app.core.clock import FixedClock
from tests.helpers import TEST_USER_ID

NOW = datetime.now(UTC).replace(microsecond=0)


def ctx(data: MockToolData | None = None) -> RunCtx:
    return RunCtx(
        user_id=TEST_USER_ID,
        timezone="America/New_York",
        clock=FixedClock(NOW),
        data=data or MockToolData(now=NOW),
    )


async def test_s21_t02_get_items_filters_sorts_and_hides_past() -> None:
    res = await get_items(ctx(), GetItemsArgs())
    titles = [r["title"] for r in res.results]
    assert "HW 6" not in titles  # due yesterday: past excluded by default
    assert titles[0] == "Lab 4: Testing"
    assert res.results[0]["due_in"] in {"in 4 hours", "in 5 hours"}
    past = await get_items(ctx(), GetItemsArgs(include_past=True))
    assert past.results[0]["title"] == "HW 6"
    exams = await get_items(ctx(), GetItemsArgs(course="CS 311", type="exam"))
    assert [r["title"] for r in exams.results] == ["Midterm 1"]
    week = await get_items(ctx(), GetItemsArgs(to_date=(NOW + timedelta(days=4)).date()))
    assert "Final Exam" not in [r["title"] for r in week.results]


async def test_s21_t02_unknown_course_note() -> None:
    res = await get_items(ctx(), GetItemsArgs(course="BIOLOGY 101"))
    assert res.results == [] and res.note and "COMPSCI 311" in res.note


async def test_s21_t03_local_times_in_profile_timezone() -> None:
    res = await get_items(ctx(), GetItemsArgs(course="CS 311", type="exam"))
    item = res.results[0]
    assert item["due_in"] in {"in 5 days", "in 6 days"}
    assert item["due_local"].endswith(("AM", "PM")) and "," in item["due_local"]
    assert item["changed_fields"] == ["due_at"]


async def test_s21_t04_get_changes_includes_midterm_moved() -> None:
    res = await get_changes(ctx(), GetChangesArgs(course="CS 311"))
    summaries = [r["summary"] for r in res.results]
    assert "COMPSCI 311 Midterm 1 moved 2 days later" in summaries
    moved = next(r for r in res.results if r["field"] == "due_at")
    assert moved["new"].endswith(("AM", "PM"))  # ISO time turned into local time


async def test_s21_t05_search_finds_slides_and_transcript_and_wraps_posts() -> None:
    res = await search_materials(
        ctx(), SearchMaterialsArgs(query="memoization memory time", course="CS 311")
    )
    ids = [r["chunk_id"] for r in res.results]
    assert 8812 in ids and 9930 in ids
    slide = next(r for r in res.results if r["chunk_id"] == 8812)
    assert slide["text"].startswith("[COMPSCI 311 · Lecture 7 slides · p.12]\n")
    transcript = next(r for r in res.results if r["chunk_id"] == 9930)
    assert transcript["time"] == "23:41"
    posts = await search_materials(ctx(), SearchMaterialsArgs(query="midterm graphs", kind="post"))
    assert posts.results and all("<untrusted source=" in r["text"] for r in posts.results)
    assert res.coverage.searched == ["canvas", "gradescope", "echo360"]
    assert res.coverage.needs_reconnect == ["echo360"]


async def test_s21_t10_zero_results_records_miss_and_hints_fetch_latest() -> None:
    data = MockToolData(now=NOW)
    res = await search_materials(
        ctx(data), SearchMaterialsArgs(query="quantum chromodynamics", course="MATH 235")
    )
    assert res.results == [] and res.note and "fetch_latest(course='MATH 235')" in res.note
    assert data.misses and data.misses[0][1] == "quantum chromodynamics"


async def test_s21_get_material_page_range_and_overview() -> None:
    material_id = str(mock.mid("material/cs311/l7"))
    res = await get_material(ctx(), GetMaterialArgs(material_id=material_id, pages="13-14"))
    assert [r["page"] for r in res.results] == [13, 14]
    unknown = await get_material(ctx(), GetMaterialArgs(material_id="nope"))
    assert unknown.results == [] and unknown.note
    ov = await get_course_overview(ctx(), GetCourseOverviewArgs(course="algorithms"))
    overview = ov.results[0]
    assert overview["code"] == "COMPSCI 311"
    assert overview["syllabus_chunks"] and overview["syllabus_chunks"][0]["chunk_id"] == 8790
    assert overview["upcoming"][0]["title"] == "HW 5: Dynamic Programming"


async def test_s21_t11_fetch_latest_statuses() -> None:
    ok = await fetch_latest(ctx(), FetchLatestArgs(course="CS 311"))
    assert ok.results[0]["status"] == "completed"
    reconnect = await fetch_latest(ctx(), FetchLatestArgs(source="echo360"))
    assert reconnect.results[0]["status"] == "needs_reconnect"
    missing = await fetch_latest(ctx(), FetchLatestArgs(source="piazza"))
    assert missing.results[0]["status"] == "not_connected"


async def test_s21_t07_registry_invoke_collects_chunk_ids_and_texts() -> None:
    spec = next(t for t in READ_TOOLS if t.name == "search_materials")
    run = ctx()
    out = json.loads(await invoke(spec, run, '{"query": "memoization"}'))
    assert out["results"] and 8812 in run.allowed_chunk_ids
    assert "Memoization stores" in run.chunk_texts[8812]
    assert {t.name for t in READ_TOOLS} == {
        "get_items",
        "get_changes",
        "search_materials",
        "get_material",
        "get_course_overview",
        "fetch_latest",
    }


def test_s21_args_nulls_mean_default() -> None:
    args = SearchMaterialsArgs.model_validate({"query": "dp", "kind": None, "k": None})
    assert args.kind == "any" and args.k == 8


def test_s21_args_dates_parse() -> None:
    assert GetItemsArgs.model_validate({"from_date": "2026-11-16"}).from_date == date(2026, 11, 16)
