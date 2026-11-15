"""`DbToolData`: agent tool data from the S01 database, scoped to ONE student (S21).

Each method borrows a pooled connection. Search embeds the query with the configured provider
(Gemini, or fake in tests); if embedding fails, search falls back to full-text only.
`request_sync` is `fetch_latest`: S10 `enqueue_sync(trigger="agent")` + `wait_for_sync`.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any
from uuid import UUID

from app.agent.tools.courses import CourseRef
from app.agent.tools.coverage import ConnectionState
from app.agent.tools.data import ChangeRow, ChunkRow, ItemRow, SyncOutcome
from app.core.change_text import change_summary
from app.core.embeddings import EmbeddingProvider, to_pgvector
from app.db.repositories import agent as repo
from app.db.repositories import sync as sync_repo

log = logging.getLogger(__name__)

ConnectionFactory = Callable[[], AbstractAsyncContextManager[Any]]


def _summary(row: dict[str, Any]) -> str:
    title = row.get("entity_title") or row["entity_type"]
    return change_summary(row["course_code"], title, row["field"], row.get("new_value"))


class DbToolData:
    def __init__(
        self,
        user_id: UUID,
        connection: ConnectionFactory,
        embedder: EmbeddingProvider | None = None,
        enqueue: Callable[..., Any] | None = None,
        wait: Callable[..., Any] | None = None,
    ) -> None:
        self.user_id = user_id
        self._connection = connection
        self._embedder = embedder
        self._enqueue = enqueue
        self._wait = wait

    async def courses(self) -> list[CourseRef]:
        async with self._connection() as conn:
            rows = await repo.list_courses(conn, self.user_id)
        return [CourseRef(id=r["id"], code=r["code"], name=r["name"]) for r in rows]

    async def connections(self) -> list[ConnectionState]:
        async with self._connection() as conn:
            rows = await sync_repo.list_connections(conn, self.user_id)
        return [ConnectionState(c.platform, c.status, c.last_sync_at) for c in rows]

    async def items(self, course_id: UUID | None, item_type: str | None) -> list[ItemRow]:
        async with self._connection() as conn:
            rows = await repo.list_items(conn, self.user_id, course_id, item_type)
        return [ItemRow.model_validate(r) for r in rows]

    async def changes(self, since: datetime, course_id: UUID | None) -> list[ChangeRow]:
        async with self._connection() as conn:
            rows = await repo.list_changes(conn, self.user_id, since, course_id)
        return [
            ChangeRow(
                course_id=r["course_id"] or UUID(int=0),
                course_code=r["course_code"],
                entity_type=r["entity_type"],
                field=r["field"],
                old_value=r["old_value"],
                new_value=r["new_value"],
                detected_at=r["detected_at"],
                summary=_summary(r),
            )
            for r in rows
        ]

    async def _embed(self, query: str) -> str | None:
        if self._embedder is None:
            return None
        try:
            vec = (await asyncio.wait_for(self._embedder.embed([query]), timeout=8))[0]
        except Exception as exc:  # noqa: BLE001 - fall back to full-text search
            log.warning("query embedding failed: %s", type(exc).__name__)
            return None
        return to_pgvector(vec)

    async def search(
        self, query: str, course_id: UUID | None, kind: str, source: str | None, k: int
    ) -> list[ChunkRow]:
        vec = await self._embed(query)
        async with self._connection() as conn:
            rows = await repo.search_chunks(
                conn, self.user_id, query, vec, course_id, kind, source, k
            )
        return [ChunkRow.model_validate(r) for r in rows]

    async def material_chunks(self, material_id: str) -> list[ChunkRow]:
        try:
            mid = UUID(material_id)
        except ValueError:
            return []
        async with self._connection() as conn:
            rows = await repo.material_chunks(conn, self.user_id, mid)
        return [ChunkRow.model_validate(r) for r in rows]

    async def chunks_by_id(self, ids: list[int]) -> list[ChunkRow]:
        async with self._connection() as conn:
            rows = await repo.chunks_by_id(conn, self.user_id, ids)
        return [ChunkRow.model_validate(r) for r in rows]

    async def record_miss(self, tool: str, query: str, course_id: UUID | None) -> None:
        async with self._connection() as conn:
            await repo.record_miss(conn, self.user_id, tool, query, course_id)

    async def request_sync(
        self, platforms: list[str], course_id: UUID | None, timeout_s: float
    ) -> SyncOutcome:
        from app.connectors.base import SyncScope
        from app.sync import jobs

        enqueue = self._enqueue or jobs.enqueue_sync
        wait = self._wait or jobs.wait_for_sync
        run_ids: list[UUID] = []
        async with self._connection() as conn:
            for platform in platforms:
                scope = SyncScope()
                if course_id:
                    pid = await repo.course_platform_id(conn, self.user_id, course_id, platform)
                    if pid:
                        scope = SyncScope(kind="course", course_platform_id=pid)
                run_ids.append(await enqueue(conn, self.user_id, platform, scope, "agent"))
            results = [await wait(conn, self.user_id, rid, timeout_s=timeout_s) for rid in run_ids]
        statuses = {r.status for r in results}
        if any(r.timed_out for r in results):
            status = "running"
        elif "needs_reconnect" in statuses:
            status = "needs_reconnect"
        elif "failed" in statuses:
            status = "failed"
        else:
            status = "completed"
        added = sum(int((r.stats or {}).get("new", 0)) for r in results)
        updated = sum(int((r.stats or {}).get("changed", 0)) for r in results)
        return SyncOutcome(
            status=status, added=added, updated=updated, sync_run_ids=[str(r) for r in run_ids]
        )
