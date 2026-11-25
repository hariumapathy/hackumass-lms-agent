"""S41 synthetic source-presence fixtures; no platform or model calls."""

from contextlib import asynccontextmanager

import pytest

from app.agent.citations import resolve_rows
from app.agent.tools.args import GetCourseOverviewArgs, GetMaterialArgs, SearchMaterialsArgs
from app.agent.tools.context import RunCtx
from app.agent.tools.data import ChunkRow
from app.agent.tools.db_source import DbToolData
from app.agent.tools.read import get_course_overview, get_material, search_materials
from app.core.clock import SystemClock
from app.db.repositories import agent as repo
from tests.integration.db import (
    ONE_VEC,
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def sources(conn):
    users = [await create_auth_user(conn) for _ in range(3)]
    rows = [await insert_minimal_rows(conn, uid) for uid in users]
    try:
        for uid, row in zip(users, rows, strict=True):
            await conn.execute(
                "insert into chunks(user_id,course_id,post_id,text,token_count,embedding) "
                "values (%s,%s,%s,'memoization syllabus grading exam policy',1,%s)",
                (uid, row["courses"], row["posts"], ONE_VEC),
            )
        # Same owner, a second removed source pair (not merely a different tenant).
        uid, removed_owner, foreign = users
        active, removed, other = rows
        for table in ("materials", "posts", "chunks"):
            await conn.execute(
                f"update {table} set user_id=%s where user_id=%s", (uid, removed_owner)
            )
        # Their course ownership must follow too for the repository's scoped joins.
        await conn.execute("update courses set user_id=%s where id=%s", (uid, removed["courses"]))
        await conn.execute(
            "update materials set status='removed' where id=%s", (removed["materials"],)
        )
        await conn.execute("update posts set status='removed' where id=%s", (removed["posts"],))
        await conn.execute(
            "insert into chunks(user_id,course_id,material_id,text,token_count,embedding,"
            "is_current) "
            "values (%s,%s,%s,'memoization old chunk',1,%s,false)",
            (uid, active["courses"], active["materials"], ONE_VEC),
        )
        yield uid, foreign, active, removed, other
    finally:
        for uid in users:
            await delete_auth_user(conn, uid)


def context(conn, uid):
    @asynccontextmanager
    async def same():
        yield conn

    return RunCtx(
        user_id=uid, timezone="America/New_York", clock=SystemClock(), data=DbToolData(uid, same)
    )


@pytest.mark.parametrize("branch", ["lexical", "vector", "hybrid"])
async def test_s41_t01_current_search_excludes_removed_foreign_old(conn, sources, branch):
    uid, _, active, _, _ = sources
    rows = await repo.search_chunks(
        conn,
        uid,
        "unmatched" if branch == "vector" else "memoization",
        None if branch == "lexical" else ONE_VEC,
        None,
        "any",
        None,
        8,
    )
    assert len(rows) == 2
    assert {r["course_id"] for r in rows} == {active["courses"]}
    assert all(r["status"] == "current" for r in rows)


async def test_s41_t02_removed_and_foreign_material_cannot_be_read(conn, sources):
    uid, _, active, removed, other = sources
    assert await repo.material_chunks(conn, uid, removed["materials"]) == []
    assert await repo.material_chunks(conn, uid, other["materials"]) == []
    assert len(await repo.material_chunks(conn, uid, active["materials"])) == 1


async def test_s41_t03_historical_citations_still_resolve_status(conn, sources):
    uid, foreign, active, removed, _ = sources
    historical = [active["chunks"], removed["chunks"]]
    await conn.execute("update chunks set is_current=false where id=%s", (active["chunks"],))
    cites = resolve_rows(
        [ChunkRow.model_validate(r) for r in await repo.chunks_by_id(conn, uid, historical)],
        historical,
    )
    assert {c.chunk_id: c.status for c in cites} == {
        active["chunks"]: "changed",
        removed["chunks"]: "removed",
    }
    assert await repo.chunks_by_id(conn, foreign, historical) == []


async def test_s41_t04_search_read_and_overview_retain_source_status(conn, sources):
    uid, _, active, _, _ = sources
    await conn.execute(
        "update materials set status='changed',kind='syllabus' where id=%s", (active["materials"],)
    )
    await conn.execute(
        "update chunks set text='memoization syllabus grading exam policy' where id=%s",
        (active["chunks"],),
    )
    ctx = context(conn, uid)
    search = await search_materials(ctx, SearchMaterialsArgs(query="memoization", kind="syllabus"))
    material = await get_material(ctx, GetMaterialArgs(material_id=str(active["materials"])))
    overview = await get_course_overview(ctx, GetCourseOverviewArgs(course=str(active["courses"])))
    for result in (search.results, material.results, overview.results[0]["syllabus_chunks"]):
        assert result and result[0]["status"] == "changed"
        assert "memoization syllabus" in result[0]["text"]


@pytest.mark.parametrize("branch", ["lexical", "vector", "hybrid"])
async def test_s41_t05_removed_hits_cannot_fill_candidate_window(conn, sources, branch):
    uid, _, active, removed, _ = sources
    for _ in range(repo.CANDIDATES + 1):
        await conn.execute(
            "insert into chunks(user_id,course_id,material_id,text,token_count,embedding) "
            "values (%s,%s,%s,'memoization memoization memoization',3,%s)",
            (uid, removed["courses"], removed["materials"], ONE_VEC),
        )
    # Every removed hit is nearer than the active slide, but the active slide is above floor.
    farther = "[" + ",".join(["0.8", "0.6"] + ["0"] * 1534) + "]"
    await conn.execute("update chunks set embedding=%s where id=%s", (farther, active["chunks"]))
    rows = await repo.search_chunks(
        conn,
        uid,
        "unmatched" if branch == "vector" else "memoization",
        None if branch == "lexical" else ONE_VEC,
        None,
        "slides",
        "canvas",
        8,
    )
    assert [r["chunk_id"] for r in rows] == [active["chunks"]]
    assert (
        await repo.search_chunks(
            conn, uid, "memoization", ONE_VEC, removed["courses"], "any", None, 8
        )
        == []
    )
    assert await repo.search_chunks(conn, uid, "memoization", None, None, "any", "piazza", 8) == []


async def test_s41_t01_foreign_parent_cannot_enter_owned_chunk_search(conn, sources):
    uid, _, active, _, other = sources
    await conn.execute(
        "insert into chunks(user_id,course_id,post_id,text,token_count,embedding) "
        "values (%s,%s,%s,'foreignparentneedle',1,%s)",
        (uid, active["courses"], other["posts"], ONE_VEC),
    )
    assert (
        await repo.search_chunks(conn, uid, "foreignparentneedle", None, None, "any", None, 8) == []
    )


async def test_s41_t04_changed_post_status_retained_in_untrusted_result(conn, sources):
    uid, _, active, _, _ = sources
    await conn.execute("update posts set status='changed' where id=%s", (active["posts"],))
    result = await search_materials(
        context(conn, uid),
        SearchMaterialsArgs(query="memoization", kind="post", course=str(active["courses"])),
    )
    assert len(result.results) == 1
    assert result.results[0]["status"] == "changed"
    assert "<untrusted source=" in result.results[0]["text"]
