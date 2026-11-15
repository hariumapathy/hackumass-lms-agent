"""S13 `local` provider (MVP): a visible Chromium window on the machine running the API.

On the demo laptop the window appears on screen; the student types NetID + password and approves
Duo in that window. We only look at page URL/HTML (`LoginSpec.is_logged_in`), never form fields.
Needs `uv run playwright install chromium` once on that machine (`make setup` does it; tests never
start a browser).

Windows: Playwright starts the browser as a subprocess, which needs a Proactor event loop, while
psycopg async (the API) needs a selector loop. So on Windows every Playwright call runs on one
dedicated background thread with its own Proactor loop (`_BrowserThread`); elsewhere it runs
inline. All Playwright objects live on that one thread.
"""

import asyncio
import sys
import threading
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

from app.connectors.browser.types import LoginHandle, LoginSpec, LoginState, PageLike, ProviderMode

T = TypeVar("T")


class _BrowserThread:
    """Runs coroutines on one long-lived background thread with its own event loop."""

    def __init__(self, loop_factory: Any = None) -> None:
        self._loop_factory = loop_factory or (
            asyncio.ProactorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self.thread: threading.Thread | None = None

    def _ensure(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = self._loop_factory()
                self.thread = threading.Thread(
                    target=loop.run_forever, name="playwright-loop", daemon=True
                )
                self.thread.start()
                self._loop = loop
            current = self._loop
        assert current is not None
        return current

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        future = asyncio.run_coroutine_threadsafe(coro, self._ensure())
        return await asyncio.wrap_future(future)


def _channels(headless: bool) -> list[str | None]:
    """Browsers to try, in order (None = Playwright's bundled Chromium). On Windows the visible
    login window uses the installed Edge/Chrome first: the freshly downloaded bundled chrome.exe can
    be blocked from starting ("spawn UNKNOWN", e.g. by Smart App Control)."""
    if sys.platform == "win32" and not headless:
        return ["msedge", "chrome", None]
    return [None, "chrome", "msedge"]


def _needs_own_loop() -> bool:
    """True on Windows unless the caller's loop can already start subprocesses."""
    if sys.platform != "win32":
        return False
    return not isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop)


@dataclass
class _Live:
    spec: LoginSpec
    playwright: Any
    browser: Any
    context: Any
    pages: list[Any] = field(default_factory=list)


class LocalPlaywrightProvider:
    mode: ProviderMode = "local"

    def __init__(self, headless_login: bool = False, own_loop: bool | None = None) -> None:
        self._headless_login = headless_login  # True only for debugging without a display
        self._live: dict[str, _Live] = {}
        self._own_loop = own_loop  # None: decide per platform (Windows -> own thread)
        self._thread = _BrowserThread()

    async def _call(self, coro: Coroutine[Any, Any, T]) -> T:
        use_thread = _needs_own_loop() if self._own_loop is None else self._own_loop
        return await (self._thread.run(coro) if use_thread else coro)

    async def _launch(self, headless: bool) -> tuple[Any, Any]:
        from playwright.async_api import async_playwright  # lazy: tests never import a browser

        pw = await async_playwright().start()
        last: Exception | None = None
        for channel in _channels(headless):
            try:
                browser = await pw.chromium.launch(headless=headless, channel=channel)
                return pw, browser
            except Exception as exc:  # try the next browser
                last = exc
        await pw.stop()
        assert last is not None
        raise last

    async def start_login(self, spec: LoginSpec) -> LoginHandle:
        return await self._call(self._start_login(spec))

    async def _start_login(self, spec: LoginSpec) -> LoginHandle:
        pw, browser = await self._launch(headless=self._headless_login)
        context = await browser.new_context()
        page = await context.new_page()
        live = _Live(spec=spec, playwright=pw, browser=browser, context=context, pages=[page])
        context.on("page", lambda p: live.pages.append(p))  # SSO may open a new tab
        handle = LoginHandle(login_id=uuid.uuid4().hex)
        self._live[handle.login_id] = live
        await page.goto(spec.start_url)
        return handle

    async def poll(self, handle: LoginHandle) -> LoginState:
        return await self._call(self._poll(handle))

    async def _poll(self, handle: LoginHandle) -> LoginState:
        live = self._live.get(handle.login_id)
        if live is None or not live.browser.is_connected():
            return "failed"
        open_pages = [p for p in live.pages if not p.is_closed()]
        if not open_pages:
            return "failed"
        for page in open_pages:
            try:
                if await live.spec.is_logged_in(page):
                    return "succeeded"
            except Exception:  # page navigating mid-check; try again next poll
                continue
        return "pending"

    async def storage_state(self, handle: LoginHandle) -> dict[str, Any]:
        live = self._live[handle.login_id]
        return await self._call(live.context.storage_state())

    async def close(self, handle: LoginHandle) -> None:
        await self._call(self._close(handle))

    async def _close(self, handle: LoginHandle) -> None:
        live = self._live.pop(handle.login_id, None)
        if live is None:
            return
        for closer in (live.context.close, live.browser.close, live.playwright.stop):
            try:
                await closer()
            except Exception:  # already closed by the student
                pass

    async def open_with_state(self, state: dict[str, Any]) -> "LocalBrowserSession":
        """Headless browser with saved cookies. On Windows the returned session lives on the
        browser thread: drive it only through this provider (no caller does yet)."""
        return await self._call(self._open_with_state(state))

    async def _open_with_state(self, state: dict[str, Any]) -> "LocalBrowserSession":
        pw, browser = await self._launch(headless=True)
        context = await browser.new_context(storage_state=state)  # type: ignore[arg-type]
        return LocalBrowserSession(pw, browser, context)


class LocalBrowserSession:
    def __init__(self, playwright: Any, browser: Any, context: Any) -> None:
        self._pw, self._browser, self._context = playwright, browser, context

    async def new_page(self) -> PageLike:
        return await self._context.new_page()

    async def close(self) -> None:
        for closer in (self._context.close, self._browser.close, self._pw.stop):
            try:
                await closer()
            except Exception:
                pass
