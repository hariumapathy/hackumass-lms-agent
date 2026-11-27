"""S13: save a finished login. Encrypt the Playwright storage state immediately (S10 crypto), store
it as `connection_secrets(kind="storage_state")`, mark the connection active, and queue the first
full sync (trigger `connect`). The plaintext state is never logged or stored unencrypted.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from psycopg import AsyncConnection

from app.connectors.base import SyncScope
from app.core.clock import Clock
from app.core.crypto import encrypt, get_fernet
from app.db.repositories import sync as repo

STORAGE_STATE_KIND = "storage_state"


async def save_storage_state(
    conn: AsyncConnection[Any],
    user_id: UUID,
    platform: str,
    state: dict[str, Any],
    *,
    fernet: Fernet | None = None,
    clock: Clock | None = None,
    defer: Any = None,
) -> UUID:
    """Returns the `sync_run_id` of the queued initial sync."""
    from app.sync.jobs import enqueue_sync

    ciphertext = encrypt(json.dumps(state), fernet or get_fernet())
    await repo.upsert_connection_secret(conn, user_id, platform, ciphertext, STORAGE_STATE_KIND)
    return await enqueue_sync(
        conn, user_id, platform, SyncScope(kind="full"), "connect", clock=clock, defer=defer
    )


async def save_login(user_id: UUID, platform: str, state: dict[str, Any]) -> None:
    """`LoginManager.on_success` for the API process (pooled DB connection, real queue)."""
    from app.db.pool import connection
    from app.sync.jobs import app as queue_app

    await queue_app.open_async()  # idempotent; the API process may not have opened it yet
    async with connection() as conn:
        await save_storage_state(conn, user_id, platform, state)


async def login_generation(user_id: UUID) -> int:
    from app.db.deletion import generation
    from app.db.pool import connection

    async with connection() as conn:
        return await generation(conn, user_id)


@asynccontextmanager
async def login_completion_guard(user_id: UUID, expected: int) -> AsyncIterator[None]:
    from app.db.deletion import pending_error, user_session

    async with user_session(user_id) as current:
        if current != expected:
            raise pending_error()
        yield
