"""Structured request logs (S20).

One JSON line per request with request_id, user_id, method, route template, status and latency.
Never logs headers, cookies, query strings, bodies, message text or course content.
"""

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_log = logging.getLogger("app.request")
_user_box: ContextVar[dict[str, str | None] | None] = ContextVar("_user_box", default=None)


class CalendarAccessFilter(logging.Filter):
    """Uvicorn's default access log otherwise includes the private feed token in its path."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            if isinstance(args[2], str):
                args[2] = re.sub(
                    r"^/calendar/[^/?]+\.ics(?:\?.*)?$", "/calendar/[private].ics", args[2]
                )
            record.args = tuple(args)
        return True


def protect_calendar_access_logs() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, CalendarAccessFilter) for f in logger.filters):
        logger.addFilter(CalendarAccessFilter())


def set_log_user(user_id: str) -> None:
    """Called by `current_user` so the request log line can name the (pseudonymous) user."""
    box = _user_box.get()
    if box is not None:
        box["user_id"] = user_id


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:16]
        status = 500
        start = time.perf_counter()
        # A mutable holder: the endpoint's context can fill it in, and we read it back here.
        user_box: dict[str, str | None] = {"user_id": None}
        token = _user_box.set(user_box)

        async def _send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            route = scope.get("route")
            request_log.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "user_id": user_box["user_id"],
                        "method": scope.get("method"),
                        "route": getattr(route, "path", None) or "unmatched",
                        "status": status,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                )
            )
            _user_box.reset(token)
