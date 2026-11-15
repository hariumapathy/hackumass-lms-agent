"""S36-T04: DbChatStore sessions on the local DB: study sets per conversation, rename, delete."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.agent.db_store import DbChatStore
from app.api import mock_data as mock
from app.api import schemas as s
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def two_users(conn):  # noqa: ANN001, ANN201
    a, b = await create_auth_user(conn), await create_auth_user(conn)
    yield a, b
    await delete_auth_user(conn, a)
    await delete_auth_user(conn, b)


def _factory(conn: Any):  # noqa: ANN202
    @asynccontextmanager
    async def same() -> AsyncIterator[Any]:
        yield conn

    return same


async def test_s36_t04_db_sessions(conn, two_users) -> None:  # noqa: ANN001
    me, other = two_users
    store = DbChatStore(_factory(conn))
    now = datetime.now(UTC)
    cid = await store.ensure_conversation(me, None, "DP flashcards", now)
    await store.add_message(
        me, cid, s.Message(id=uuid4(), role="user", text="DP flashcards", created_at=now)
    )
    st = mock.study_set().model_copy(update={"id": uuid4(), "course_id": None})
    await store.save_study_set(me, st, cid)

    convs = await store.conversations(me)
    assert [c.id for c in convs] == [cid]
    assert [x.id for x in convs[0].study_sets] == [st.id]
    assert (await store.study_sets(me))[0].conversation_id == cid
    assert await store.conversations(other) == []

    assert await store.rename_conversation(other, cid, "Hacked") is None
    renamed = await store.rename_conversation(me, cid, "Midterm prep")
    assert renamed is not None and renamed.title == "Midterm prep"

    assert await store.delete_conversation(other, cid) is False
    assert await store.delete_conversation(me, cid) is True
    assert await store.conversation(me, cid) is None
    cur = await conn.execute(
        "select count(*) as n from messages where conversation_id = %s", (cid,)
    )
    assert (await cur.fetchone())["n"] == 0
    kept = await store.study_sets(me)
    assert [x.id for x in kept] == [st.id] and kept[0].conversation_id is None
    assert await store.delete_conversation(me, cid) is False
