# pyright: reportOptionalSubscript=false
"""S13 browser sessions: saved login is encrypted and queues the first sync (local DB)."""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from cryptography.fernet import Fernet

from app.connectors.browser.store import save_storage_state
from app.core.clock import FixedClock
from app.core.crypto import decrypt
from app.sync.jobs import SyncJob
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
COOKIE = "s3cr3t-gradescope-cookie-value"
STATE = {
    "cookies": [
        {
            "name": "_gradescope_session",
            "value": COOKIE,
            "domain": "www.gradescope.com",
            "path": "/",
        }
    ],
    "origins": [],
}


@pytest.fixture
async def conn() -> AsyncIterator[Any]:
    async for c in conn_fixture():
        yield c


async def test_s13_t04_storage_state_encrypted_never_plaintext(
    conn: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fernet = Fernet(Fernet.generate_key())
    deferred: list[tuple[SyncJob, int]] = []

    async def defer(job: SyncJob, priority: int) -> None:
        deferred.append((job, priority))

    user_id = await create_auth_user(conn)
    try:
        run_id = await save_storage_state(
            conn,
            user_id,
            "gradescope",
            STATE,
            fernet=fernet,
            clock=FixedClock(datetime(2026, 11, 14, 20, tzinfo=UTC)),
            defer=defer,
        )
        cur = await conn.execute(
            "select c.status, s.kind, s.ciphertext from connections c join connection_secrets s "
            "on s.connection_id = c.id where c.user_id = %s and c.platform = 'gradescope'",
            (user_id,),
        )
        row = await cur.fetchone()
        assert row["status"] == "active" and row["kind"] == "storage_state"
        ciphertext = bytes(row["ciphertext"])
        assert COOKIE.encode() not in ciphertext
        assert json.loads(decrypt(ciphertext, fernet)) == STATE
        # no plaintext anywhere else on the connection row
        cur = await conn.execute(
            "select row_to_json(c)::text as j from connections c where user_id = %s", (user_id,)
        )
        assert COOKIE not in (await cur.fetchone())["j"]
        # first full sync queued with trigger `connect`
        cur = await conn.execute(
            "select trigger, scope, status from sync_runs where id = %s", (run_id,)
        )
        run = await cur.fetchone()
        assert run["trigger"] == "connect" and run["scope"]["kind"] == "full"
        assert len(deferred) == 1 and deferred[0][0].platform == "gradescope"
        assert COOKIE not in caplog.text
    finally:
        await delete_auth_user(conn, user_id)
