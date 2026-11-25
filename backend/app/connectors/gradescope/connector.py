"""S14 Gradescope connector: saved session (S13) → /account course list → student course pages →
NCourse/NItem. Read-only; never calls gradescopeapi's login or any write method.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from gradescopeapi.classes.connection import GSConnection

from app.connectors.base import (
    AccountInfo,
    AuthExpired,
    ConnectorContext,
    NItem,
    NormalizedRecord,
    PlatformError,
    SyncScope,
)
from app.connectors.gradescope.client import (
    GradescopeClient,
    connection_from_storage_state,
    set_csrf_from_html,
)
from app.connectors.gradescope.login import GRADESCOPE_BASE_URL
from app.connectors.gradescope.parsers import (
    DEFAULT_TZ,
    LAYOUT_CHANGED,
    parse_assignments,
    parse_course_list,
    student_courses,
    to_ncourse,
    to_nitem,
)
from app.db.models import Platform

log = logging.getLogger("app.connectors.gradescope")

DEBUG_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "_debug"  # git-ignored


def _save_debug(name: str, html: str) -> None:
    """S14 rule 7: keep the page that broke the parser for a quick local fix (never committed)."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (DEBUG_DIR / f"gradescope_{name}.html").write_text(html)
    except OSError:
        pass


class GradescopeConnector:
    platform: Platform = "gradescope"

    def __init__(
        self,
        *,
        base_url: str = GRADESCOPE_BASE_URL,
        tz: str = DEFAULT_TZ,
        min_interval_s: float = 1.0,
        connection_factory: Callable[[dict[str, Any], str], GSConnection] = (
            connection_from_storage_state
        ),
        save_debug: Callable[[str, str], None] = _save_debug,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.tz = tz
        self.min_interval_s = min_interval_s
        self.connection_factory = connection_factory
        self.save_debug = save_debug

    def _client(self, ctx: ConnectorContext) -> GradescopeClient:
        try:
            state = json.loads(ctx.secret.get_secret_value())
        except ValueError as exc:
            raise AuthExpired("saved Gradescope session is unreadable") from exc
        if not isinstance(state, dict):
            raise AuthExpired("saved Gradescope session is unreadable")
        conn = self.connection_factory(state, self.base_url)
        return GradescopeClient(conn, min_interval_s=self.min_interval_s)

    async def _get(self, ctx: ConnectorContext, client: GradescopeClient, path: str) -> str:
        await ctx.checkpoint()
        _, html = await asyncio.to_thread(client.get_html, path)
        return html

    async def _account(self, ctx: ConnectorContext, client: GradescopeClient) -> str:
        html = await self._get(ctx, client, "/account")
        set_csrf_from_html(client.conn, html)
        return html

    async def validate(self, ctx: ConnectorContext) -> AccountInfo:
        client = self._client(ctx)
        html = await self._account(ctx, client)
        try:
            parse_course_list(html)
        except PlatformError:
            self.save_debug("account", html)
            raise
        return AccountInfo()

    async def _items(
        self, ctx: ConnectorContext, client: GradescopeClient, course_id: str
    ) -> list[NItem]:
        html = await self._get(ctx, client, f"/courses/{course_id}")
        try:
            assignments = parse_assignments(html)
        except PlatformError as exc:
            if str(exc) == LAYOUT_CHANGED:
                self.save_debug(f"course_{course_id}", html)
            raise
        return [to_nitem(a, course_id, self.tz, self.base_url) for a in assignments]

    async def fetch(
        self, ctx: ConnectorContext, scope: SyncScope
    ) -> AsyncIterator[NormalizedRecord]:
        client = self._client(ctx)
        if scope.kind == "material":
            return  # Gradescope has no materials we sync
        if scope.kind == "full":
            html = await self._account(ctx, client)
            try:
                courses = student_courses(parse_course_list(html))
            except PlatformError:
                self.save_debug("account", html)
                raise
            for course in courses:
                yield to_ncourse(course, self.base_url)
                for item in await self._items(ctx, client, course.id):
                    yield item
            return
        assert scope.course_platform_id is not None
        for item in await self._items(ctx, client, scope.course_platform_id):
            if scope.kind == "item" and item.platform_id != scope.platform_id:
                continue
            yield item
