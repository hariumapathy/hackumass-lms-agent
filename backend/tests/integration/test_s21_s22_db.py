"""DB-backed agent tools (S21), citations (S23), chat store (S22/S24) on the S03 seed.

Needs the local DB (`make db && make db-reset`); skips otherwise. Each test seeds its own student
under a unique namespace, so tests can re-run against the same DB.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call

from app.agent.citations import resolve_rows
from app.agent.db_store import DbChatStore
from app.agent.runtime import ChatRuntime
from app.agent.tools.args import (
    FetchLatestArgs,
    GetChangesArgs,
    GetItemsArgs,
    SearchMaterialsArgs,
)
from app.agent.tools.context import RunCtx
from app.agent.tools.db_source import DbToolData
from app.agent.tools.read import fetch_latest, get_changes, get_items, search_materials
from app.api import schemas as s
from app.core.auth import UserCtx
from app.core.clock import SystemClock
from app.core.embeddings import FakeEmbeddings
from app.db.seed import seed_user
from app.sync.jobs import SyncRunResult
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


def _factory(conn: Any):  # noqa: ANN202
    @asynccontextmanager
    async def same() -> AsyncIterator[Any]:
        yield conn

    return same


@pytest.fixture
async def seeded(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    await seed_user(conn, uid, FakeEmbeddings(), namespace=f"test-{uuid4().hex[:8]}")
    yield uid
    await delete_auth_user(conn, uid)


@pytest.fixture
async def empty_user(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    yield uid
    await delete_auth_user(conn, uid)


def _ctx(conn: Any, uid: UUID, **kw: Any) -> RunCtx:
    data = DbToolData(uid, _factory(conn), embedder=FakeEmbeddings(), **kw)
    return RunCtx(user_id=uid, timezone="America/New_York", clock=SystemClock(), data=data)


async def test_s21_t02_t03_get_items_on_seed(conn, seeded) -> None:  # noqa: ANN001
    res = await get_items(_ctx(conn, seeded), GetItemsArgs())
    assert res.results, "seed should have upcoming items"
    dues = [r["due_local"] for r in res.results if r["due_local"]]
    assert all(d.endswith(("AM", "PM")) for d in dues)
    assert all(not r["due_in"].endswith("ago") for r in res.results)  # past hidden by default
    exams = await get_items(_ctx(conn, seeded), GetItemsArgs(course="CS 311", type="exam"))
    assert any("Midterm" in r["title"] for r in exams.results)
    assert all(r["course"] == "COMPSCI 311" for r in exams.results)
    assert res.coverage.needs_reconnect == ["echo360"]


async def test_s21_t04_get_changes_on_seed(conn, seeded) -> None:  # noqa: ANN001
    res = await get_changes(_ctx(conn, seeded), GetChangesArgs(since_days=14))
    assert res.results
    assert any(r["field"] == "due_at" for r in res.results)
    assert all(r["summary"] for r in res.results)


async def test_s21_t05_t06_search_full_text_and_current_only(conn, seeded) -> None:  # noqa: ANN001
    ctx = _ctx(conn, seeded)
    res = await search_materials(ctx, SearchMaterialsArgs(query="memoization", course="CS 311"))
    assert res.results and any("emoiz" in r["text"].lower() for r in res.results)
    first = res.results[0]["chunk_id"]
    await conn.execute("update chunks set is_current = false where id = %s", (first,))
    again = await search_materials(ctx, SearchMaterialsArgs(query="memoization", course="CS 311"))
    assert first not in [r["chunk_id"] for r in again.results]


async def test_s21_t09_user_isolation(conn, seeded, empty_user) -> None:  # noqa: ANN001
    mine = await search_materials(_ctx(conn, seeded), SearchMaterialsArgs(query="memoization"))
    ids = [r["chunk_id"] for r in mine.results]
    other = _ctx(conn, empty_user)
    assert (await search_materials(other, SearchMaterialsArgs(query="memoization"))).results == []
    assert (await get_items(other, GetItemsArgs(include_past=True))).results == []
    assert await other.data.chunks_by_id(ids) == []  # S23-T02/T09: no cross-user resolution


async def test_s21_t10_zero_results_writes_miss(conn, seeded) -> None:  # noqa: ANN001
    res = await search_materials(
        _ctx(conn, seeded), SearchMaterialsArgs(query="zyxwvut quantumfoam")
    )
    assert res.results == [] and res.note and "fetch_latest" in res.note
    cur = await conn.execute("select count(*) as n from misses where user_id = %s", (seeded,))
    row = await cur.fetchone()
    assert row and row["n"] == 1


async def test_s21_t11_fetch_latest_enqueues_and_waits(conn, seeded) -> None:  # noqa: ANN001
    calls: list[tuple[str, str]] = []
    run_id = uuid4()

    async def enqueue(_conn, _uid, platform, scope, trigger):  # noqa: ANN001, ANN202
        calls.append((platform, scope.kind))
        assert trigger == "agent"
        return run_id

    async def wait(_conn, _uid, rid, timeout_s):  # noqa: ANN001, ANN202
        return SyncRunResult(
            sync_run_id=rid,
            status="succeeded",
            timed_out=False,
            stats={"new": 2, "changed": 1, "unchanged": 0, "removed": 0},
        )

    ctx = _ctx(conn, seeded, enqueue=enqueue, wait=wait)
    res = await fetch_latest(ctx, FetchLatestArgs(course="CS 311", source="canvas"))
    assert res.results[0] == {
        "status": "completed",
        "added": 2,
        "updated": 1,
        "sync_run_ids": [str(run_id)],
    }
    assert calls == [("canvas", "course")]
    reconnect = await fetch_latest(ctx, FetchLatestArgs(source="echo360"))
    assert reconnect.results[0]["status"] == "needs_reconnect" and len(calls) == 1


async def test_s23_t05_t06_resolution_fields_and_status(conn, seeded) -> None:  # noqa: ANN001
    ctx = _ctx(conn, seeded)
    hits = (await search_materials(ctx, SearchMaterialsArgs(query="memoization"))).results
    ids = [h["chunk_id"] for h in hits[:2]]
    cites = resolve_rows(await ctx.data.chunks_by_id(ids), ids)
    assert [c.chunk_id for c in cites] == ids
    for c in cites:
        assert c.url.startswith("https://") and c.deep_link and c.quote and c.course_code
        assert c.status == "current"
    await conn.execute("update chunks set is_current = false where id = %s", (ids[0],))
    changed = resolve_rows(await ctx.data.chunks_by_id(ids[:1]), ids[:1])
    assert changed[0].status == "changed"


async def test_s22_t09_runtime_persists_to_db(conn, seeded) -> None:  # noqa: ANN001
    store = DbChatStore(_factory(conn))
    probe = await search_materials(_ctx(conn, seeded), SearchMaterialsArgs(query="memoization"))
    cid = probe.results[0]["chunk_id"]
    cards = [{"front": f"Q{i}", "back": "A", "chunk_ids": [cid]} for i in range(5)]
    model = ScriptedModel(
        [
            [function_call("search_materials", {"query": "memoization"}, call_id="c1")],
            [
                function_call(
                    "create_study_set",
                    {"type": "flashcards", "title": "DP", "flashcards": {"cards": cards}},
                    call_id="c2",
                )
            ],
            [assistant_message(f"Done [cite:chunk_{cid}].")],
        ]
    )
    runtime = ChatRuntime(
        store=store,
        data_factory=lambda u: DbToolData(u.user_id, _factory(conn), embedder=FakeEmbeddings()),
        model_factory=lambda _c: (model, "scripted"),
        clock=SystemClock(),
    )
    user = UserCtx(user_id=seeded)
    events = [e async for e in runtime.run(user, s.ChatRequest(message="DP flashcards"))]
    assert events[-1].type == "done", events[-1]
    conv_id = events[0].conversation_id  # type: ignore[union-attr]
    detail = await store.conversation(seeded, conv_id)
    assert detail and [m.role for m in detail.messages] == ["user", "assistant"]
    assert detail.messages[1].citations and detail.messages[1].study_set_ids
    cur = await conn.execute(
        "select status, tool_calls from agent_runs where user_id = %s and conversation_id = %s",
        (seeded, conv_id),
    )
    run = await cur.fetchone()
    assert run and run["status"] == "done"
    assert [t["tool"] for t in run["tool_calls"]] == ["search_materials", "create_study_set"]
    sets = await store.study_sets(seeded)
    assert any(x.id == detail.messages[1].study_set_ids[0] for x in sets)
    assert await store.conversation(uuid4(), conv_id) is None
