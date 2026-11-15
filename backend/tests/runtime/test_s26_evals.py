"""S26 evals: golden file loads, scorer logic (T04), runner end to end with ScriptedModel (T05)."""

from datetime import UTC, datetime

from agents.testing import ScriptedModel, assistant_message, function_call

from app.agent.runtime import ChatRuntime
from app.agent.store import MemoryChatStore
from app.agent.tools.mock_source import MockToolData
from app.core.clock import FixedClock
from app.evals import (
    GoldenCase,
    Outcome,
    StudySetExpectation,
    format_table,
    load_cases,
    run_all,
    score,
    summarize,
)

NOW = datetime.now(UTC).replace(microsecond=0)


def test_s26_golden_file_loads_with_unique_ids() -> None:
    cases = load_cases()
    assert len(cases) >= 12
    assert {"G01", "G11"} <= {c.id for c in cases}


def _names(checks) -> dict[str, bool]:  # noqa: ANN001
    return {c.name: c.ok for c in checks}


def test_s26_t04_scorer_each_expectation_type() -> None:
    case = GoldenCase(
        id="X",
        question="q",
        expect_tools_any=["get_items"],
        expect_tools_all=["get_items", "search_materials"],
        expect_answer_contains=["Lab 4"],
        expect_answer_contains_any=["today", "tonight"],
        expect_answer_not_contains=["HW 6"],
        expect_citations=True,
        expect_citation_ids_any=[8812],
        expect_study_set=StudySetExpectation(type="flashcards", min_items=2),
        expect_blocks=True,
        max_latency_s=10,
    )
    good = Outcome(
        tools=["get_items", "search_materials"],
        answer="Lab 4 is due TODAY.",
        citation_ids=[8812],
        study_sets=[{"type": "flashcards", "payload": {"cards": [{}, {}]}}],
        blocks=2,
        latency_s=3,
    )
    assert all(_names(score(case, good)).values())
    bad = Outcome(
        tools=["get_changes"],
        answer="HW 6 is late",
        study_sets=[{"type": "quiz", "payload": {"questions": [{}]}}],
        error="model_error",
        latency_s=30,
    )
    result = _names(score(case, bad))
    assert not any(result.values()), result


async def test_s26_t05_runner_end_to_end_with_scripted_model() -> None:
    model = ScriptedModel(
        [
            [function_call("get_items", {}, call_id="c1")],
            [assistant_message("Lab 4 and HW 5 are due this week.")],
            [assistant_message("I couldn't find BIOLOGY 101 in your courses.")],
        ]
    )
    runtime = ChatRuntime(
        store=MemoryChatStore(),
        data_factory=lambda _u: MockToolData(now=NOW),
        model_factory=lambda _c: (model, "scripted/test"),
        clock=FixedClock(NOW),
    )
    cases = [c for c in load_cases() if c.id in {"G01", "G08"}]
    cases.append(GoldenCase(id="GX", question="q", requires_tools=["not_built_yet"]))
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    results = await run_all(runtime, cases, delay_s=2, sleep=fake_sleep)
    by_id = {r.id: r for r in results}
    assert by_id["G01"].status == "pass", by_id["G01"].checks
    assert by_id["G01"].outcome.tools == ["get_items"]
    assert by_id["G08"].status == "pass", by_id["G08"].checks
    assert by_id["GX"].status == "skip"
    assert slept == [2]
    summary = summarize(results, "scripted/test")
    assert summary["pass_rate"] == 1.0 and summary["skipped"] == 1
    table = format_table(results, summary)
    assert "| G01 |" in table and "Pass rate 2/2" in table
