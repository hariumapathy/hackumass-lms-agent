"""Connect flow for `POST /connections/canvas` (S11): validate the pasted token with Canvas,
store it encrypted, and queue the first sync (`trigger="connect"`). The API route only maps
`InvalidCanvasToken` -> 400 `invalid_token` and `PlatformError` -> 502/503."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from psycopg import AsyncConnection
from pydantic import BaseModel, SecretStr

from app.connectors.base import AuthExpired, ConnectorContext, SyncScope
from app.connectors.canvas.connector import CanvasConnector
from app.core.clock import Clock, SystemClock
from app.core.crypto import encrypt
from app.db.repositories import sync as repo
from app.sync import jobs

# Canvas doesn't report token expiry; the guide tells students to pick the longest (90 days).
TOKEN_LIFETIME = timedelta(days=90)


class InvalidCanvasToken(Exception):  # noqa: N818
    """The pasted token is empty or Canvas rejected it (401). Route -> 400 `invalid_token`."""

    code = "invalid_token"


class CanvasConnectResult(BaseModel):
    connection_id: UUID
    sync_run_id: UUID
    status: str = "active"
    account_label: str | None = None
    expires_at: datetime


async def connect_canvas(
    conn: AsyncConnection[Any],
    user_id: UUID,
    token: str,
    *,
    clock: Clock | None = None,
    base_url: str | None = None,
    fernet: Fernet | None = None,
    defer: jobs.Defer | None = None,
) -> CanvasConnectResult:
    """Validate -> encrypt -> upsert connection + secret -> enqueue a full `connect` sync.

    Raises `InvalidCanvasToken` (nothing stored) or `PlatformError` (Canvas down/slow).
    The plaintext token is never logged or returned.
    """
    clock = clock or SystemClock()
    token = token.strip()
    if not token:
        raise InvalidCanvasToken("empty token")
    ctx = ConnectorContext(user_id=user_id, platform="canvas", secret=SecretStr(token), clock=clock)
    try:
        info = await CanvasConnector(base_url=base_url).validate(ctx)
    except AuthExpired as exc:
        raise InvalidCanvasToken("Canvas rejected the token") from exc
    expires_at = clock.now() + TOKEN_LIFETIME
    connection_id = await repo.upsert_connection_secret(
        conn,
        user_id,
        "canvas",
        encrypt(token, fernet),
        "canvas_token",
        expires_at=expires_at,
        account_label=info.account_label,
    )
    run_id = await jobs.enqueue_sync(
        conn, user_id, "canvas", SyncScope(kind="full"), "connect", clock=clock, defer=defer
    )
    return CanvasConnectResult(
        connection_id=connection_id,
        sync_run_id=run_id,
        account_label=info.account_label,
        expires_at=expires_at,
    )
