"""S13 live-login manager: one watched browser login per (user, platform), status by `login_id`.

State lives in memory in the API process (S13 rule 7, single instance for MVP). A background task
polls the provider until the platform shows a logged-in page, then hands the storage state to
`on_success` (encrypt + save + enqueue the first sync), drops it, and closes the browser.
"""

import asyncio
import importlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.connectors.browser.types import (
    BrowserProvider,
    LoginHandle,
    LoginSpec,
    LoginState,
    ProviderMode,
)
from app.core.clock import Clock, SystemClock
from app.core.errors import AppError, not_found

log = logging.getLogger("app.browser")

OnSuccess = Callable[[UUID, str, dict[str, Any]], Awaitable[None]]
Sleep = Callable[[float], Awaitable[None]]

# Platforms that connect through the live login; value = "module:attribute" of its LoginSpec.
_LOGIN_SPECS = {
    "gradescope": "app.connectors.gradescope.login:GRADESCOPE_LOGIN",
    "piazza": "app.connectors.piazza.login:PIAZZA_LOGIN",
}

WINDOW_CLOSED = "The login window was closed before you finished. Try again."
CANCELLED = "Login cancelled."
SAVE_FAILED = "We couldn't finish connecting. Try again."


def login_spec_for(platform: str) -> LoginSpec:
    target = _LOGIN_SPECS.get(platform)
    if target is None:
        raise AppError(
            "validation_error", f"Connecting {platform} with a login isn't available yet.", 422
        )
    module, attr = target.split(":")
    return getattr(importlib.import_module(module), attr)


@dataclass
class LoginSession:
    login_id: UUID
    user_id: UUID
    platform: str
    started_at: datetime
    state: LoginState = "pending"
    error: str | None = None
    live_view_url: str | None = None
    handle: LoginHandle | None = None
    task: "asyncio.Task[None] | None" = field(default=None, repr=False)


class LoginManager:
    def __init__(
        self,
        provider: BrowserProvider,
        on_success: OnSuccess,
        *,
        clock: Clock | None = None,
        poll_interval_s: float = 1.0,
        sleep: Sleep = asyncio.sleep,
        specs: Callable[[str], LoginSpec] = login_spec_for,
    ) -> None:
        self.provider = provider
        self.on_success = on_success
        self.clock = clock or SystemClock()
        self.poll_interval_s = poll_interval_s
        self.sleep = sleep
        self.specs = specs
        self._sessions: dict[UUID, LoginSession] = {}

    @property
    def mode(self) -> ProviderMode:
        return self.provider.mode

    def _pending(self, user_id: UUID, platform: str) -> LoginSession | None:
        for s in self._sessions.values():
            if s.user_id == user_id and s.platform == platform and s.state == "pending":
                return s
        return None

    async def start(self, user_id: UUID, platform: str) -> LoginSession:
        """Open the login browser. 409 `conflict` if one is already pending (S13 rule 1)."""
        spec = self.specs(platform)
        if self._pending(user_id, platform) is not None:
            raise AppError("conflict", "A login for this site is already in progress.", 409)
        session = LoginSession(
            login_id=uuid4(), user_id=user_id, platform=platform, started_at=self.clock.now()
        )
        self._sessions[session.login_id] = session  # reserve before awaiting (no double start)
        try:
            session.handle = await self.provider.start_login(spec)
        except Exception as exc:
            session.state, session.error = "failed", "We couldn't open the login window."
            log.warning("login browser failed to start for %s: %s", platform, type(exc).__name__)
            raise AppError(
                "internal", "We couldn't open the login window. Try again.", 503, retryable=True
            ) from exc
        session.live_view_url = session.handle.live_view_url
        session.task = asyncio.create_task(self._watch(session, spec))
        return session

    def get(self, user_id: UUID, login_id: UUID) -> LoginSession:
        session = self._sessions.get(login_id)
        if session is None or session.user_id != user_id:
            raise not_found("Login")
        return session

    async def cancel(self, user_id: UUID, login_id: UUID) -> LoginSession:
        session = self.get(user_id, login_id)
        if session.task and not session.task.done():
            session.task.cancel()
            try:
                await session.task
            except asyncio.CancelledError:
                pass
        return session

    async def wait(self, login_id: UUID) -> LoginSession:
        """Test helper: wait for the watch task to finish."""
        session = self._sessions[login_id]
        if session.task:
            await session.task
        return session

    async def _watch(self, session: LoginSession, spec: LoginSpec) -> None:
        assert session.handle is not None
        handle = session.handle
        try:
            while True:
                if (self.clock.now() - session.started_at).total_seconds() >= spec.timeout_s:
                    session.state = "expired"  # S13 rule 2
                    return
                polled = await self.provider.poll(handle)
                if polled == "succeeded":
                    state = await self.provider.storage_state(handle)
                    try:
                        await self.on_success(session.user_id, session.platform, state)
                    finally:
                        del state  # S13 rule 4: drop the plaintext copy right after saving
                    session.state = "succeeded"
                    log.info("live login succeeded for %s", session.platform)
                    return
                if polled == "failed":
                    session.state, session.error = "failed", WINDOW_CLOSED
                    return
                await self.sleep(self.poll_interval_s)
        except asyncio.CancelledError:
            session.state, session.error = "failed", CANCELLED
            raise
        except Exception as exc:  # never log the exception text (could include cookies)
            log.error("live login for %s failed: %s", session.platform, type(exc).__name__)
            session.state, session.error = "failed", SAVE_FAILED
        finally:
            try:
                await self.provider.close(handle)
            except Exception:
                log.warning("closing the login browser failed")


# ---------------------------------------------------------------------------------------------
# Process-wide manager (API process). Tests build their own LoginManager with a fake provider.
# ---------------------------------------------------------------------------------------------
_manager: LoginManager | None = None


def get_login_manager() -> LoginManager:
    global _manager
    if _manager is None:
        from app.connectors.browser.local import LocalPlaywrightProvider
        from app.connectors.browser.store import save_login
        from app.core.settings import get_settings

        if get_settings().browser_provider != "local":
            raise AppError(
                "validation_error", "Live account login is unavailable on this server.", 503
            )
        _manager = LoginManager(LocalPlaywrightProvider(), save_login)
    return _manager


def set_login_manager(manager: LoginManager | None) -> None:
    global _manager
    _manager = manager
