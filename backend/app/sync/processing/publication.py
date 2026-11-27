"""S48 owner/source snapshots and short parent -> intent publication transactions.

The private parent generation is checked on every path, including trusted direct helpers.
The scoped context adds production intent binding without changing worker adapter signatures;
it never substitutes for the explicit parent snapshot.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any, Literal
from uuid import UUID

from psycopg import AsyncConnection

from app.db.repositories import processing as intents
from app.sync.access import session_lock

ParentTable = Literal["materials", "posts"]


class ProcessingSuperseded(Exception):
    """Source/intent changed; old output must not publish or alter replacement state."""


@dataclass(frozen=True)
class WorkSnapshot:
    user_id: UUID
    parent_id: UUID
    table: ParentTable
    source_revision: UUID
    source_hash: str
    intent_id: UUID | None = None
    intent_revision: UUID | None = None
    base_version: int | None = None
    base_path: str | None = None


_expected: ContextVar[WorkSnapshot | None] = ContextVar("expected_processing_work", default=None)


@contextmanager
def bind_intent(row: dict[str, Any]) -> Iterator[None]:
    token = _expected.set(
        WorkSnapshot(
            user_id=row["user_id"],
            parent_id=row["material_id"] or row["post_id"],
            table="materials" if row["material_id"] else "posts",
            source_revision=row["parent_source_revision"],
            source_hash=row["source_hash"],
            intent_id=row["id"],
            intent_revision=row["revision"],
        )
    )
    try:
        yield
    finally:
        _expected.reset(token)


def snapshot(
    user_id: UUID, parent_id: UUID, table: ParentTable, row: dict[str, Any]
) -> WorkSnapshot:
    if row["status"] == "removed":
        raise ProcessingSuperseded()
    observed = WorkSnapshot(
        user_id,
        parent_id,
        table,
        row["source_revision"],
        row["content_hash"],
        base_version=row.get("version"),
        base_path=row.get("storage_path"),
    )
    expected = _expected.get()
    if expected is None:
        return observed  # Trusted direct helper: still requires its own mandatory parent fence.
    if (
        expected.user_id != user_id
        or expected.parent_id != parent_id
        or expected.table != table
        or expected.source_revision != observed.source_revision
        or expected.source_hash != observed.source_hash
    ):
        raise ProcessingSuperseded()
    return replace(observed, intent_id=expected.intent_id, intent_revision=expected.intent_revision)


@asynccontextmanager
async def parent_work(
    conn: AsyncConnection[Any], user_id: UUID, parent_id: UUID, table: ParentTable
) -> AsyncIterator[None]:
    # deletion imports Storage via this package; defer the barrier import until runtime.
    from app.db.deletion import user_work

    async with (
        user_work(conn, user_id),
        session_lock(conn, f"processing-parent:{user_id}:{table}:{parent_id}"),
    ):
        yield


@asynccontextmanager
async def publication(
    conn: AsyncConnection[Any], work: WorkSnapshot
) -> AsyncIterator[dict[str, Any]]:
    async with conn.transaction():
        parent = await (
            await conn.execute(
                f"select * from {work.table} where user_id=%s and id=%s for update",
                (work.user_id, work.parent_id),
            )
        ).fetchone()
        if (
            not parent
            or parent["status"] == "removed"
            or parent["source_revision"] != work.source_revision
            or parent["content_hash"] != work.source_hash
            or (
                work.base_version is not None
                and (
                    parent["version"] != work.base_version
                    or parent["storage_path"] != work.base_path
                )
            )
        ):
            raise ProcessingSuperseded()
        if work.intent_id is not None:
            row = await (
                await conn.execute(
                    "select revision,source_hash,parent_source_revision,completed_at "
                    "from processing_intents "
                    "where user_id=%s and id=%s "
                    "and coalesce(material_id,post_id)=%s for update",
                    (work.user_id, work.intent_id, work.parent_id),
                )
            ).fetchone()
            if (
                not row
                or row["revision"] != work.intent_revision
                or row["completed_at"]
                or row["source_hash"] != work.source_hash
                or row["parent_source_revision"] != work.source_revision
            ):
                raise ProcessingSuperseded()
        yield parent


async def complete(conn: AsyncConnection[Any], work: WorkSnapshot) -> None:
    """Only call inside the same guarded publication transaction as chunks/pointer/status."""
    if work.intent_id is not None and work.intent_revision is not None:
        await intents.complete(conn, work.user_id, work.intent_id, work.intent_revision)
