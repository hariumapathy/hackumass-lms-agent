"""Connection and sync endpoints. DB mode (DATA_SOURCE=db): Canvas connect (S11), manual sync
and sync status (S10) are real; mock mode keeps the S02 stubs. Logins: S13."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.connectors.browser.manager import LoginManager, get_login_manager
from app.core.errors import AppError, not_found
from app.core.settings import get_settings
from app.db.pool import connection
from app.db.repositories import profiles
from app.db.repositories import sync as sync_repo

router = APIRouter(tags=["connections"])
User = Annotated[UserCtx, Depends(current_user)]
Logins = Annotated[LoginManager, Depends(get_login_manager)]


def _db_mode() -> bool:
    return get_settings().data_source == "db"


@router.post("/connections/canvas", response_model=s.Connection)
async def connect_canvas(body: s.CanvasConnectRequest, user: User) -> s.Connection:
    """S11: validate the token with Canvas, store it encrypted, queue the first sync.
    The token is never logged or returned."""
    if _db_mode():
        from app.connectors.base import PlatformError
        from app.connectors.canvas.service import InvalidCanvasToken
        from app.connectors.canvas.service import connect_canvas as connect

        try:
            async with connection() as conn:
                await profiles.ensure_profile(conn, user.user_id, user.email)
                result = await connect(conn, user.user_id, body.token)
        except InvalidCanvasToken:
            raise AppError(
                "invalid_token",
                "Canvas didn't accept that token. Copy it again from Canvas → Account → "
                "Settings → New Access Token.",
                status=400,
            ) from None
        except PlatformError:
            raise AppError(
                "platform_unavailable",
                "Canvas isn't answering right now. Try again in a minute.",
                status=503,
                retryable=True,
            ) from None
        return s.Connection(
            platform="canvas",
            status="active",
            expires_at=body.expires_at or result.expires_at,
            last_sync_at=None,
            account_label=result.account_label,
        )
    now = datetime.now(UTC)
    return s.Connection(
        platform="canvas",
        status="active",
        expires_at=body.expires_at or now + timedelta(days=90),
        last_sync_at=None,
        account_label="Demo Student",
    )


@router.post("/connections/{platform}/login", response_model=s.LoginStartResponse)
async def start_login(platform: s.Platform, user: User, logins: Logins) -> s.LoginStartResponse:
    session = await logins.start(user.user_id, platform)  # S13; 409 if one is already pending
    return s.LoginStartResponse(
        login_id=session.login_id, mode=logins.mode, live_view_url=session.live_view_url
    )


@router.get("/connections/{platform}/login/{login_id}", response_model=s.LoginStatusResponse)
async def login_status(
    platform: s.Platform, login_id: UUID, user: User, logins: Logins
) -> s.LoginStatusResponse:
    session = logins.get(user.user_id, login_id)
    if session.platform != platform:
        raise not_found("Login")
    return s.LoginStatusResponse(state=session.state, error=session.error)


@router.delete("/connections/{platform}", status_code=204)
async def disconnect(platform: s.Platform, user: User) -> Response:
    """S13 rule 6: delete the connection + its secret and cancel queued syncs. Synced course
    data stays (Delete my data removes it). Idempotent: 204 even if not connected."""
    if _db_mode():
        from app.sync.disconnect import disconnect_platform

        async with connection() as conn:
            await disconnect_platform(conn, user.user_id, platform)
    return Response(status_code=204)


@router.post("/sync", response_model=s.SyncStartResponse)
async def start_sync(body: s.SyncRequest, user: User) -> s.SyncStartResponse:
    """Manual "Refresh" (S10, trigger=manual): every usable connection, or one platform."""
    if not _db_mode():
        return s.SyncStartResponse(sync_run_ids=[uuid4()])
    from app.connectors.base import SyncScope
    from app.sync.jobs import enqueue_sync

    run_ids: list[UUID] = []
    async with connection() as conn:
        for c in await sync_repo.list_connections(conn, user.user_id):
            if c.status != "active" or (body.platform and c.platform != body.platform):
                continue
            run_ids.append(
                await enqueue_sync(conn, user.user_id, c.platform, SyncScope(), "manual")
            )
    return s.SyncStartResponse(sync_run_ids=run_ids)


@router.get("/sync/status", response_model=s.SyncStatusResponse)
async def sync_status(user: User) -> s.SyncStatusResponse:
    if not _db_mode():
        return s.SyncStatusResponse(sources=mock.sources())
    from app.agent.tools.coverage import SCHEDULE_INTERVAL

    now = datetime.now(UTC)
    async with connection() as conn:
        rows = await sync_repo.list_connections(conn, user.user_id)
        running = await sync_repo.running_platforms(conn, user.user_id)
    return s.SyncStatusResponse(
        sources=[
            s.SourceStatus(
                platform=c.platform,
                connection_status=c.status,
                last_sync_at=c.last_sync_at,
                running=c.platform in running,
                stale=c.last_sync_at is None
                or now - c.last_sync_at > 2 * SCHEDULE_INTERVAL[c.platform],
            )
            for c in rows
            if c.status != "disconnected"
        ]
    )
