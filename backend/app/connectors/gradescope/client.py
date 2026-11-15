"""S14: a `gradescopeapi` connection built from the saved browser session (never password login),
plus a throttled, read-only GET helper that turns logged-out pages into `AuthExpired`.
"""

import time
from collections.abc import Callable
from typing import Any

import requests
from bs4 import BeautifulSoup
from gradescopeapi.classes.account import Account
from gradescopeapi.classes.connection import GSConnection

from app.connectors.base import AuthExpired, PlatformError
from app.connectors.gradescope._vendored.auth_checks import _expiry_reason, _site
from app.connectors.gradescope.login import GRADESCOPE_BASE_URL

TIMEOUT = (10, 60)  # connect, read seconds


def _is_gradescope_cookie(cookie: dict[str, Any]) -> bool:
    domain = str(cookie.get("domain") or "").lstrip(".").lower()
    return domain == "gradescope.com" or domain.endswith(".gradescope.com")


def connection_from_storage_state(
    state: dict[str, Any], base_url: str = GRADESCOPE_BASE_URL
) -> GSConnection:
    """New `GSConnection` carrying only the gradescope.com cookies from a Playwright storage state.

    Never calls `GSConnection.login` (password login). UMass SSO / Duo cookies are left out.
    """
    conn = GSConnection(gradescope_base_url=base_url)
    for c in state.get("cookies", []):
        if not _is_gradescope_cookie(c) or "name" not in c:
            continue
        conn.session.cookies.set(
            c["name"],
            c.get("value", ""),
            domain=c.get("domain"),
            path=c.get("path") or "/",
            secure=bool(c.get("secure", False)),
        )
    conn.logged_in = True
    conn.account = Account(conn.session, base_url)  # type: ignore[assignment]
    return conn


def set_csrf_from_html(conn: GSConnection, html: str) -> None:
    """Copy the page's `<meta name="csrf-token">` into the session headers (Rails CSRF)."""
    meta = BeautifulSoup(html, "html.parser").find("meta", attrs={"name": "csrf-token"})
    if meta is not None and meta.get("content"):
        conn.session.headers["X-CSRF-Token"] = str(meta["content"])


class GradescopeClient:
    """GET-only. At most one request per `min_interval_s` (S14 rule 5)."""

    def __init__(
        self,
        conn: GSConnection,
        *,
        min_interval_s: float = 1.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.conn = conn
        self.base_url = conn.gradescope_base_url.rstrip("/")
        self.min_interval_s = min_interval_s
        self._monotonic, self._sleep = monotonic, sleep
        self._last: float | None = None

    def _throttle(self) -> None:
        if self._last is not None and self.min_interval_s > 0:
            wait = self.min_interval_s - (self._monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._monotonic()

    def get_html(self, path: str) -> tuple[str, str]:
        """GET `path` → (final_url, html). Logged out: AuthExpired; HTTP/network: PlatformError."""
        self._throttle()
        try:
            resp = self.conn.session.get(f"{self.base_url}{path}", timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise PlatformError(f"network error: {type(exc).__name__}") from exc
        site = _site(self.base_url)
        for r in [*resp.history, resp]:
            reason = _expiry_reason(r, site)
            if reason:
                raise AuthExpired(reason)
        if resp.status_code != 200:
            raise PlatformError(f"HTTP {resp.status_code} for {path}")
        return resp.url, resp.text
