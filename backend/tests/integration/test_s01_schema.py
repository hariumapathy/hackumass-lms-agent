"""S01 database schema tests (docs/specs/S01-database-schema.md).

Need a local DB with migrations applied: `make db && make db-reset`.
"""

from typing import Any

import psycopg
import pytest

from app.db.models import TABLE_MODELS
from app.db.repositories.profiles import USER_TABLES
from tests.integration.db import (
    ONE_VEC,
    AsUser,
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
)

pytestmark = pytest.mark.integration

ALL_TABLES = (*USER_TABLES, "connection_secrets")


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def two_users(conn):  # noqa: ANN001, ANN201
    a = await create_auth_user(conn)
    b = await create_auth_user(conn)
    ids_a = await insert_minimal_rows(conn, a)
    ids_b = await insert_minimal_rows(conn, b)
    yield a, b, ids_a, ids_b
    await delete_auth_user(conn, a)
    await delete_auth_user(conn, b)


async def test_s01_t01_every_table_exists_with_rls(conn) -> None:  # noqa: ANN001
    cur = await conn.execute(
        "select c.relname, c.relrowsecurity from pg_class c join pg_namespace n "
        "on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r'"
    )
    tables = {r["relname"]: r["relrowsecurity"] for r in await cur.fetchall()}
    for t in ALL_TABLES:
        assert t in tables, f"missing table {t}"
        assert tables[t], f"RLS not enabled on {t}"
    assert set(TABLE_MODELS) == set(ALL_TABLES)


async def test_s01_t01b_pydantic_models_match_columns(conn) -> None:  # noqa: ANN001
    for table, model in TABLE_MODELS.items():
        cur = await conn.execute(
            "select column_name from information_schema.columns "
            "where table_schema = 'public' and table_name = %s",
            (table,),
        )
        cols = {r["column_name"] for r in await cur.fetchall()} - {"tsv"}
        assert cols == set(model.model_fields), f"{table}: {cols ^ set(model.model_fields)}"


async def test_s01_t02_user_a_cannot_see_user_b_rows(conn, two_users) -> None:  # noqa: ANN001
    a, b, *_ = two_users
    async with AsUser(conn, a):
        for t in USER_TABLES:
            cur = await conn.execute(f"select user_id from {t}")  # noqa: S608
            owners = {r["user_id"] for r in await cur.fetchall()}
            assert owners == {a}, f"{t} leaked rows: {owners}"
    async with AsUser(conn, None, role="anon"):
        for t in USER_TABLES:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                async with conn.transaction():
                    await conn.execute(f"select 1 from {t}")  # noqa: S608


@pytest.mark.parametrize("table", USER_TABLES)
async def test_s01_t03_authenticated_cannot_write(conn, two_users, table: str) -> None:  # noqa: ANN001
    a, _b, ids_a, _ = two_users
    key = "user_id" if table in {"profiles", "calendar_feeds"} else "id"
    ident = a if key == "user_id" else ids_a[table]
    statements: list[tuple[str, tuple[Any, ...]]] = [
        (f"update {table} set user_id = user_id where {key} = %s", (ident,)),  # noqa: S608
        (f"delete from {table} where {key} = %s", (ident,)),  # noqa: S608
        (f"insert into {table} (user_id) values (%s)", (a,)),  # noqa: S608
    ]
    for sql, params in statements:
        async with AsUser(conn, a):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute(sql, params)


async def test_s01_t04_no_client_role_can_read_secrets(conn, two_users) -> None:  # noqa: ANN001
    a, *_ = two_users
    for uid, role in ((a, "authenticated"), (None, "anon")):
        async with AsUser(conn, uid, role=role):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute("select * from connection_secrets")


async def test_s01_t05_upsert_updates_instead_of_duplicating(conn, two_users) -> None:  # noqa: ANN001
    a, _b, ids_a, _ = two_users
    sql = (
        "insert into posts (user_id, course_id, kind, title, posted_at, platform, platform_id, "
        "source_url, content_hash) values (%s, %s, 'announcement', %s, now(), 'canvas', 'dup-1', "
        "'https://example.instructure.com/d', %s) on conflict (user_id, platform, platform_id) "
        "do update set title = excluded.title, content_hash = excluded.content_hash"
    )
    await conn.execute(sql, (a, ids_a["courses"], "v1", "h1"))
    await conn.execute(sql, (a, ids_a["courses"], "v2", "h2"))
    cur = await conn.execute(
        "select title from posts where user_id = %s and platform_id = 'dup-1'", (a,)
    )
    rows = await cur.fetchall()
    assert [r["title"] for r in rows] == ["v2"]


async def test_s01_t06_chunk_needs_exactly_one_parent(conn, two_users) -> None:  # noqa: ANN001
    a, _b, ids_a, _ = two_users
    sql = (
        "insert into chunks (user_id, course_id, material_id, post_id, text, token_count, "
        "embedding) values (%s, %s, %s, %s, 't', 1, %s)"
    )
    for mat, post in ((ids_a["materials"], ids_a["posts"]), (None, None)):
        with pytest.raises(psycopg.errors.CheckViolation):
            await conn.execute(sql, (a, ids_a["courses"], mat, post, ONE_VEC))
    with pytest.raises(psycopg.errors.DataException):  # wrong embedding dimension
        await conn.execute(sql, (a, ids_a["courses"], ids_a["materials"], None, "[1,0,0]"))


async def test_s01_t07_deleting_user_cascades(conn) -> None:  # noqa: ANN001
    uid = await create_auth_user(conn)
    ids = await insert_minimal_rows(conn, uid)
    await delete_auth_user(conn, uid)
    for t in USER_TABLES:
        cur = await conn.execute(f"select count(*) as n from {t} where user_id = %s", (uid,))  # noqa: S608
        row = await cur.fetchone()
        assert row and row["n"] == 0, t
    cur = await conn.execute(
        "select count(*) as n from connection_secrets where connection_id = %s",
        (ids["connections"],),
    )
    row = await cur.fetchone()
    assert row and row["n"] == 0


async def test_s01_t08_vector_search_uses_hnsw(conn) -> None:  # noqa: ANN001
    async with conn.transaction(force_rollback=True):
        await conn.execute("set local enable_seqscan = off")
        cur = await conn.execute(
            "explain select id from chunks order by embedding <=> %s::extensions.vector limit 5",
            (ONE_VEC,),
        )
        plan = "\n".join(next(iter(r.values())) for r in await cur.fetchall())
    assert "chunks_embedding_hnsw_idx" in plan, plan
