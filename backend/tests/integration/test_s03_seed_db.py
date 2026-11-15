"""S03 seed data: integration tests against the local DB. docs/specs/S03-seed-data.md.

Each test seeds a fresh throwaway user under its own ID namespace, so it never touches (or
collides with) the demo account loaded by `make db-reset`.
"""

import time
from typing import Any
from uuid import uuid4

import pytest

from app.core.embeddings import FakeEmbeddings
from app.db.seed import SeedExistsError, load_fixtures, seed_user
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    yield uid
    await delete_auth_user(conn, uid)


def _ns() -> str:
    return f"test-{uuid4().hex[:8]}"


async def _counts(conn: Any, uid: Any) -> dict[str, int]:
    out = {}
    for t in (
        "courses",
        "course_links",
        "items",
        "item_sources",
        "materials",
        "posts",
        "chunks",
        "changes",
        "study_sets",
        "study_blocks",
        "conversations",
        "messages",
        "connections",
        "sync_runs",
    ):
        cur = await conn.execute(f"select count(*) as n from {t} where user_id = %s", (uid,))  # noqa: S608
        row = await cur.fetchone()
        out[t] = row["n"]
    return out


async def test_s03_t01_loader_creates_expected_counts(conn, user) -> None:  # noqa: ANN001
    started = time.monotonic()
    result = await seed_user(conn, user, FakeEmbeddings(), namespace=_ns())
    assert time.monotonic() - started < 60
    fx = load_fixtures()
    content = fx["content"].values()
    expected = {
        "courses": len(fx["courses"]),
        "course_links": sum(len(c["platforms"]) for c in fx["courses"]),
        "items": sum(len(c["items"]) for c in content),
        "item_sources": sum(len(i["sources"]) for c in content for i in c["items"]),
        "materials": sum(len(c["materials"]) for c in content),
        "posts": sum(len(c["posts"]) for c in content),
        "chunks": sum(len(c["posts"]) for c in content)
        + sum(len(m.get("pages") or m.get("cues") or []) for c in content for m in c["materials"]),
        "changes": len(fx["changes"]),
        "study_sets": len(fx["study_sets"]),
        "study_blocks": len(fx["study_blocks"]),
        "conversations": len(fx["conversations"]),
        "messages": sum(len(c["messages"]) for c in fx["conversations"]),
        "connections": len(fx["connections"]),
        "sync_runs": len(fx["connections"]),
    }
    assert await _counts(conn, user) == expected
    assert {k: result.counts[k] for k in expected} == expected
    # Today view / tools need non-empty, sensible data:
    cur = await conn.execute(
        "select count(*) as n from items where user_id = %s and due_at between now() and "
        "now() + interval '7 days'",
        (user,),
    )
    row = await cur.fetchone()
    assert row and row["n"] >= 5


async def test_s03_t04_rerun_refuses_then_reset_gives_same_counts(conn, user) -> None:  # noqa: ANN001
    ns = _ns()
    await seed_user(conn, user, FakeEmbeddings(), namespace=ns)
    before = await _counts(conn, user)
    with pytest.raises(SeedExistsError):
        await seed_user(conn, user, FakeEmbeddings(), namespace=ns)
    await seed_user(conn, user, FakeEmbeddings(), namespace=ns, reset=True)
    assert await _counts(conn, user) == before


async def test_s03_t05_every_chunk_has_one_parent_and_a_source_url(conn, user) -> None:  # noqa: ANN001
    await seed_user(conn, user, FakeEmbeddings(), namespace=_ns())
    cur = await conn.execute(
        "select c.id, c.page, c.start_s, m.kind as mkind, "
        "coalesce(m.source_url, p.source_url) as url, c.text "
        "from chunks c left join materials m on m.id = c.material_id "
        "left join posts p on p.id = c.post_id where c.user_id = %s",
        (user,),
    )
    rows = await cur.fetchall()
    assert rows
    for r in rows:
        assert r["url"] and r["url"].startswith("https://example."), r
        assert "umass" not in r["url"]
        assert r["text"].startswith("["), "S12 context header missing"
        if r["mkind"] == "transcript":
            assert r["start_s"] is not None
        elif r["mkind"] in {"file", "syllabus"}:
            assert r["page"] is not None


async def test_s03_citations_in_seeded_messages_resolve(conn, user) -> None:  # noqa: ANN001
    await seed_user(conn, user, FakeEmbeddings(), namespace=_ns())
    cur = await conn.execute(
        "select content from messages where user_id = %s and role = 'assistant'", (user,)
    )
    msg = (await cur.fetchone())["content"]
    ids = [c["chunk_id"] for c in msg["citations"]]
    assert ids and all(f"[cite:chunk_{i}]" in msg["text"] for i in ids)
    assert "{{" not in msg["text"]
    cur = await conn.execute(
        "select payload from study_sets where user_id = %s and type = 'flashcards'", (user,)
    )
    payload = (await cur.fetchone())["payload"]
    for card in payload["cards"]:
        assert card["chunk_ids"] and all(str(i) in payload["citations"] for i in card["chunk_ids"])
    transcript = [c for c in payload["citations"].values() if c["kind"] == "transcript"]
    assert transcript and "?time=" in transcript[0]["deep_link"]
