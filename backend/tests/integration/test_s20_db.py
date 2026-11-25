"""S20 integration tests that need the S01 schema (`profiles` + every user table).

Skipped until Neal's S01 migrations land and a local DB is running (`make db && make db-reset`).
The repository code they exercise (`app/db/repositories/profiles.py`) is already written against
the S01 spec, so these should pass as soon as the schema exists.
"""

from typing import Any
from uuid import uuid4

import psycopg
import pytest

from app.core.settings import get_settings
from app.db import pool
from app.db.models import DEFAULT_TIMEZONE
from app.db.repositories import profiles

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():
    try:  # fail fast if no local DB (the pool would wait out its 5 s timeout)
        probe = await psycopg.AsyncConnection.connect(
            get_settings().database_url, connect_timeout=2
        )
        await probe.close()
    except psycopg.OperationalError:
        pytest.skip("pending S01 / no local database (make db && make db-reset)")
    try:
        async with pool.connection() as c:
            cur = await c.execute("select to_regclass('public.profiles') as t")
            row: Any = await cur.fetchone()
            if not row or row["t"] is None:
                pytest.skip("pending S01: `profiles` table not migrated yet")
            yield c
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, pytest.skip.Exception):
            raise
        pytest.skip(f"pending S01 / no local database: {type(exc).__name__}")
    finally:
        await pool.close_pool()


async def _create_auth_user(conn, email: str):  # noqa: ANN001, ANN202
    user_id = uuid4()
    email = f"{user_id.hex[:8]}-{email}"  # unique: tests re-run against the same local DB
    await conn.execute(
        "insert into auth.users (id, email, aud, role) values (%s, %s, 'authenticated', "
        "'authenticated')",
        (user_id, email),
    )
    return user_id


async def test_s20_t05_first_request_creates_profile_with_defaults(conn) -> None:  # noqa: ANN001
    user_id = await _create_auth_user(conn, "first@umass.edu")
    assert await profiles.get_profile(conn, user_id) is None
    created = await profiles.ensure_profile(conn, user_id, "first@umass.edu")
    assert created.user_id == user_id and created.timezone == DEFAULT_TIMEZONE
    again = await profiles.ensure_profile(conn, user_id, "first@umass.edu")
    assert again.created_at == created.created_at


async def test_s20_t07_delete_my_data_removes_only_that_users_rows(conn) -> None:  # noqa: ANN001
    a = await _create_auth_user(conn, "a@umass.edu")
    b = await _create_auth_user(conn, "b@umass.edu")
    for uid in (a, b):
        await profiles.ensure_profile(conn, uid, None)
    await profiles.delete_user_data(conn, a)
    assert await profiles.get_profile(conn, a) is None
    assert await profiles.get_profile(conn, b) is not None
    for table in profiles.USER_TABLES:
        cur = await conn.execute(f"select count(*) as n from {table} where user_id = %s", (a,))
        row = await cur.fetchone()
        assert row and row["n"] == 0, table
