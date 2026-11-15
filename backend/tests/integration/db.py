"""Shared helpers for integration tests that need the local Supabase DB with the S01 schema."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from app.core.settings import get_settings


async def open_conn() -> AsyncConnection[Any]:
    """Direct (non-pooled) autocommit connection as `postgres`; skips if no DB / no schema."""
    try:
        conn: AsyncConnection[Any] = await psycopg.AsyncConnection.connect(
            get_settings().database_url,
            connect_timeout=2,
            autocommit=True,
            row_factory=cast(Any, dict_row),
        )
    except psycopg.OperationalError:
        pytest.skip("no local database (make db && make db-reset)")
    cur = await conn.execute("select to_regclass('public.chunks') as t")
    row = await cur.fetchone()
    if not row or row["t"] is None:
        await conn.close()
        pytest.skip("S01 schema not migrated (make db-reset)")
    return conn


async def conn_fixture() -> AsyncIterator[AsyncConnection[Any]]:
    conn = await open_conn()
    try:
        yield conn
    finally:
        await conn.close()


async def create_auth_user(conn: AsyncConnection[Any], email: str | None = None) -> UUID:
    user_id = uuid4()
    await conn.execute(
        "insert into auth.users (id, email, aud, role) values (%s, %s, 'authenticated', "
        "'authenticated')",
        (user_id, email or f"{user_id.hex[:8]}@test.umass.edu"),
    )
    return user_id


async def delete_auth_user(conn: AsyncConnection[Any], user_id: UUID) -> None:
    await conn.execute("delete from auth.users where id = %s", (user_id,))


class AsUser:
    """`async with AsUser(conn, uid):` runs statements as the `authenticated` role with a JWT for
    `uid`, the way PostgREST does for a signed-in student. Rolled back on exit."""

    def __init__(
        self, conn: AsyncConnection[Any], user_id: UUID | None, role: str = "authenticated"
    ):
        self.conn, self.user_id, self.role = conn, user_id, role
        self._tx: Any = None

    async def __aenter__(self) -> AsyncConnection[Any]:
        self._tx = self.conn.transaction(force_rollback=True)
        await self._tx.__aenter__()
        claims = {"sub": str(self.user_id), "role": self.role} if self.user_id else {}
        await self.conn.execute(
            "select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),)
        )
        await self.conn.execute(SQL("set local role {}").format(Identifier(self.role)))
        return self.conn

    async def __aexit__(self, *exc: object) -> None:
        await self._tx.__aexit__(*exc)


ONE_VEC = "[" + ",".join(["1"] + ["0"] * 1535) + "]"


async def insert_minimal_rows(conn: AsyncConnection[Any], user_id: UUID) -> dict[str, Any]:
    """One row in every user table for `user_id`. Returns ids by table."""
    ids: dict[str, Any] = {}

    async def one(sql: str, params: tuple[Any, ...]) -> Any:
        cur = await conn.execute(cast(Any, sql), params)
        row = await cur.fetchone()
        return row["id"] if row and "id" in row else None

    await conn.execute("insert into profiles (user_id) values (%s)", (user_id,))
    ids["connections"] = await one(
        "insert into connections (user_id, platform) values (%s, 'canvas') returning id",
        (user_id,),
    )
    await conn.execute(
        "insert into connection_secrets (connection_id, ciphertext, kind) "
        "values (%s, 'x'::bytea, 'canvas_token')",
        (ids["connections"],),
    )
    cid = ids["courses"] = await one(
        "insert into courses (user_id, name, code) values (%s, 'Algorithms', 'COMPSCI 311') "
        "returning id",
        (user_id,),
    )
    src = "'canvas', %s, 'https://example.instructure.com/x', 'h'"
    ids["course_links"] = await one(
        "insert into course_links (user_id, course_id, platform, platform_id, source_url, "
        f"content_hash) values (%s, %s, {src}) returning id",
        (user_id, cid, f"c-{uuid4().hex[:6]}"),
    )
    iid = ids["items"] = await one(
        "insert into items (user_id, course_id, title) values (%s, %s, 'HW 1') returning id",
        (user_id, cid),
    )
    ids["item_sources"] = await one(
        "insert into item_sources (user_id, item_id, course_id, raw_title, platform, platform_id, "
        f"source_url, content_hash) values (%s, %s, %s, 'HW 1', {src}) returning id",
        (user_id, iid, cid, f"a-{uuid4().hex[:6]}"),
    )
    mid = ids["materials"] = await one(
        "insert into materials (user_id, course_id, kind, title, platform, platform_id, "
        f"source_url, content_hash) values (%s, %s, 'file', 'Lecture 1', {src}) returning id",
        (user_id, cid, f"f-{uuid4().hex[:6]}"),
    )
    pid = ids["posts"] = await one(
        "insert into posts (user_id, course_id, kind, title, posted_at, platform, platform_id, "
        f"source_url, content_hash) values (%s, %s, 'announcement', 'Hi', now(), {src}) "
        "returning id",
        (user_id, cid, f"p-{uuid4().hex[:6]}"),
    )
    ids["chunks"] = await one(
        "insert into chunks (user_id, course_id, material_id, text, token_count, embedding) "
        "values (%s, %s, %s, 'memoization', 1, %s) returning id",
        (user_id, cid, mid, ONE_VEC),
    )
    ids["changes"] = await one(
        "insert into changes (user_id, entity_type, entity_id, course_id, field) "
        "values (%s, 'post', %s, %s, 'body') returning id",
        (user_id, pid, cid),
    )
    conv = ids["conversations"] = await one(
        "insert into conversations (user_id) values (%s) returning id", (user_id,)
    )
    ids["messages"] = await one(
        "insert into messages (user_id, conversation_id, role) values (%s, %s, 'user') "
        "returning id",
        (user_id, conv),
    )
    run = ids["agent_runs"] = await one(
        "insert into agent_runs (user_id, conversation_id, model) values (%s, %s, 'm') "
        "returning id",
        (user_id, conv),
    )
    ids["study_sets"] = await one(
        "insert into study_sets (user_id, type, title) values (%s, 'quiz', 'Q') returning id",
        (user_id,),
    )
    ids["study_blocks"] = await one(
        "insert into study_blocks (user_id, run_id, title, start_at, end_at) "
        "values (%s, %s, 'Study', now(), now() + interval '1 hour') returning id",
        (user_id, run),
    )
    await conn.execute(
        "insert into calendar_feeds (user_id, secret_token) values (%s, %s)",
        (user_id, uuid4().hex),
    )
    ids["sync_runs"] = await one(
        "insert into sync_runs (user_id, platform, trigger) values (%s, 'canvas', 'manual') "
        "returning id",
        (user_id,),
    )
    ids["misses"] = await one(
        "insert into misses (user_id, tool, query) values (%s, 'search_materials', 'q') "
        "returning id",
        (user_id,),
    )
    return ids
