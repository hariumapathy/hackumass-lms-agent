"""Connection and sync endpoints (S02 stubs; real logic in S10, S11, S13)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.connectors.browser.manager import LoginManager, get_login_manager
from app.core.errors import not_found

router = APIRouter(tags=["connections"])
User = Annotated[UserCtx, Depends(current_user)]
Logins = Annotated[LoginManager, Depends(get_login_manager)]


@router.post("/connections/canvas", response_model=s.Connection)
async def connect_canvas(body: s.CanvasConnectRequest, user: User) -> s.Connection:
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
    return Response(status_code=204)


@router.post("/sync", response_model=s.SyncStartResponse)
async def start_sync(body: s.SyncRequest, user: User) -> s.SyncStartResponse:
    return s.SyncStartResponse(sync_run_ids=[uuid4()])


@router.get("/sync/status", response_model=s.SyncStatusResponse)
async def sync_status(user: User) -> s.SyncStatusResponse:
    return s.SyncStatusResponse(sources=mock.sources())
