"""GET-only Canvas REST client (S11). A student token can submit work, so this client has no
way to send anything but GET: there is no post/put/patch/delete, and `request()` refuses any
other method before touching the network."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from app.connectors.base import AuthExpired, PlatformError

THROTTLE_BELOW = 50.0  # rule 8: X-Rate-Limit-Remaining below this -> 1 s between requests
THROTTLE_SLEEP_S = 1.0
MAX_CONCURRENCY = 4  # rule 8: per user (one client per sync)

Params = dict[str, Any] | None


class ForbiddenMethod(RuntimeError):
    """Anything but GET. The Canvas client is read-only by design."""


class CanvasForbidden(Exception):  # noqa: N818
    """403 that is not rate limiting (e.g. the Files tab is hidden in a course)."""


class CanvasNotFound(Exception):  # noqa: N818
    """404 (object deleted or not visible to the student)."""


class CanvasClient:
    def __init__(
        self,
        base_url: str,
        token: SecretStr,
        http: httpx.AsyncClient,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._host = urlsplit(self.base_url).netloc
        self._token = token
        self._http = http
        self._sleep = sleep
        self._throttle = False
        self._sem = asyncio.Semaphore(MAX_CONCURRENCY)

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            if urlsplit(path_or_url).netloc != self._host:  # never send the token elsewhere
                raise PlatformError("Canvas returned a link to another host")
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    async def request(self, method: str, path: str, params: Params = None) -> httpx.Response:
        if method.upper() != "GET":
            raise ForbiddenMethod(f"Canvas client is GET-only (refused {method.upper()})")
        url = self._url(path)
        async with self._sem:
            if self._throttle:
                await self._sleep(THROTTLE_SLEEP_S)
            try:
                resp = await self._http.request(
                    "GET",
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self._token.get_secret_value()}"},
                )
            except httpx.HTTPError as exc:  # timeouts, connection errors
                raise PlatformError(f"Canvas request failed: {type(exc).__name__}") from exc
        self._update_throttle(resp)
        self._raise_for_status(resp)
        return resp

    def _update_throttle(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-Rate-Limit-Remaining")
        try:
            self._throttle = remaining is not None and float(remaining) < THROTTLE_BELOW
        except ValueError:
            self._throttle = False

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        code = resp.status_code
        if code < 400:
            return
        where = resp.request.url.path
        if code == 401:
            raise AuthExpired("Canvas token is invalid or expired")
        if code == 403:
            if "rate limit exceeded" in resp.text.lower():
                raise PlatformError("Canvas rate limit exceeded")
            raise CanvasForbidden(where)
        if code == 404:
            raise CanvasNotFound(where)
        raise PlatformError(f"Canvas returned {code} for {where}")

    async def get(self, path: str, params: Params = None) -> Any:
        """One page / one object, parsed JSON."""
        return (await self.request("GET", path, params)).json()

    async def paginate(self, path: str, params: Params = None) -> AsyncIterator[Any]:
        """Every element of a list endpoint, following `Link: <...>; rel="next"`."""
        url: str | None = path
        while url:
            resp = await self.request("GET", url, params)
            try:
                data = resp.json()
            except ValueError:
                raise PlatformError("Canvas returned an invalid list response") from None
            if not isinstance(data, list):
                raise PlatformError("Canvas returned an invalid list response")
            for element in data:
                yield element
            nxt = resp.links.get("next", {}).get("url")
            url, params = nxt, None  # the next link already carries the query
