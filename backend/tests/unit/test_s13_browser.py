"""S13 browser sessions: login state machine, timeout, 409, check_session (fake browser, no
Playwright). docs/specs/S13-browser-sessions.md.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.connectors.browser.manager import LoginManager, get_login_manager
from app.connectors.browser.session import check_session
from app.connectors.browser.types import LoginHandle, LoginSpec, LoginState, PageLike, ProviderMode
from app.connectors.gradescope.login import GRADESCOPE_LOGIN
from app.core.clock import FixedClock
from app.core.errors import AppError
from app.main import create_app
from tests.helpers import OTHER_USER_ID, TEST_USER_ID, auth_header

ACCOUNT_HTML = '<a href="/logout">Log Out</a><div id="account-show"></div>'
LOGIN_HTML = (
    '<form action="/login" method="post"><input name="authenticity_token" value="x">'
    '<input name="session[password]" type="password"></form>'
)
STATE = {
    "cookies": [
        {
            "name": "_gradescope_session",
            "value": "s3cr3t-cookie",
            "domain": "www.gradescope.com",
            "path": "/",
        }
    ],
    "origins": [],
}


class FakePage:
    def __init__(self, url: str = "about:blank", html: str = "", routes: dict | None = None):
        self._url, self.html, self.closed = url, html, False
        self.routes = routes or {}

    @property
    def url(self) -> str:
        return self._url

    async def content(self) -> str:
        return self.html

    def is_closed(self) -> bool:
        return self.closed

    async def goto(self, url: str, **kwargs: Any) -> None:
        self._url, self.html = self.routes.get(url, (url, ""))


class FakeSession:
    def __init__(self, page: FakePage) -> None:
        self.page, self.closed = page, False

    async def new_page(self) -> PageLike:
        return self.page

    async def close(self) -> None:
        self.closed = True


class FakeProvider:
    """Scripted poll results; never starts a browser."""

    mode: ProviderMode = "local"

    def __init__(self, script: list[LoginState] | None = None, page: FakePage | None = None):
        self.script = list(script or [])
        self.started: list[LoginSpec] = []
        self.closed: list[str] = []
        self.polls = 0
        self.page = page

    async def start_login(self, spec: LoginSpec) -> LoginHandle:
        self.started.append(spec)
        return LoginHandle(login_id=f"h{len(self.started)}")

    async def poll(self, handle: LoginHandle) -> LoginState:
        self.polls += 1
        return self.script.pop(0) if self.script else "pending"

    async def storage_state(self, handle: LoginHandle) -> dict[str, Any]:
        return dict(STATE)

    async def close(self, handle: LoginHandle) -> None:
        self.closed.append(handle.login_id)

    async def open_with_state(self, state: dict[str, Any]) -> FakeSession:
        assert self.page is not None
        return FakeSession(self.page)


class Saved:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, dict[str, Any]]] = []

    async def __call__(self, user_id: UUID, platform: str, state: dict[str, Any]) -> None:
        self.calls.append((user_id, platform, state))


async def no_sleep(_: float) -> None:
    await asyncio.sleep(0)


def manager(provider: FakeProvider, saved: Saved, **kw: Any) -> LoginManager:
    return LoginManager(provider, saved, sleep=kw.pop("sleep", no_sleep), poll_interval_s=0, **kw)


# --- S13-T01 --------------------------------------------------------------------------------------
async def test_s13_t01_pending_then_succeeded_saves_state_and_closes() -> None:
    provider, saved = FakeProvider(["pending", "pending", "succeeded"]), Saved()
    m = manager(provider, saved)
    user = uuid4()
    session = await m.start(user, "gradescope")
    assert session.state == "pending"
    assert provider.started[0].start_url == "https://www.gradescope.com/login"
    done = await m.wait(session.login_id)
    assert done.state == "succeeded" and done.error is None
    assert provider.polls == 3
    assert saved.calls == [(user, "gradescope", STATE)]
    assert provider.closed == ["h1"]
    assert m.get(user, session.login_id).state == "succeeded"


async def test_s13_t01_window_closed_is_failed() -> None:
    provider = FakeProvider(["pending", "failed"])
    m = manager(provider, Saved())
    s = await m.start(uuid4(), "gradescope")
    done = await m.wait(s.login_id)
    assert done.state == "failed" and done.error and "closed" in done.error
    assert provider.closed == ["h1"]


async def test_s13_t01_save_failure_is_failed_and_closes() -> None:
    async def broken(user_id: UUID, platform: str, state: dict[str, Any]) -> None:
        raise RuntimeError("db down s3cr3t-cookie")

    provider = FakeProvider(["succeeded"])
    m = LoginManager(provider, broken, sleep=no_sleep, poll_interval_s=0)
    s = await m.start(uuid4(), "gradescope")
    done = await m.wait(s.login_id)
    assert done.state == "failed" and "s3cr3t" not in (done.error or "")
    assert provider.closed == ["h1"]


# --- S13-T02 --------------------------------------------------------------------------------------
async def test_s13_t02_timeout_expires_and_closes_browser() -> None:
    clock = FixedClock(datetime(2026, 11, 14, 20, 0, tzinfo=UTC))

    async def sleep(_: float) -> None:
        clock.advance(timedelta(seconds=100))

    provider, saved = FakeProvider(), Saved()  # stays pending forever (Duo never approved)
    m = manager(provider, saved, clock=clock, sleep=sleep)
    s = await m.start(uuid4(), "gradescope")
    done = await m.wait(s.login_id)
    assert done.state == "expired"
    assert provider.polls == 3  # t=0, 100, 200; at 300 s (timeout_s) → expired
    assert provider.closed == ["h1"] and saved.calls == []


async def test_s13_cancel_closes_browser() -> None:
    provider = FakeProvider()
    m = LoginManager(provider, Saved(), poll_interval_s=60)
    user = uuid4()
    s = await m.start(user, "gradescope")
    await asyncio.sleep(0)
    done = await m.cancel(user, s.login_id)
    assert done.state == "failed" and provider.closed == ["h1"]


async def test_s13_unsupported_platform_and_other_users_login() -> None:
    m = manager(FakeProvider(), Saved())
    with pytest.raises(AppError) as err:
        await m.start(uuid4(), "canvas")
    assert err.value.status == 422
    s = await m.start(uuid4(), "gradescope")
    with pytest.raises(AppError) as err:
        m.get(uuid4(), s.login_id)
    assert err.value.status == 404
    await m.cancel(s.user_id, s.login_id)


# --- S13-T03 (API level, fake provider) -----------------------------------------------------------
@pytest.fixture
def api() -> Any:
    provider = FakeProvider()
    m = LoginManager(provider, Saved(), poll_interval_s=0.01)
    app = create_app()
    app.dependency_overrides[get_login_manager] = lambda: m
    with TestClient(app) as client:
        yield client, m, provider


def test_s13_t03_second_concurrent_login_is_409(api: Any) -> None:
    client, _, provider = api
    r1 = client.post("/connections/gradescope/login", headers=auth_header())
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["mode"] == "local" and body["live_view_url"] is None
    login_id = body["login_id"]
    r2 = client.post("/connections/gradescope/login", headers=auth_header())
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "conflict"
    assert len(provider.started) == 1
    # another student can log in at the same time
    r3 = client.post("/connections/gradescope/login", headers=auth_header(OTHER_USER_ID))
    assert r3.status_code == 200
    status = client.get(f"/connections/gradescope/login/{login_id}", headers=auth_header())
    assert status.status_code == 200 and status.json() == {"state": "pending", "error": None}


def test_s13_t03_status_scoped_to_user_and_platform(api: Any) -> None:
    client, m, _ = api
    login_id = client.post("/connections/gradescope/login", headers=auth_header()).json()[
        "login_id"
    ]
    other = client.get(
        f"/connections/gradescope/login/{login_id}", headers=auth_header(OTHER_USER_ID)
    )
    assert other.status_code == 404
    wrong_platform = client.get(f"/connections/echo360/login/{login_id}", headers=auth_header())
    assert wrong_platform.status_code == 404
    unknown = client.get(f"/connections/gradescope/login/{uuid4()}", headers=auth_header())
    assert unknown.status_code == 404
    assert m.get(TEST_USER_ID, UUID(login_id)).state == "pending"


def test_s13_t03_succeeded_status_via_api(api: Any) -> None:
    client, m, provider = api
    provider.script = ["succeeded"]
    login_id = client.post("/connections/gradescope/login", headers=auth_header()).json()[
        "login_id"
    ]
    for _ in range(200):
        r = client.get(f"/connections/gradescope/login/{login_id}", headers=auth_header())
        if r.json()["state"] != "pending":
            break
    assert r.json() == {"state": "succeeded", "error": None}
    assert m.on_success.calls[0][0] == TEST_USER_ID  # type: ignore[attr-defined]


# --- S13-T05 --------------------------------------------------------------------------------------
async def test_s13_t05_check_session_false_when_redirected_to_login() -> None:
    page = FakePage(
        routes={
            "https://www.gradescope.com/account": ("https://www.gradescope.com/login", LOGIN_HTML)
        }
    )
    provider = FakeProvider(page=page)
    assert await check_session("gradescope", STATE, provider) is False


async def test_s13_t05_check_session_true_when_logged_in() -> None:
    page = FakePage(
        routes={
            "https://www.gradescope.com/account": (
                "https://www.gradescope.com/account",
                ACCOUNT_HTML,
            )
        }
    )
    assert await check_session("gradescope", STATE, FakeProvider(page=page), GRADESCOPE_LOGIN)


async def test_s13_gradescope_is_logged_in_ignores_sso_pages() -> None:
    sso = FakePage("https://webauth.umass.edu/idp/profile/SAML2", '<a href="/logout">x</a>')
    assert await GRADESCOPE_LOGIN.is_logged_in(sso) is False
    assert await GRADESCOPE_LOGIN.is_logged_in(
        FakePage("https://www.gradescope.com/account", ACCOUNT_HTML)
    )


# --- Windows event-loop fix: Playwright runs on its own thread + loop ----------------------------


async def test_s13_browser_thread_runs_coroutines_on_its_own_loop() -> None:
    import asyncio
    import threading

    from app.connectors.browser.local import _BrowserThread

    runner = _BrowserThread(loop_factory=asyncio.new_event_loop)
    caller_loop = asyncio.get_running_loop()

    async def where() -> tuple[str, bool]:
        return threading.current_thread().name, asyncio.get_running_loop() is caller_loop

    name, same_loop = await runner.run(where())
    assert name == "playwright-loop" and same_loop is False
    assert (await runner.run(where()))[0] == "playwright-loop"  # reuses the same thread


async def test_s13_local_provider_uses_thread_when_asked() -> None:
    import threading

    from app.connectors.browser.local import LocalPlaywrightProvider
    from app.connectors.browser.types import LoginHandle

    seen: list[str] = []
    provider = LocalPlaywrightProvider(own_loop=True)
    provider._thread._loop_factory = __import__("asyncio").new_event_loop  # portable for CI

    async def fake_poll(handle: LoginHandle) -> str:
        seen.append(threading.current_thread().name)
        return "pending"

    provider._poll = fake_poll  # type: ignore[method-assign]
    assert await provider.poll(LoginHandle(login_id="x")) == "pending"
    assert seen == ["playwright-loop"]
    inline = LocalPlaywrightProvider(own_loop=False)
    inline._poll = fake_poll  # type: ignore[method-assign]
    await inline.poll(LoginHandle(login_id="y"))
    assert seen[-1] != "playwright-loop"


def test_s13_login_window_prefers_installed_browsers_on_windows(monkeypatch) -> None:  # noqa: ANN001
    from app.connectors.browser import local

    monkeypatch.setattr(local.sys, "platform", "win32")
    assert local._channels(headless=False) == ["msedge", "chrome", None]
    assert local._channels(headless=True)[0] is None
    monkeypatch.setattr(local.sys, "platform", "darwin")
    assert local._channels(headless=False)[0] is None


async def test_s40_t06_delayed_snapshot_preserves_single_pending_login():
    release = asyncio.Event()
    both = asyncio.Event()
    snapshots = 0

    async def snapshot(user_id):
        nonlocal snapshots
        snapshots += 1
        if snapshots == 2:
            both.set()
        await release.wait()
        return 0

    provider = FakeProvider()
    manager = LoginManager(provider, Saved(), snapshot=snapshot)
    first = asyncio.create_task(manager.start(TEST_USER_ID, "gradescope"))
    second = asyncio.create_task(manager.start(TEST_USER_ID, "gradescope"))
    await both.wait()
    release.set()
    results = await asyncio.gather(first, second, return_exceptions=True)
    try:
        assert len(provider.started) == 1
        errors = [r for r in results if isinstance(r, AppError)]
        assert len(errors) == 1 and errors[0].status == 409
    finally:
        for result in results:
            if not isinstance(result, BaseException):
                await manager.cancel(TEST_USER_ID, result.login_id)
