# Vendored from https://github.com/profess/piazza-mcp @ 782f62c,
# src/piazza_mcp/services/piazza/client.py, MIT License, (c) 2026 mkslge
# (full text: LICENSE-piazza-mcp in this folder).
# Modified for S17: REMOVED the email/password login (`_authenticate` / `rpc.user_login`) and the
# `PiazzaConfig` dependency; ADDED `PiazzaClient.from_storage_state()` (cookies from the student's
# saved S13 browser session, piazza.com cookies only) and a throttle (>= 1 s between requests) in
# `_TimeoutSession`, which also turns HTTP 401/403 into `NotAuthenticatedError` and 429/5xx into
# `requests.HTTPError`; REMOVED
# `search_posts` / `list_filtered_posts` (unused); `_run_sync` runs once (no re-login retry) and
# maps piazza-api `RequestError`s that mention login/session/auth to `PiazzaAuthenticationError`.
# Read-only: no method creates, edits or marks anything.
"""Async, bounded, read-only adapter around the synchronous unofficial Piazza API."""

import asyncio
import json
import re
import time
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

import requests
from piazza_api import Piazza
from piazza_api.exceptions import AuthenticationError, NotAuthenticatedError, RequestError
from piazza_api.rpc import PiazzaRPC


class PiazzaClientError(RuntimeError):
    """Base error for safe Piazza transport failures."""


class PiazzaAuthenticationError(PiazzaClientError):
    """Raised when Piazza credentials or session authentication fail."""


class PiazzaTimeoutError(PiazzaClientError):
    """Raised when Piazza does not respond before the configured timeout."""


class PiazzaResponseError(PiazzaClientError):
    """Raised when Piazza returns an unusable response."""


class PiazzaClientProtocol(Protocol):
    async def list_courses(self) -> list[dict[str, Any]]: ...

    async def list_posts(self, course_id: str, limit: int, offset: int) -> list[dict[str, Any]]: ...

    async def get_post(self, course_id: str, post_number: int) -> dict[str, Any]: ...


_AUTH_ERROR_RE = re.compile(r"log\s*-?\s*(?:ged\s*)?in|auth|session|expired|csrf", re.IGNORECASE)


def _is_piazza_cookie(cookie: dict[str, Any]) -> bool:
    domain = str(cookie.get("domain") or "").lstrip(".").lower()
    return domain == "piazza.com" or domain.endswith(".piazza.com")


class _TimeoutSession(requests.Session):
    def __init__(
        self,
        timeout_seconds: float,
        *,
        min_interval_s: float = 1.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__()
        self.timeout_seconds = timeout_seconds
        self.min_interval_s = min_interval_s
        self._monotonic, self._sleep = monotonic, sleep
        self._last: float | None = None

    def _throttle(self) -> None:
        if self._last is not None and self.min_interval_s > 0:
            wait = self.min_interval_s - (self._monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._monotonic()

    def request(self, method, url, *args, **kwargs):  # type: ignore[override]  # noqa: ANN001, ANN002, ANN003, ANN201
        self._throttle()
        kwargs.setdefault("timeout", self.timeout_seconds)
        response = super().request(method, url, *args, **kwargs)
        if response.status_code in (401, 403):
            raise NotAuthenticatedError("Piazza rejected the session")
        if response.status_code == 429 or response.status_code >= 500:
            raise requests.HTTPError(f"Piazza HTTP {response.status_code}")
        return response


T = TypeVar("T")


class PiazzaClient:
    """Async, bounded adapter around the synchronous unofficial Piazza API."""

    def __init__(self, piazza: Piazza):
        self._piazza = piazza
        self._lock = asyncio.Lock()

    @classmethod
    def from_storage_state(
        cls,
        state: dict[str, Any],
        *,
        timeout_seconds: float = 30.0,
        min_interval_s: float = 1.0,
        session: _TimeoutSession | None = None,
    ) -> "PiazzaClient":
        """Client using the piazza.com cookies of a Playwright storage state (S13). Never logs in.

        piazza-api sends the `session_id` cookie as the `CSRF-Token` header on every call.
        """
        sess = session or _TimeoutSession(timeout_seconds, min_interval_s=min_interval_s)
        for c in state.get("cookies", []):
            if not isinstance(c, dict) or not _is_piazza_cookie(c) or "name" not in c:
                continue
            sess.cookies.set(
                c["name"],
                c.get("value", ""),
                domain=c.get("domain"),
                path=c.get("path") or "/",
                secure=bool(c.get("secure", False)),
            )
        rpc = PiazzaRPC()
        rpc.session = sess
        return cls(Piazza(piazza_rpc=rpc))

    @property
    def session(self) -> requests.Session:
        return self._piazza._rpc_api.session  # type: ignore[union-attr]

    async def list_courses(self) -> list[dict[str, Any]]:
        result = await self._run(lambda piazza: piazza.get_user_classes())
        return self._require_dict_list(result, "course list")

    async def list_posts(self, course_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        result = await self._run(lambda piazza: piazza.network(course_id).get_feed(limit, offset))
        return self._extract_posts(result, "Piazza feed")

    async def get_post(self, course_id: str, post_number: int) -> dict[str, Any]:
        result = await self._run(lambda piazza: piazza.network(course_id).get_post(post_number))
        if not isinstance(result, dict) or not result:
            raise PiazzaResponseError("Piazza returned an invalid post")
        return result

    async def _run(self, operation: Callable[[Piazza], T]) -> T:
        async with self._lock:
            return await asyncio.to_thread(self._run_sync, operation)

    def _run_sync(self, operation: Callable[[Piazza], T]) -> T:
        try:
            if "session_id" not in self.session.cookies:
                raise NotAuthenticatedError("no Piazza session cookie")
            return operation(self._piazza)
        except (AuthenticationError, NotAuthenticatedError):
            raise PiazzaAuthenticationError("Unable to authenticate with Piazza") from None
        except RequestError as exc:
            if _AUTH_ERROR_RE.search(str(exc).split("Response:")[-1]):
                raise PiazzaAuthenticationError("Unable to authenticate with Piazza") from None
            raise PiazzaResponseError("Piazza returned an error") from None
        except requests.Timeout:
            raise PiazzaTimeoutError("Piazza request timed out") from None
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            raise PiazzaResponseError("Piazza returned an invalid response") from None
        except requests.RequestException:
            raise PiazzaClientError("Unable to reach Piazza") from None
        except PiazzaClientError:
            raise
        except Exception:
            raise PiazzaClientError("Unable to load Piazza data") from None

    @staticmethod
    def _require_dict_list(value: Any, label: str) -> list[dict[str, Any]]:
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise PiazzaResponseError(f"Piazza returned an invalid {label}")
        return value

    @classmethod
    def _extract_posts(cls, value: Any, label: str) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return cls._require_dict_list(value, label)
        if isinstance(value, dict):
            for key in ("feed", "posts", "results"):
                if key in value:
                    return cls._require_dict_list(value[key], label)
        raise PiazzaResponseError(f"Piazza returned an invalid {label}")
