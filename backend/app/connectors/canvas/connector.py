"""Canvas connector (S11): personal access token -> normalized records for the S10 pipeline."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.connectors.base import AccountInfo, ConnectorContext, NormalizedRecord, SyncScope
from app.connectors.canvas import mapping as m
from app.connectors.canvas.client import CanvasClient, CanvasForbidden, CanvasNotFound
from app.db.models import Platform

log = logging.getLogger("app.connectors.canvas")

ANNOUNCEMENT_WINDOW = timedelta(days=60)
EVENT_HORIZON = timedelta(days=120)
EVENT_LOOKBACK_FALLBACK = timedelta(days=120)  # when a course has no term/course start date
MAX_FILES_PER_COURSE = 500
HTTP_TIMEOUT_S = 30.0


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class CanvasConnector:
    platform: Platform = "canvas"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        incremental_announcements: bool = False,
        max_files_per_course: int = MAX_FILES_PER_COURSE,
    ) -> None:
        self._base_url = base_url
        self._sleep = sleep
        self.incremental_announcements = incremental_announcements
        self.max_files_per_course = max_files_per_course

    @property
    def base_url(self) -> str:
        if self._base_url:
            return self._base_url.rstrip("/")
        from app.core.settings import get_settings

        return get_settings().canvas_base_url.rstrip("/")

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=HTTP_TIMEOUT_S, follow_redirects=False)

    async def validate(self, ctx: ConnectorContext) -> AccountInfo:
        """GET /users/self. 401 -> AuthExpired (the connect flow reports `invalid_token`)."""
        async with self._http() as http:
            client = CanvasClient(self.base_url, ctx.secret, http, sleep=self._sleep)
            me = await client.get("/api/v1/users/self")
        uid = me.get("id")
        return AccountInfo(
            account_label=me.get("name") or me.get("short_name") or None,
            platform_user_id=str(uid) if uid is not None else None,
        )

    async def fetch(
        self, ctx: ConnectorContext, scope: SyncScope
    ) -> AsyncIterator[NormalizedRecord]:
        async with self._http() as http:
            run = _Run(self, CanvasClient(self.base_url, ctx.secret, http, sleep=self._sleep), ctx)
            if scope.kind == "full":
                gen = run.full()
            elif scope.kind == "course":
                gen = run.one_course(str(scope.course_platform_id))
            elif scope.kind == "item":
                gen = run.one_item(str(scope.course_platform_id), str(scope.platform_id))
            else:
                gen = run.one_material(str(scope.course_platform_id), str(scope.platform_id))
            async for rec in gen:
                yield rec


class _Run:
    """One fetch: holds the client, clock and settings for the duration of a sync."""

    def __init__(self, conn: CanvasConnector, client: CanvasClient, ctx: ConnectorContext):
        self.c, self.client, self.ctx = conn, client, ctx
        self.base = client.base_url
        self.now: datetime = ctx.clock.now()

    # --- scopes ----------------------------------------------------------------------------
    async def full(self) -> AsyncIterator[NormalizedRecord]:
        params = {"enrollment_state": "active", "include[]": ["term"], "per_page": 100}
        courses = [c async for c in self.client.paginate("/api/v1/courses", params)]
        for course in courses:
            if not m.course_usable(course):
                continue
            async for rec in self.course_contents(course, incremental=True):
                yield rec

    async def one_course(self, course_id: str) -> AsyncIterator[NormalizedRecord]:
        try:
            course = await self.client.get(
                f"/api/v1/courses/{course_id}", {"include[]": ["term", "syllabus_body"]}
            )
        except (CanvasNotFound, CanvasForbidden):
            log.warning("canvas: course %s not available", course_id)
            return
        if not m.course_usable(course):
            return
        async for rec in self.course_contents(course, incremental=False, detail=course):
            yield rec

    async def one_item(self, course_id: str, item_id: str) -> AsyncIterator[NormalizedRecord]:
        try:
            if item_id.startswith("event-"):
                ev = await self.client.get(f"/api/v1/calendar_events/{item_id[6:]}")
                rec = m.event_to_item(ev, course_id, self.base)
            else:
                a = await self.client.get(
                    f"/api/v1/courses/{course_id}/assignments/{item_id}",
                    {"include[]": ["submission"]},
                )
                rec = m.to_item(a, course_id, self.base)
        except (CanvasNotFound, CanvasForbidden):
            log.warning("canvas: item %s/%s not available", course_id, item_id)
            return
        if rec is not None:
            yield rec

    async def one_material(self, course_id: str, mat_id: str) -> AsyncIterator[NormalizedRecord]:
        try:
            if mat_id.startswith("syllabus-"):
                course = await self.client.get(
                    f"/api/v1/courses/{course_id}", {"include[]": ["syllabus_body"]}
                )
                rec = m.to_syllabus(course, self.base)
            else:
                f = await self.client.get(f"/api/v1/courses/{course_id}/files/{mat_id}")
                rec = m.to_file_material(f, course_id, self.base)
        except (CanvasNotFound, CanvasForbidden):
            log.warning("canvas: material %s/%s not available", course_id, mat_id)
            return
        if rec is not None:
            yield rec

    # --- one course ------------------------------------------------------------------------
    async def course_contents(
        self, course: dict[str, Any], *, incremental: bool, detail: dict[str, Any] | None = None
    ) -> AsyncIterator[NormalizedRecord]:
        cid = str(course["id"])
        yield m.to_course(course, self.base)
        sections: list[tuple[str, str, Callable[[], AsyncIterator[NormalizedRecord]]]] = [
            ("syllabus", "materials", lambda: self.syllabus(cid, detail)),
            ("assignments", "item_sources", lambda: self.assignments(cid)),
            ("calendar events", "item_sources", lambda: self.events(cid, course)),
            ("announcements", "posts", lambda: self.announcements(cid, incremental)),
            ("files", "materials", lambda: self.files(cid)),
        ]
        # Announcements are listed for a time window only: never treat older ones as removed.
        self.ctx.incomplete.add((cid, "posts"))
        for name, table, section in sections:
            try:
                async for rec in section():
                    yield rec
            except (CanvasForbidden, CanvasNotFound):
                # One hidden tab must not fail the whole sync (AuthExpired/PlatformError still do),
                # and must not make that tab's earlier records look removed.
                self.ctx.incomplete.add((cid, table))
                log.warning("canvas: skipped %s for course %s (not available)", name, cid)

    async def syllabus(
        self, cid: str, detail: dict[str, Any] | None
    ) -> AsyncIterator[NormalizedRecord]:
        course: dict[str, Any] = detail or {}
        if "syllabus_body" not in course:
            course = await self.client.get(
                f"/api/v1/courses/{cid}", {"include[]": ["syllabus_body"]}
            )
        rec = m.to_syllabus(course, self.base)
        if rec:
            yield rec

    async def assignments(self, cid: str) -> AsyncIterator[NormalizedRecord]:
        params = {"per_page": 100, "order_by": "due_at", "include[]": ["submission"]}
        async for a in self.client.paginate(f"/api/v1/courses/{cid}/assignments", params):
            yield m.to_item(a, cid, self.base)

    async def events(self, cid: str, course: dict[str, Any]) -> AsyncIterator[NormalizedRecord]:
        term = course.get("term") or {}
        start = (
            m.parse_dt(term.get("start_at"))
            or m.parse_dt(course.get("start_at"))
            or self.now - EVENT_LOOKBACK_FALLBACK
        )
        params = {
            "type": "event",
            "context_codes[]": f"course_{cid}",
            "start_date": _iso(start),
            "end_date": _iso(self.now + EVENT_HORIZON),
            "per_page": 100,
        }
        async for ev in self.client.paginate("/api/v1/calendar_events", params):
            rec = m.event_to_item(ev, cid, self.base)
            if rec:
                yield rec

    async def announcements(self, cid: str, incremental: bool) -> AsyncIterator[NormalizedRecord]:
        start = self.now - ANNOUNCEMENT_WINDOW
        last = self.ctx.last_success_at
        if incremental and self.c.incremental_announcements and last is not None:
            start = last - timedelta(days=1)  # rule 7 (off by default, see S11 notes)
        params = {
            "context_codes[]": f"course_{cid}",
            "start_date": _iso(start),
            "end_date": _iso(self.now + timedelta(days=1)),
            "per_page": 100,
        }
        async for a in self.client.paginate("/api/v1/announcements", params):
            rec = m.to_post(a, cid, self.base)
            if rec:
                yield rec

    async def files(self, cid: str) -> AsyncIterator[NormalizedRecord]:
        cap = self.c.max_files_per_course
        count = 0
        try:
            source = self.client.paginate(
                f"/api/v1/courses/{cid}/files", {"per_page": 100, "sort": "updated_at"}
            )
            async for f in source:
                rec = m.to_file_material(f, cid, self.base)
                if rec is None:
                    continue
                if count >= cap:
                    self.ctx.incomplete.add((cid, "materials"))
                    log.info("canvas: course %s has more than %d files; capped", cid, cap)
                    return
                count += 1
                yield rec
            return
        except CanvasForbidden:
            log.info("canvas: files tab hidden for course %s; using modules", cid)
        async for rec in self.module_files(cid, cap):
            yield rec

    async def module_files(self, cid: str, cap: int) -> AsyncIterator[NormalizedRecord]:
        # Modules expose a subset of course files, even when every listed item is readable.
        # Never infer that earlier files disappeared from this non-authoritative fallback.
        self.ctx.incomplete.add((cid, "materials"))
        seen: set[str] = set()
        params = {"include[]": ["items"], "per_page": 100}
        file_ids: list[str] = []
        async for module in self.client.paginate(f"/api/v1/courses/{cid}/modules", params):
            for it in module.get("items") or []:
                fid = str(it.get("content_id") or "")
                if it.get("type") == "File" and fid and fid not in seen:
                    seen.add(fid)
                    file_ids.append(fid)
        count = 0
        for fid in file_ids:
            if count >= cap:
                log.info("canvas: course %s has more than %d module files; capped", cid, cap)
                return
            try:
                f = await self.client.get(f"/api/v1/courses/{cid}/files/{fid}")
            except (CanvasForbidden, CanvasNotFound):
                continue
            rec = m.to_file_material(f, cid, self.base)
            if rec:
                count += 1
                yield rec
