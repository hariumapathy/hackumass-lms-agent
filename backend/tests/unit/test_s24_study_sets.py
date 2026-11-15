"""S24: create_study_set validation, citation filtering, runtime event, per-user listing."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call
from fastapi.testclient import TestClient

from app.agent.runtime import ChatRuntime, _flat_schema
from app.agent.store import MemoryChatStore
from app.agent.tools import AGENT_TOOLS, STUDY_SET_TOOL
from app.agent.tools.context import RunCtx
from app.agent.tools.mock_source import MockToolData
from app.agent.tools.runner import invoke
from app.agent.tools.study_sets import CreateStudySetArgs
from app.api import mock_data as mock
from app.api import schemas as s
from app.core.auth import UserCtx
from app.core.clock import FixedClock
from app.main import create_app
from tests.helpers import OTHER_USER_ID, TEST_USER_ID, auth_header

NOW = datetime(2026, 11, 14, 17, 0, tzinfo=UTC)  # Sat Nov 14, noon in New York


def ctx(allowed: set[int] | None = None) -> RunCtx:
    run = RunCtx(
        user_id=TEST_USER_ID,
        timezone="America/New_York",
        clock=FixedClock(NOW),
        data=MockToolData(now=NOW),
    )
    run.allowed_chunk_ids = {8812, 8813, 9930} if allowed is None else allowed
    return run


def cards(n: int, ids: list[int] | None = None) -> list[dict[str, Any]]:
    return [{"front": f"Q{i}", "back": f"A{i}", "chunk_ids": ids or [8812]} for i in range(n)]


def mcq(answer: int = 1, choices: int = 4) -> dict[str, Any]:
    return {
        "type": "mcq",
        "prompt": "What does memoization store?",
        "choices": [f"choice {i}" for i in range(choices)],
        "answer_index": answer,
        "explanation": "See slide 12.",
        "chunk_ids": [8812],
    }


async def call(args: dict[str, Any], run: RunCtx | None = None) -> tuple[str, RunCtx]:
    run = run or ctx()
    return await invoke(STUDY_SET_TOOL, run, json.dumps(args)), run


# --- S24-T01 (in-memory until S01): each type saves and returns a small summary ---------------


@pytest.mark.parametrize(
    "args",
    [
        {
            "type": "flashcards",
            "title": "DP cards",
            "course": "CS 311",
            "flashcards": {"cards": cards(5)},
        },
        {
            "type": "quiz",
            "title": "DP quiz",
            "quiz": {
                "questions": [
                    mcq(),
                    mcq(2),
                    {
                        "type": "short",
                        "prompt": "Define memoization",
                        "answer_text": "Caching answers",
                        "explanation": "x",
                        "chunk_ids": [9930],
                    },
                ]
            },
        },
        {
            "type": "plan",
            "title": "Midterm plan",
            "plan": {
                "days": [
                    {
                        "date": "2026-11-15",
                        "minutes": 60,
                        "topics": ["DP"],
                        "tasks": [{"text": "Re-read slides 12-14", "chunk_ids": [8812, 8813]}],
                    }
                ]
            },
        },
    ],
    ids=["flashcards", "quiz", "plan"],
)
async def test_s24_t01_each_type_creates_set_with_summary(args: dict[str, Any]) -> None:
    out, run = await call(args)
    summary = json.loads(out)["results"][0]
    assert summary["type"] == args["type"] and summary["title"] == args["title"]
    assert "payload" not in summary  # the model only gets a summary back
    assert len(run.study_sets) == 1 and run.study_sets[0].type == args["type"]
    if args.get("course"):
        assert run.study_sets[0].course_id == mock.mid("course/cs311")


# --- S24-T02: MCQ shape ------------------------------------------------------------------------


@pytest.mark.parametrize("question", [mcq(choices=3), mcq(answer=4), mcq(answer=-1)])
async def test_s24_t02_bad_mcq_rejected_readably(question: dict[str, Any]) -> None:
    out, run = await call(
        {"type": "quiz", "title": "q", "quiz": {"questions": [question, mcq(), mcq()]}}
    )
    assert out.startswith("Invalid arguments for create_study_set") and not run.study_sets


async def test_s24_t02_duplicate_choices_rejected() -> None:
    dup = mcq() | {"choices": ["a", "a", "b", "c"]}
    out, _ = await call({"type": "quiz", "title": "q", "quiz": {"questions": [dup, mcq(), mcq()]}})
    assert "different" in out


# --- S24-T03 / T04: citation filtering ------------------------------------------------------------


async def test_s24_t03_items_with_only_invalid_ids_removed() -> None:
    deck = cards(9) + [{"front": "made up", "back": "x", "chunk_ids": [424242]}]
    out, run = await call({"type": "flashcards", "title": "t", "flashcards": {"cards": deck}})
    summary = json.loads(out)["results"][0]
    assert summary["counts"] == {"cards": 9} and summary["removed_uncited_items"] == 1
    assert all(c["chunk_ids"] == [8812] for c in run.study_sets[0].payload["cards"])


async def test_s24_t03_mixed_ids_keep_only_valid() -> None:
    _, run = await call(
        {"type": "flashcards", "title": "t", "flashcards": {"cards": cards(5, ids=[8812, 777])}}
    )
    assert run.study_sets[0].payload["cards"][0]["chunk_ids"] == [8812]


async def test_s24_t04_more_than_30_percent_uncited_is_rejected() -> None:
    deck = cards(3) + cards(2, ids=[424242])
    out, run = await call({"type": "flashcards", "title": "t", "flashcards": {"cards": deck}})
    assert out.startswith("create_study_set rejected:") and "search_materials" in out
    assert not run.study_sets


# --- S24-T05: plan dates ------------------------------------------------------------------------


async def test_s24_t05_plan_dates_outside_today_to_exam_rejected() -> None:
    exam = next(i for i in mock.items() if i.title == "Midterm 1")

    def plan(day: str) -> dict[str, Any]:
        return {
            "type": "plan",
            "title": "p",
            "exam_item_id": str(exam.id),
            "plan": {
                "days": [
                    {
                        "date": day,
                        "minutes": 30,
                        "topics": ["DP"],
                        "tasks": [{"text": "x", "chunk_ids": [8812]}],
                    }
                ]
            },
        }

    past, _ = await call(plan("2026-11-13"))
    assert past.startswith("create_study_set rejected:") and "outside" in past
    assert exam.due_at is not None
    after_exam = (exam.due_at + timedelta(days=3)).date().isoformat()
    late, _ = await call(plan(after_exam))
    assert late.startswith("create_study_set rejected:")
    ok, run = await call(plan("2026-11-15"))
    assert run.study_sets, ok


# --- S24-T06: type/payload mismatch ------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        {"type": "quiz", "title": "t", "flashcards": {"cards": cards(5)}},
        {"type": "flashcards", "title": "t"},
        {
            "type": "flashcards",
            "title": "t",
            "flashcards": {"cards": cards(5)},
            "quiz": {"questions": [mcq(), mcq(), mcq()]},
        },
        {"type": "flashcards", "title": "t", "flashcards": {"cards": cards(4)}},  # < 5 cards
    ],
)
async def test_s24_t06_type_payload_mismatch_rejected(args: dict[str, Any]) -> None:
    out, run = await call(args)
    assert out.startswith("Invalid arguments for create_study_set") and not run.study_sets


def test_s24_schema_is_flat_for_gemini() -> None:
    schema = json.dumps(_flat_schema(CreateStudySetArgs))
    assert "$ref" not in schema and "$defs" not in schema and '"title": "Card"' not in schema
    assert "front" in schema and "answer_index" in schema


# --- S24-T07: study_set SSE event from the real tool ------------------------------------------


async def test_s24_t07_runtime_emits_study_set_and_saves_it() -> None:
    store = MemoryChatStore()
    model = ScriptedModel(
        [
            [
                function_call(
                    "search_materials", {"query": "memoization dynamic programming"}, call_id="c1"
                )
            ],
            [
                function_call(
                    "create_study_set",
                    {"type": "flashcards", "title": "DP cards", "flashcards": {"cards": cards(5)}},
                    call_id="c2",
                )
            ],
            [assistant_message("Here are 5 flashcards.")],
        ]
    )
    runtime = ChatRuntime(
        store=store,
        data_factory=lambda _u: MockToolData(now=NOW),
        model_factory=lambda _c: (model, "scripted"),
        clock=FixedClock(NOW),
        tools=AGENT_TOOLS,
    )
    user = UserCtx(user_id=TEST_USER_ID)
    events = [e async for e in runtime.run(user, s.ChatRequest(message="5 DP flashcards"))]
    types = [e.type for e in events]
    assert types.count("study_set") == 1 and types.index("study_set") < types.index("citations")
    event = next(e for e in events if isinstance(e, s.StudySetEvent))
    assert len(event.study_set.payload["cards"]) == 5
    statuses = [e for e in events if isinstance(e, s.StatusEvent) and e.tool == "create_study_set"]
    assert statuses[0].label == "Making your flashcards…" and statuses[-1].state == "done"
    assert [x.id for x in await store.study_sets(TEST_USER_ID)] == [event.study_set.id]
    done = events[-1]
    assert isinstance(done, s.DoneEvent)
    detail = await store.conversation(TEST_USER_ID, events[0].conversation_id)  # type: ignore[union-attr]
    assert detail and detail.messages[-1].study_set_ids == [event.study_set.id]


# --- S24-T08: only the caller's sets (in-memory until S01) ------------------------------------


def test_s24_t08_get_study_sets_only_callers() -> None:
    app = create_app()
    store = MemoryChatStore()
    app.state.chat_runtime = ChatRuntime(
        store=store,
        data_factory=lambda _u: MockToolData(),
        model_factory=lambda _c: (ScriptedModel([]), "x"),
        clock=FixedClock(NOW),
    )
    mine = mock.study_set()
    import asyncio

    asyncio.run(store.save_study_set(TEST_USER_ID, mine))
    client = TestClient(app)
    assert [x["id"] for x in client.get("/study-sets", headers=auth_header()).json()] == [
        str(mine.id)
    ]
    other = auth_header(OTHER_USER_ID)
    assert client.get("/study-sets", headers=other).json() == []
    assert client.get(f"/study-sets/{mine.id}", headers=other).status_code == 404
    assert client.get(f"/study-sets/{mine.id}", headers=auth_header()).status_code == 200
    assert UUID(client.get(f"/study-sets/{mine.id}", headers=auth_header()).json()["id"])
