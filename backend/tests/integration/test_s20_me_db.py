"""S20 account routes in DB mode (DATA_SOURCE=db) against the local database.

Uses httpx's ASGI transport on the test's own (selector) event loop: Starlette's TestClient runs
the app on a separate loop, which psycopg async can't use on Windows.
"""

import httpx
import pytest

from app.core.settings import get_settings
from app.db.pool import close_pool
from app.main import create_app
from tests.helpers import auth_header
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


async def test_s20_me_routes_use_profiles_table(conn, monkeypatch) -> None:  # noqa: ANN001
    uid = await create_auth_user(conn)
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    transport = httpx.ASGITransport(app=create_app())
    h = auth_header(uid, email="new.student@umass.edu")
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            me = await client.get("/me", headers=h)  # S20-T05 over HTTP: first call creates it
            assert me.status_code == 200, me.text
            body = me.json()
            assert body["user_id"] == str(uid) and body["timezone"] == "America/New_York"
            assert body["display_name"] == "new.student"
            assert {c["platform"] for c in body["connections"]} == set()
            patched = await client.patch("/me", json={"timezone": "America/Chicago"}, headers=h)
            assert patched.status_code == 200 and patched.json()["timezone"] == "America/Chicago"
            cur = await conn.execute("select timezone from profiles where user_id = %s", (uid,))
            row = await cur.fetchone()
            assert row and row["timezone"] == "America/Chicago"
            assert (await client.delete("/me/data", headers=h)).status_code == 204  # S20-T07
            cur = await conn.execute(
                "select count(*) as n from profiles where user_id = %s", (uid,)
            )
            row = await cur.fetchone()
            assert row and row["n"] == 0
    finally:
        await close_pool()
        await delete_auth_user(conn, uid)
