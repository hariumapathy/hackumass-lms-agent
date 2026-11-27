"""S17 Piazza connector: saved session (S13) → enrolled current-term classes → feed (newest
first, capped) → full post only for new/changed feed items → NCourse / NPost.

Read-only; never logs in with a password, never posts, edits or marks anything.
"""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any

from app.connectors.base import (
    AccountInfo,
    AuthExpired,
    ConnectorContext,
    NormalizedRecord,
    NPost,
    PlatformError,
    SyncScope,
)
from app.connectors.piazza._vendored.client import (
    PiazzaAuthenticationError,
    PiazzaClient,
    PiazzaClientError,
    PiazzaClientProtocol,
    PiazzaResponseError,
)
from app.connectors.piazza._vendored.normalizer import PiazzaNormalizationError, PiazzaNormalizer
from app.connectors.piazza.mapping import feed_updated, is_current_term, to_ncourse, to_npost
from app.db.models import Platform

log = logging.getLogger("app.connectors.piazza")

MAX_POSTS_PER_CLASS = 300  # S17 rule 3


def _client_from_state(state: dict[str, Any], min_interval_s: float) -> PiazzaClientProtocol:
    return PiazzaClient.from_storage_state(state, min_interval_s=min_interval_s)


class PiazzaConnector:
    platform: Platform = "piazza"

    def __init__(
        self,
        *,
        min_interval_s: float = 1.0,
        max_posts: int = MAX_POSTS_PER_CLASS,
        client_factory: Callable[[dict[str, Any], float], PiazzaClientProtocol] = (
            _client_from_state
        ),
    ) -> None:
        self.min_interval_s = min_interval_s
        self.max_posts = max_posts
        self.client_factory = client_factory
        self.normalizer = PiazzaNormalizer()

    def _client(self, ctx: ConnectorContext) -> PiazzaClientProtocol:
        try:
            state = json.loads(ctx.secret.get_secret_value())
        except ValueError as exc:
            raise AuthExpired("saved Piazza session is unreadable") from exc
        if not isinstance(state, dict):
            raise AuthExpired("saved Piazza session is unreadable")
        return self.client_factory(state, self.min_interval_s)

    @staticmethod
    async def _call(ctx: ConnectorContext, operation: Callable[[], Awaitable[Any]]) -> Any:
        await ctx.checkpoint()
        try:
            return await operation()
        except PiazzaAuthenticationError as exc:
            raise AuthExpired("Piazza session expired") from exc
        except PiazzaClientError as exc:
            raise PlatformError(f"Piazza: {type(exc).__name__}") from exc

    async def validate(self, ctx: ConnectorContext) -> AccountInfo:
        await self._call(ctx, self._client(ctx).list_courses)
        return AccountInfo()  # no name/email stored

    async def _post(
        self,
        ctx: ConnectorContext,
        client: PiazzaClientProtocol,
        nid: str,
        number: int,
        now: datetime,
    ) -> NPost | None:
        try:
            raw = await self._call(ctx, lambda: client.get_post(nid, number))
        except PlatformError as exc:
            if isinstance(exc.__cause__, PiazzaResponseError):
                return None  # one unusable post: skip it, keep the class
            raise
        try:
            thread = self.normalizer.normalize_thread(raw, nid)
        except PiazzaNormalizationError:
            return None
        return to_npost(thread, raw, now)

    async def _posts(
        self, ctx: ConnectorContext, client: PiazzaClientProtocol, nid: str
    ) -> AsyncIterator[NPost]:
        feed = await self._call(ctx, lambda: client.list_posts(nid, self.max_posts, 0))
        # Windowed listing: capped feed, unchanged posts not re-fetched (so not yielded) →
        # full-scope removal must skip this class's posts (S10 rule 5).
        complete = len(feed) < self.max_posts
        since = ctx.last_success_at
        now = ctx.clock.now()
        for item in feed[: self.max_posts]:
            try:
                number = int(item.get("nr"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                complete = False
                continue
            updated = feed_updated(item)
            if since is not None and updated is not None and updated <= since:
                complete = False  # unchanged since the last good sync: no get_post (S17-T04)
                continue
            post = await self._post(ctx, client, nid, number, now)
            if post is None:
                complete = False
                continue
            yield post
        if not complete:
            ctx.incomplete.add((nid, "posts"))

    async def fetch(
        self, ctx: ConnectorContext, scope: SyncScope
    ) -> AsyncIterator[NormalizedRecord]:
        client = self._client(ctx)
        if scope.kind == "material":
            return  # Piazza has no materials
        if scope.kind == "item":
            assert scope.course_platform_id is not None and scope.platform_id is not None
            nid, _, nr = scope.platform_id.rpartition(":")
            if nr.isdigit():
                post = await self._post(
                    ctx, client, nid or scope.course_platform_id, int(nr), ctx.clock.now()
                )
                if post is not None:
                    yield post
            return
        if scope.kind == "course":
            assert scope.course_platform_id is not None
            async for post in self._posts(ctx, client, scope.course_platform_id):
                yield post
            return
        classes = await self._call(ctx, client.list_courses)
        now = ctx.clock.now()
        for raw in classes:
            if not raw.get("nid") or not is_current_term(raw.get("term"), now):
                continue
            course = to_ncourse(raw)
            yield course
            async for post in self._posts(ctx, client, course.platform_id):
                yield post
