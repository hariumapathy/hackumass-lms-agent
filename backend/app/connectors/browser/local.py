"""S13 `local` provider (MVP): a visible Chromium window on the machine running the API.

On the demo laptop the window appears on screen; the student types NetID + password and approves
Duo in that window. We only look at page URL/HTML (`LoginSpec.is_logged_in`), never form fields.
Needs `uv run playwright install chromium` once on that machine (tests never start a browser).
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.connectors.browser.types import LoginHandle, LoginSpec, LoginState, PageLike, ProviderMode


@dataclass
class _Live:
    spec: LoginSpec
    playwright: Any
    browser: Any
    context: Any
    pages: list[Any] = field(default_factory=list)


class LocalPlaywrightProvider:
    mode: ProviderMode = "local"

    def __init__(self, headless_login: bool = False) -> None:
        self._headless_login = headless_login  # True only for debugging without a display
        self._live: dict[str, _Live] = {}

    async def _launch(self, headless: bool) -> tuple[Any, Any]:
        from playwright.async_api import async_playwright  # lazy: tests never import a browser

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(headless=headless)
        except Exception:
            await pw.stop()
            raise
        return pw, browser

    async def start_login(self, spec: LoginSpec) -> LoginHandle:
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
        return await live.context.storage_state()

    async def close(self, handle: LoginHandle) -> None:
        live = self._live.pop(handle.login_id, None)
        if live is None:
            return
        for closer in (live.context.close, live.browser.close, live.playwright.stop):
            try:
                await closer()
            except Exception:  # already closed by the student
                pass

    async def open_with_state(self, state: dict[str, Any]) -> "LocalBrowserSession":
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
