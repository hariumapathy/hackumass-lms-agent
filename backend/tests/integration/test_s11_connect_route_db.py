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


async def test_S11_S32_canvas_connect_import_merge_dashboard(conn, monkeypatch) -> None:  # noqa: ANN001
    """Use the real connector/pipeline/merge with scrubbed Canvas responses, then read via HTTP."""
    from datetime import UTC, datetime

    import app.connectors.registry  # noqa: F401
    from app.core.clock import FixedClock
    from app.sync import jobs
    from app.sync.merge import merge_user
    from tests.canvas_fake import mock_canvas

    queued = []
    followups = []

    async def defer_sync(job, priority):  # noqa: ANN001, ANN202
        queued.append(job)

    async def defer(task, kwargs, **options):  # noqa: ANN001, ANN202
        followups.append((task, kwargs, options))

    monkeypatch.setattr(jobs, "_defer_sync", defer_sync)
    monkeypatch.setattr(jobs, "_defer", defer)
    monkeypatch.setenv("DATA_SOURCE", "db")
    monkeypatch.setenv("CANVAS_BASE_URL", BASE)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    uid = await create_auth_user(conn)
    clock = FixedClock(datetime(2026, 11, 14, 20, tzinfo=UTC))
    transport = httpx.ASGITransport(app=create_app(clock=clock))
    h = auth_header(uid)
    try:
        with respx.mock(assert_all_called=False) as router:
            router.route(host="test").pass_through()
            mock_canvas(router)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                assert (await client.get("/courses", headers=h)).json() == []
                linked = await client.post("/connections/canvas", json={"token": TOKEN}, headers=h)
                assert linked.status_code == 200, linked.text
                assert (await client.get("/sync/status", headers=h)).json()["sources"][0]["running"]
                assert (
                    await jobs.execute_sync(conn, queued[0], final_attempt=True, clock=clock)
                    == "succeeded"
                )
                merge_jobs = [options for task, _, options in followups if task is jobs.merge_user]
                assert len(merge_jobs) == 1 and merge_jobs[0]["priority"] == jobs.PRIORITY["manual"]
                await merge_user(conn, uid, clock=clock)
                courses = (await client.get("/courses", headers=h)).json()
                assert {c["code"] for c in courses} == {"COMPSCI 311", "MATH 235"}
                today = (await client.get("/today", headers=h)).json()
                exam = next(i for i in today["upcoming_exams"] if i["title"] == "Midterm 1")
                assert exam["due_at"] == "2026-11-21T00:00:00Z"
                assert exam["sources"][0]["source_url"] == f"{BASE}/courses/12345/assignments/99812"
                detail = (await client.get(f"/courses/{exam['course_id']}", headers=h)).json()
                assert detail["materials"] and detail["recent_posts"]
                status = (await client.get("/sync/status", headers=h)).json()["sources"][0]
                assert not status["running"] and not status["stale"]
    finally:
        await close_pool()
        await delete_auth_user(conn, uid)
