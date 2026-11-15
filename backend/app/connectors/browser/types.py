"""S13 browser-session types: login spec per platform, provider interface, login handle/state.

`PageLike` is the slice of Playwright's `Page` we use, so tests can pass a fake page.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.db.models import Platform

LoginState = Literal["pending", "succeeded", "failed", "expired"]
ProviderMode = Literal["local", "hosted"]


class PageLike(Protocol):
    @property
    def url(self) -> str: ...

    async def content(self) -> str: ...

    def is_closed(self) -> bool: ...

    async def goto(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class LoginSpec:
    """Per-platform login recipe (defined in each connector, e.g. `gradescope/login.py`).

    `is_logged_in` looks at page state only (URL + HTML); it never reads form fields (S13 rule 3).
    `check_url` is a page that needs a session; `check_session` opens it to validate saved state.
    """

    platform: Platform
    start_url: str
    is_logged_in: Callable[[PageLike], Awaitable[bool]]
    check_url: str
    timeout_s: int = 300


@dataclass(frozen=True)
class LoginHandle:
    login_id: str
    live_view_url: str | None = None


class BrowserProvider(Protocol):
    """`local` = headed Playwright Chromium on this machine (MVP); `hosted` = cloud browser."""

    mode: ProviderMode

    async def start_login(self, spec: LoginSpec) -> LoginHandle: ...

    async def poll(self, handle: LoginHandle) -> LoginState:
        """`succeeded` once `spec.is_logged_in`; `failed` if the window was closed; else pending."""
        ...

    async def storage_state(self, handle: LoginHandle) -> dict[str, Any]: ...

    async def close(self, handle: LoginHandle) -> None: ...

    async def open_with_state(self, state: dict[str, Any]) -> "BrowserSession":
        """Headless context with saved cookies (for syncing / `check_session`)."""
        ...


class BrowserSession(Protocol):
    """A headless browser context opened from a saved storage state."""

    async def new_page(self) -> PageLike: ...

    async def close(self) -> None: ...
