# pyright: reportArgumentType=false, reportIndexIssue=false, reportCallIssue=false, reportOptionalSubscript=false
"""S11 Canvas: connect flow + a real `run_sync` into the local DB, Canvas mocked with respx."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import respx
from cryptography.fernet import Fernet

from app.connectors.base import SyncScope, get_connector
from app.connectors.canvas.connector import CanvasConnector
from app.connectors.canvas.service import InvalidCanvasToken, connect_canvas
from app.core.clock import FixedClock
from app.core.crypto import decrypt
from app.db.repositories import sync as repo
from app.sync.pipeline import run_sync
from tests.canvas_fake import API, BASE, fx, mock_canvas
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)
TOKEN = "fake-canvas-token-123"


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn):  # noqa: ANN001, ANN201
    uid = await create_auth_user(conn)
    yield uid
    await delete_auth_user(conn, uid)


async def _one(conn: Any, sql: str, *params: Any) -> Any:
    cur = await conn.execute(sql, params)
    return await cur.fetchone()


async def test_s11_t12_connect_stores_encrypted_token_and_enqueues_connect_sync(conn, user):  # noqa: ANN001, ANN201
    fernet = Fernet(Fernet.generate_key())
    deferred: list[Any] = []

    async def fake_defer(job: Any, priority: int) -> None:
        deferred.append(job)

    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        res = await connect_canvas(
            conn,
            user,
            f"  {TOKEN}\n",
            clock=FixedClock(NOW),
            base_url=BASE,
            fernet=fernet,
            defer=fake_defer,
        )
        assert [c.request.url.path for c in router.calls] == ["/api/v1/users/self"]

    assert res.status == "active" and res.account_label == "Test Student"
    assert res.expires_at == NOW + timedelta(days=90)
    cx = await repo.get_connection(conn, user, "canvas")
    assert cx and cx.id == res.connection_id and cx.status == "active"
    assert cx.expires_at == NOW + timedelta(days=90) and cx.account_label == "Test Student"
    secret = await _one(
        conn,
        "select ciphertext, kind from connection_secrets where connection_id = %s",
        res.connection_id,
    )
    assert secret["kind"] == "canvas_token"
    assert TOKEN.encode() not in bytes(secret["ciphertext"])
    assert decrypt(secret["ciphertext"], fernet) == TOKEN  # stripped before storing
    run = await repo.get_run(conn, user, res.sync_run_id)
    assert run and run.trigger == "connect" and run.status == "queued"
    assert len(deferred) == 1
    job = deferred[0]
    assert job.trigger == "connect" and job.scope == SyncScope(kind="full")
    assert job.sync_run_id == res.sync_run_id and job.platform == "canvas"


async def test_s11_t09_connect_with_bad_token_is_invalid_token_and_stores_nothing(conn, user):  # noqa: ANN001, ANN201
    async def fake_defer(job: Any, priority: int) -> None:
        raise AssertionError("must not enqueue")

    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/users/self").respond(401, json=fx("unauthorized"))
        with pytest.raises(InvalidCanvasToken) as err:
            await connect_canvas(
                conn, user, "bad", clock=FixedClock(NOW), base_url=BASE, defer=fake_defer
            )
    assert err.value.code == "invalid_token"
    with pytest.raises(InvalidCanvasToken):
        await connect_canvas(conn, user, "   ", clock=FixedClock(NOW), base_url=BASE)
    assert await repo.get_connection(conn, user, "canvas") is None


async def test_s11_registered_in_registry() -> None:
    import app.connectors.registry  # noqa: F401

    assert isinstance(get_connector("canvas"), CanvasConnector)


async def test_s11_run_sync_with_canvas_connector_into_db(conn, user):  # noqa: ANN001, ANN201
    await conn.execute("insert into connections (user_id, platform) values (%s, 'canvas')", (user,))
    connector = CanvasConnector(base_url=BASE)

    async def sync() -> Any:
        run_id = await repo.create_run(conn, user, "canvas", {"kind": "full"}, "connect", NOW)
        with respx.mock(assert_all_called=False) as router:
            mock_canvas(router)
            return await run_sync(
                conn,
                user_id=user,
                run_id=run_id,
                scope=SyncScope(),
                connector=connector,
                secret=TOKEN,
                clock=FixedClock(NOW),
            )

    out = await sync()
    assert out.status == "succeeded", out.error
    # 2 courses + 7 items + 2 posts + 5 materials (syllabus, 2 files, 2 via modules)
    assert out.stats == {"new": 16, "changed": 0, "unchanged": 0, "removed": 0}
    codes = await conn.execute("select code from courses where user_id = %s order by code", (user,))
    assert [r["code"] for r in await codes.fetchall()] == ["COMPSCI 311", "MATH 235"]
    mid = await _one(
        conn,
        "select raw_title, raw_due_at, source_url from item_sources "
        "where user_id = %s and platform_id = '99812'",
        user,
    )
    assert mid["raw_title"] == "Midterm 1"
    assert mid["raw_due_at"] == datetime(2026, 11, 21, tzinfo=UTC)
    assert mid["source_url"] == f"{BASE}/courses/12345/assignments/99812"
    n = await _one(conn, "select count(*) as n from posts where user_id = %s", user)
    assert n["n"] == 2

    again = await sync()
    assert again.stats == {"new": 0, "changed": 0, "unchanged": 16, "removed": 0}
