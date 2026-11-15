"""S22: agent runtime. Uses the Agents SDK's ScriptedModel (no real LLM, no network)."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call
from agents.tracing import get_trace_provider
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agent.prompts import PromptContext, build_instructions
from app.agent.runtime import ChatRuntime, RunState, history_window, map_stream_event
from app.agent.store import MemoryChatStore
from app.agent.tools import READ_TOOLS
from app.agent.tools.context import RunCtx
from app.agent.tools.courses import CourseRef
from app.agent.tools.mock_source import MockToolData
from app.agent.tools.results import ToolResult
from app.agent.tools.runner import ToolSpec
from app.api import mock_data as mock
from app.api import schemas as s
from app.api.sse import parse_sse
from app.core.auth import UserCtx
from app.core.clock import FixedClock
from app.main import create_app
from tests.helpers import TEST_USER_ID, auth_header

NOW = datetime.now(UTC).replace(microsecond=0)
USER = UserCtx(user_id=TEST_USER_ID, email="student@umass.edu")


def runtime(
    model: ScriptedModel, tools: list[ToolSpec] | None = None, store: MemoryChatStore | None = None
) -> ChatRuntime:
    return ChatRuntime(
        store=store or MemoryChatStore(),
        data_factory=lambda _u: MockToolData(now=NOW),
        model_factory=lambda _c: (model, "scripted/test"),
        clock=FixedClock(NOW),
        tools=tools,
    )


async def collect(
    rt: ChatRuntime, message: str = "What's due this week?", conversation_id: UUID | None = None
) -> list[s.ChatEvent]:
    req = s.ChatRequest(message=message, conversation_id=conversation_id)
    return [ev async for ev in rt.run(USER, req)]


def types(events: list[s.ChatEvent]) -> list[str]:
    return [e.type for e in events]


async def test_S25_T01_T09_real_tool_persists_and_emits_one_approval() -> None:
    local_start = (NOW + timedelta(days=1)).replace(tzinfo=None).isoformat()
    model = ScriptedModel(
        [
            [
                function_call(
                    "add_study_block",
                    {
                        "title": "Review algorithms",
                        "start_local": local_start,
                        "duration_min": 30,
                        "course": None,
                        "item_id": None,
                    },
                    call_id="schedule",
                )
            ],
            [assistant_message("Please approve this study session.")],
        ]
    )
    store = MemoryChatStore()
    events = await collect(runtime(model, store=store), "Plan study time tomorrow.")
    approvals = [e for e in events if isinstance(e, s.ApprovalRequiredEvent)]
    assert len(approvals) == 1 and len(approvals[0].blocks) == 1
    # Plain, correct wording for one session (live test showed "Add 1 study sessions?").
    assert approvals[0].summary == "Add this study session?"
    saved = await store.blocks(TEST_USER_ID)
    assert saved == approvals[0].blocks and saved[0].status == "proposed"
    assert types(events).index("text") < types(events).index("approval_required")
    assert types(events)[-1] == "done"


# --- S22-T01: system prompt ---------------------------------------------------------------------


def test_s22_t01_build_instructions_has_context_and_rules() -> None:
    text = build_instructions(
        PromptContext(
            today_local="Sat Nov 14, 12:00 PM",
            timezone="America/New_York",
            courses=[
                CourseRef(
                    id=mock.mid("course/cs311"),
                    code="COMPSCI 311",
                    name="Introduction to Algorithms",
                )
            ],
            freshness={"canvas": "12 minutes ago", "echo360": "3 days ago"},
            needs_reconnect=["echo360"],
        )
    )
    for needle in [
        "Sat Nov 14, 12:00 PM",
        "America/New_York",
        "COMPSCI 311",
        "Introduction to Algorithms",
        "canvas: updated 12 minutes ago",
        "echo360: updated 3 days ago (needs the student to reconnect)",
        "[cite:chunk_<id>]",
        "Never write URLs",
        "<untrusted>",
        "fetch_latest",
        "add_study_block",
        "create_study_set",
        "Never invent dates",
    ]:
        assert needle in text, needle


# --- S22-T02: event mapping -------------------------------------------------------------------


async def test_s22_t02_map_stream_event_text_tool_start_done_and_error() -> None:
    from agents import Agent, Runner

    model = ScriptedModel(
        [
            [
                function_call("get_items", {"course": "CS 311", "type": "exam"}, call_id="c1"),
                function_call("get_items", {"type": "homework"}, call_id="c2"),
            ],
            [assistant_message("Done.")],
        ]
    )
    rt = runtime(model)
    state = RunState(specs={t.name: t for t in rt.tools})
    from app.agent.runtime import to_function_tool

    agent = Agent(
        name="t", instructions="x", model=model, tools=[to_function_tool(t) for t in rt.tools]
    )
    ctx = RunCtx(
        user_id=TEST_USER_ID,
        timezone="America/New_York",
        clock=FixedClock(NOW),
        data=MockToolData(now=NOW),
    )
    result = Runner.run_streamed(agent, input="hi", context=ctx)
    mapped: list[s.ChatEvent] = []
    async for ev in result.stream_events():
        mapped += map_stream_event(ev, state)
    statuses = [e for e in mapped if isinstance(e, s.StatusEvent)]
    by_id: dict[str, list[str]] = {}
    for st in statuses:
        by_id.setdefault(st.id, []).append(st.state)
    assert by_id == {"t1": ["started", "done"], "t2": ["started", "failed"]}
    assert statuses[0].label == "Checking your CS 311 exams…"
    assert [e.delta for e in mapped if isinstance(e, s.TextEvent)] == ["Done."]


# --- S22-T03: full ordering with real tools on mock data ---------------------------------------


async def test_s22_t03_events_ordered_and_citations_validated() -> None:
    model = ScriptedModel(
        [
            [
                function_call(
                    "search_materials", {"query": "memoization", "course": "CS 311"}, call_id="c1"
                )
            ],
            [
                assistant_message(
                    "Memoization stores answers to subproblems [cite:chunk_8812] "
                    "[cite:chunk_424242]."
                )
            ],
        ]
    )
    store = MemoryChatStore()
    events = await collect(runtime(model, store=store), "What is memoization?")
    t = types(events)
    assert t[0] == "run_started" and t[-1] == "done"
    assert t.index("status") < t.index("text") < t.index("citations") < t.index("done")
    assert [x for x in t if x in {"done", "error"}] == ["done"]
    cites = next(e for e in events if isinstance(e, s.CitationsEvent))
    assert [c.chunk_id for c in cites.citations] == [8812]
    assert cites.dropped == [424242]
    assert cites.citations[0].url.startswith("https://example.instructure.com/")
    done = events[-1]
    assert isinstance(done, s.DoneEvent)
    assert done.final_text == "Memoization stores answers to subproblems [cite:chunk_8812]."
    model.assert_complete()


async def test_s22_t03_citation_without_tool_result_is_dropped() -> None:
    model = ScriptedModel([[assistant_message("The midterm is Thursday [cite:chunk_8812].")]])
    events = await collect(runtime(model))
    cites = next(e for e in events if isinstance(e, s.CitationsEvent))
    assert cites.citations == [] and cites.dropped == [8812]


# --- S22-T04 / T05: study set + proposed blocks ------------------------------------------------


class _NoArgs(BaseModel):
    title: str = "x"


def _fake_set_tool() -> ToolSpec:
    async def fn(ctx: RunCtx, __: Any) -> ToolResult:
        ctx.study_sets.append(mock.study_set())
        return ToolResult(results=[{"study_set_id": "x"}])

    return ToolSpec("create_study_set", _NoArgs, fn)


def _fake_block_tool() -> ToolSpec:
    async def fn(ctx: RunCtx, __: Any) -> ToolResult:
        ctx.proposed_blocks.append(mock.study_blocks()[len(ctx.proposed_blocks) % 2])
        ctx.block_summary = "Add 1 session?"
        return ToolResult(results=[{"proposed": 1}])

    return ToolSpec("add_study_block", _NoArgs, fn)


async def test_s22_t04_t05_study_set_and_single_approval_after_text() -> None:
    tools = [*READ_TOOLS, _fake_set_tool(), _fake_block_tool()]
    model = ScriptedModel(
        [
            [
                function_call("create_study_set", {}, call_id="c1"),
                function_call("add_study_block", {}, call_id="c2"),
            ],
            [function_call("add_study_block", {}, call_id="c3")],
            [assistant_message("I made flashcards and proposed study time.")],
        ]
    )
    events = await collect(runtime(model, tools=tools))
    t = types(events)
    assert t.count("study_set") == 1 and t.count("approval_required") == 1
    last_text = max(i for i, x in enumerate(t) if x == "text")
    assert last_text < t.index("study_set") < t.index("approval_required") < t.index("citations")
    approval = next(e for e in events if isinstance(e, s.ApprovalRequiredEvent))
    assert len(approval.blocks) == 2 and approval.summary == "Add 1 session?"


# --- S22-T06 / T07: max turns, provider error -------------------------------------------------


async def test_s22_t06_max_turns_gives_error_last() -> None:
    steps = [[function_call("get_items", {}, call_id=f"c{i}")] for i in range(9)]
    events = await collect(runtime(ScriptedModel(steps)))
    assert events[-1].type == "error" and events[-1].code == "max_turns"  # type: ignore[union-attr]
    assert "done" not in types(events)


async def test_s22_t07_provider_exception_is_single_retryable_error() -> None:
    model = ScriptedModel([RuntimeError("provider exploded: secret details")])
    events = await collect(runtime(model))
    errors = [e for e in events if isinstance(e, s.ErrorEvent)]
    assert len(errors) == 1 and events[-1] is errors[0]
    assert errors[0].code == "model_error" and errors[0].retryable
    assert "secret" not in errors[0].message
    assert types(events)[0] == "run_started" and "done" not in types(events)


# --- S22-T08: history window --------------------------------------------------------------------


def test_s22_t08_history_keeps_last_12() -> None:
    msgs = [
        s.Message(
            id=mock.mid(f"m{i}"),
            role="user" if i % 2 == 0 else "assistant",
            text=f"msg {i}",
            created_at=NOW + timedelta(seconds=i),
        )
        for i in range(20)
    ]
    window = history_window(msgs)
    assert (
        len(window) == 12 and window[0]["content"] == "msg 8" and window[-1]["content"] == "msg 19"
    )


async def test_s22_t08_history_is_sent_to_the_model() -> None:
    store = MemoryChatStore()
    first = ScriptedModel([[assistant_message("Hi! How can I help?")]])
    events = await collect(runtime(first, store=store), "Hello")
    conv_id = events[0].conversation_id  # type: ignore[union-attr]
    second = ScriptedModel([[assistant_message("Sure.")]])
    await collect(runtime(second, store=store), "And tomorrow?", conversation_id=conv_id)
    sent = json.dumps(second.first_call.input, default=str)  # type: ignore[union-attr]
    assert "Hello" in sent and "Hi! How can I help?" in sent and "And tomorrow?" in sent


# --- S22-T09 (memory store until S01): messages + run log persisted ---------------------------


async def test_s22_t09_messages_and_run_log_saved_with_clean_text() -> None:
    store = MemoryChatStore()
    model = ScriptedModel(
        [
            [function_call("search_materials", {"query": "memoization"}, call_id="c1")],
            [assistant_message("Memo [cite:chunk_8812][cite:chunk_1].")],
        ]
    )
    events = await collect(runtime(model, store=store), "memoization?")
    conv_id = events[0].conversation_id  # type: ignore[union-attr]
    detail = await store.conversation(TEST_USER_ID, conv_id)
    assert detail is not None
    assert [m.role for m in detail.messages] == ["user", "assistant"]
    assistant = detail.messages[1]
    assert assistant.text == "Memo [cite:chunk_8812]."
    assert [c.chunk_id for c in assistant.citations] == [8812]
    run = next(iter(store.runs.values()))
    assert run.status == "done" and run.dropped_citations == [1]
    assert run.tool_calls and run.tool_calls[0]["tool"] == "search_materials"
    assert "memoization" not in json.dumps(run.tool_calls)  # no content in the run log
    # another student can't read it
    assert await store.conversation(UUID(int=7), conv_id) is None


# --- S22-T10: tracing disabled ------------------------------------------------------------------


def test_s22_t10_tracing_disabled_at_startup() -> None:
    import app.agent.runtime  # noqa: F401

    provider = get_trace_provider()
    assert getattr(provider, "_disabled", None) is True


# --- S22-T11: client disconnect cancels the run ------------------------------------------------


async def test_s22_t11_disconnect_cancels_run() -> None:
    store = MemoryChatStore()
    model = ScriptedModel(
        [
            [function_call("get_items", {}, call_id="c1")],
            [function_call("get_changes", {}, call_id="c2")],
            [assistant_message("never reached")],
        ]
    )
    gen = runtime(model, store=store).run(USER, s.ChatRequest(message="hi"))
    first = await gen.__anext__()
    assert first.type == "run_started"
    await gen.__anext__()  # first status event
    await gen.aclose()
    run = next(iter(store.runs.values()))
    assert run.status == "cancelled"
    assert model.remaining_steps >= 1


# --- route wiring -------------------------------------------------------------------------------


def test_s22_chat_route_uses_runtime_when_configured() -> None:
    app = create_app()
    model = ScriptedModel([[assistant_message("Hello from the agent.")]])
    app.state.chat_runtime = runtime(model)
    client = TestClient(app)
    with client.stream("POST", "/chat", json={"message": "hi"}, headers=auth_header()) as r:
        raw = "".join(r.iter_text())
    events = parse_sse(raw)
    assert [t for t, _ in events][0] == "run_started" and events[-1][0] == "done"
    assert events[-1][1]["final_text"] == "Hello from the agent."
    convs = client.get("/conversations", headers=auth_header()).json()
    assert len(convs) == 1 and convs[0]["title"] == "hi"
    detail = client.get(f"/conversations/{convs[0]['id']}", headers=auth_header())
    assert detail.status_code == 200 and len(detail.json()["messages"]) == 2


@pytest.mark.parametrize("mode", ["scripted", "auto"])
def test_s22_chat_mode_scripted_or_no_key_uses_scripted_stream(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from app.core.settings import get_settings

    monkeypatch.setenv("CHAT_MODE", mode)
    monkeypatch.setenv("GEMINI_API_KEY", "x" if mode == "scripted" else "")
    get_settings.cache_clear()
    assert create_app().state.chat_runtime is None
