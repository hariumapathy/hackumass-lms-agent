"""S11-T12: `POST /connections/canvas` in DB mode stores the token encrypted and queues a
`connect` sync. Canvas is faked with respx (no real account); needs the local DB."""

import httpx
import pytest
import respx
from cryptography.fernet import Fernet

from app.core.settings import get_settings
from app.db.pool import close_pool
from app.main import create_app
from tests.canvas_fake import API, BASE, fx
from tests.helpers import auth_header
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
TOKEN = "1234~fake-canvas-token-for-tests-only"


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


async def test_s11_t12_connect_canvas_route(conn, monkeypatch) -> None:  # noqa: ANN001
    from app.sync import jobs

    deferred: list[dict] = []

    async def fake_defer(job, priority):  # noqa: ANN001, ANN202
        deferred.append({"platform": job.platform, "trigger": job.trigger})

    monkeypatch.setattr(jobs, "_defer_sync", fake_defer)
    monkeypatch.setenv("DATA_SOURCE", "db")
    monkeypatch.setenv("CANVAS_BASE_URL", BASE)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    uid = await create_auth_user(conn)
    h = auth_header(uid)
    transport = httpx.ASGITransport(app=create_app())
    try:
        with respx.mock(assert_all_called=False) as router:
            router.route(host="test").pass_through()
            self_route = router.get(f"{API}/users/self")
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                self_route.respond(401, json={"errors": [{"message": "Invalid access token."}]})
                bad = await client.post("/connections/canvas", json={"token": TOKEN}, headers=h)
                assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_token"
                assert "Canvas" in bad.json()["error"]["message"]

                self_route.respond(json=fx("users_self"))
                ok = await client.post("/connections/canvas", json={"token": TOKEN}, headers=h)
                assert ok.status_code == 200, ok.text
                assert ok.json()["platform"] == "canvas" and ok.json()["status"] == "active"
                assert TOKEN not in ok.text

                status = await client.get("/sync/status", headers=h)
                assert [x["platform"] for x in status.json()["sources"]] == ["canvas"]
                again = await client.post("/sync", json={}, headers=h)
                assert again.status_code == 200
        cur = await conn.execute(
            "select s.ciphertext from connection_secrets s join connections c "
            "on c.id = s.connection_id where c.user_id = %s and c.platform = 'canvas'",
            (uid,),
        )
        row = await cur.fetchone()
        assert row and TOKEN.encode() not in bytes(row["ciphertext"])  # stored encrypted
        assert deferred and deferred[0] == {"platform": "canvas", "trigger": "connect"}
    finally:
        await close_pool()
        await delete_auth_user(conn, uid)
