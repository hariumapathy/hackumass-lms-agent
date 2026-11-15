"""Model evals (S26): run golden student questions through the real agent and score them.

`uv run app evals [--only G01,G05] [--model gemini-3.5-flash] [--delay 4]` prints a table and
writes JSON + Markdown reports to `backend/evals/reports/` (git-ignored). Uses real models, so it
never runs in CI; `tests/runtime/test_s26_evals.py` covers the scorer and runner with
ScriptedModel.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from pydantic import BaseModel

from app.api import schemas as s
from app.core.auth import UserCtx

EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
EVAL_USER = UserCtx(user_id=UUID("00000000-0000-4000-8000-0000000e7a15"), email=None)


class StudySetExpectation(BaseModel):
    type: str
    min_items: int = 1


class GoldenCase(BaseModel):
    id: str
    question: str
    topic: str = ""
    requires_tools: list[str] = []
    expect_tools_any: list[str] = []
    expect_tools_all: list[str] = []
    expect_answer_contains: list[str] = []
    expect_answer_contains_any: list[str] = []
    expect_answer_not_contains: list[str] = []
    expect_citations: bool | None = None
    expect_citation_ids_any: list[int] = []
    expect_study_set: StudySetExpectation | None = None
    expect_blocks: bool | None = None
    max_latency_s: float = 45


@dataclass
class Outcome:
    tools: list[str] = field(default_factory=list)
    failed_tools: list[str] = field(default_factory=list)
    answer: str = ""
    citation_ids: list[int] = field(default_factory=list)
    dropped_ids: list[int] = field(default_factory=list)
    study_sets: list[dict[str, Any]] = field(default_factory=list)
    blocks: int = 0
    error: str | None = None
    latency_s: float = 0.0


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class CaseResult:
    id: str
    topic: str
    question: str
    status: str  # pass | fail | skip
    checks: list[Check]
    outcome: Outcome


def load_cases(path: Path | None = None) -> list[GoldenCase]:
    raw = yaml.safe_load((path or EVALS_DIR / "golden.yaml").read_text(encoding="utf-8"))
    cases = [GoldenCase.model_validate(item) for item in raw]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate golden ids")
    return cases


def _has(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def _items(study_set: dict[str, Any]) -> int:
    payload = study_set.get("payload") or {}
    for key in ("cards", "questions", "sessions", "items"):
        if isinstance(payload.get(key), list):
            return len(payload[key])
    return 0


def score(case: GoldenCase, out: Outcome) -> list[Check]:
    checks = [Check("no_error", out.error is None, out.error or "")]
    tools = set(out.tools)
    if case.expect_tools_any:
        checks.append(
            Check("tools_any", bool(tools & set(case.expect_tools_any)), f"called {sorted(tools)}")
        )
    if case.expect_tools_all:
        missing = set(case.expect_tools_all) - tools
        checks.append(Check("tools_all", not missing, f"missing {sorted(missing)}"))
    for needle in case.expect_answer_contains:
        checks.append(Check(f"contains:{needle}", _has(out.answer, needle)))
    if case.expect_answer_contains_any:
        hit = [n for n in case.expect_answer_contains_any if _has(out.answer, n)]
        checks.append(Check("contains_any", bool(hit), f"matched {hit}"))
    for needle in case.expect_answer_not_contains:
        checks.append(Check(f"not_contains:{needle}", not _has(out.answer, needle)))
    if case.expect_citations is True:
        checks.append(Check("has_citations", bool(out.citation_ids), f"{out.citation_ids}"))
    if case.expect_citation_ids_any:
        hit = set(out.citation_ids) & set(case.expect_citation_ids_any)
        checks.append(Check("citation_ids_any", bool(hit), f"cited {out.citation_ids}"))
    if case.expect_study_set:
        want = case.expect_study_set
        good = [
            st
            for st in out.study_sets
            if st.get("type") == want.type and _items(st) >= want.min_items
        ]
        checks.append(Check("study_set", bool(good), f"{len(out.study_sets)} sets"))
    if case.expect_blocks:
        checks.append(Check("blocks", out.blocks > 0, f"{out.blocks} blocks"))
    checks.append(Check("latency", out.latency_s <= case.max_latency_s, f"{out.latency_s:.1f}s"))
    return checks


async def run_case(runtime: Any, case: GoldenCase) -> Outcome:
    out = Outcome()
    start = time.perf_counter()
    async for ev in runtime.run(EVAL_USER, s.ChatRequest(message=case.question)):
        if isinstance(ev, s.StatusEvent) and ev.state != "started":
            out.tools.append(ev.tool)
            if ev.state == "failed":
                out.failed_tools.append(ev.tool)
        elif isinstance(ev, s.CitationsEvent):
            out.citation_ids = [c.chunk_id for c in ev.citations]
            out.dropped_ids = list(ev.dropped)
        elif isinstance(ev, s.StudySetEvent):
            out.study_sets.append(ev.study_set.model_dump(mode="json"))
        elif isinstance(ev, s.ApprovalRequiredEvent):
            out.blocks += len(ev.blocks)
        elif isinstance(ev, s.DoneEvent):
            out.answer = ev.final_text
        elif isinstance(ev, s.ErrorEvent):
            out.error = ev.code
    out.latency_s = round(time.perf_counter() - start, 2)
    return out


async def run_all(
    runtime: Any, cases: list[GoldenCase], delay_s: float = 0.0, sleep: Any = None
) -> list[CaseResult]:
    import asyncio

    sleep = sleep or asyncio.sleep
    available = {t.name for t in runtime.tools}
    results: list[CaseResult] = []
    for i, case in enumerate(cases):
        missing = set(case.requires_tools) - available
        if missing:
            results.append(
                CaseResult(
                    case.id,
                    case.topic,
                    case.question,
                    "skip",
                    [Check("requires_tools", False, f"missing {sorted(missing)}")],
                    Outcome(),
                )
            )
            continue
        if i and delay_s:
            await sleep(delay_s)  # stay under free-tier requests-per-minute limits
        outcome = await run_case(runtime, case)
        checks = score(case, outcome)
        status = "pass" if all(c.ok for c in checks) else "fail"
        results.append(CaseResult(case.id, case.topic, case.question, status, checks, outcome))
    return results


def summarize(results: list[CaseResult], model: str) -> dict[str, Any]:
    ran = [r for r in results if r.status != "skip"]
    passed = [r for r in ran if r.status == "pass"]
    latencies = [r.outcome.latency_s for r in ran]
    cite_cases = [r for r in ran if any(c.name == "has_citations" for c in r.checks)]
    return {
        "model": model,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cases": len(results),
        "ran": len(ran),
        "skipped": len(results) - len(ran),
        "passed": len(passed),
        "pass_rate": round(len(passed) / len(ran), 3) if ran else 0.0,
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "max_latency_s": max(latencies) if latencies else 0.0,
        "avg_tool_calls": round(sum(len(r.outcome.tools) for r in ran) / len(ran), 2) if ran else 0,
        "failed_tool_calls": sum(len(r.outcome.failed_tools) for r in ran),
        "errors": sum(1 for r in ran if r.outcome.error),
        "citation_cases_with_citations": sum(1 for r in cite_cases if r.outcome.citation_ids),
        "citation_cases": len(cite_cases),
        "dropped_citations": sum(len(r.outcome.dropped_ids) for r in ran),
    }


def format_table(results: list[CaseResult], summary: dict[str, Any]) -> str:
    lines = [
        f"## Eval: {summary['model']} ({summary['at']})",
        "",
        f"**Pass rate {summary['passed']}/{summary['ran']} ({summary['pass_rate']:.0%})**, "
        f"skipped {summary['skipped']}, avg latency {summary['avg_latency_s']} s "
        f"(max {summary['max_latency_s']} s), avg tool calls {summary['avg_tool_calls']}, "
        f"errors {summary['errors']}, dropped citations {summary['dropped_citations']}.",
        "",
        "| ID | Topic | Result | Tools | Latency | Failed checks |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        failed = "; ".join(
            f"{c.name} ({c.detail})" if c.detail else c.name for c in r.checks if not c.ok
        )
        tools = ", ".join(r.outcome.tools) or "-"
        lines.append(
            f"| {r.id} | {r.topic} | {r.status} | {tools} | "
            f"{r.outcome.latency_s:.1f}s | {failed or '-'} |"
        )
    return "\n".join(lines) + "\n"


def write_report(results: list[CaseResult], summary: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    base = out_dir / f"{stamp}-{summary['model'].replace('/', '_')}"
    base.with_suffix(".json").write_text(
        json.dumps({"summary": summary, "results": [asdict(r) for r in results]}, indent=2),
        encoding="utf-8",
    )
    base.with_suffix(".md").write_text(format_table(results, summary), encoding="utf-8")
    return base
