"""Data access for agent tools (S21).

Tools read through `ToolData`, already scoped to ONE student. Two implementations:
- `MockToolData` (`mock_source.py`): the S02 mock semester; lets the real agent run before S01.
- `DbToolData` (after S01/S03): SQL in `app/db/repositories/`, every query filtered by user_id.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

from app.agent.tools.courses import CourseRef
from app.agent.tools.coverage import ConnectionState


class ItemRow(BaseModel):
    id: UUID
    course_id: UUID
    course_code: str
    type: str
    title: str
    due_at: datetime | None = None
    points: float | None = None
    status: str = "active"
    changed_fields: list[str] = []
    platforms: list[str] = []
    submitted: bool = False


class ChangeRow(BaseModel):
    course_id: UUID
    course_code: str
    entity_type: str
    field: str
    old_value: Any = None
    new_value: Any = None
    detected_at: datetime
    summary: str | None = None


class ChunkRow(BaseModel):
    chunk_id: int
    course_id: UUID
    course_code: str
    material_id: str | None = None
    file_id: UUID | None = None  # stored original PDF the app can show (GET /files/{id})
    title: str
    kind: str  # slides | transcript | post | syllabus
    platform: str
    post_kind: str | None = None  # announcement | piazza | email (posts only)
    page: int | None = None
    start_s: int | None = None
    end_s: int | None = None
    text: str
    posted_or_recorded_at: datetime | None = None
    source_url: str
    last_synced_at: datetime
    status: str = "current"  # current | changed | removed


@dataclass
class SyncOutcome:
    status: str  # completed | running | failed | needs_reconnect | not_connected
    added: int = 0
    updated: int = 0
    sync_run_ids: list[str] = field(default_factory=list)


class ToolData(Protocol):
    async def courses(self) -> list[CourseRef]: ...
    async def connections(self) -> list[ConnectionState]: ...
    async def items(self, course_id: UUID | None, item_type: str | None) -> list[ItemRow]: ...
    async def changes(self, since: datetime, course_id: UUID | None) -> list[ChangeRow]: ...
    async def search(
        self, query: str, course_id: UUID | None, kind: str, source: str | None, k: int
    ) -> list[ChunkRow]: ...
    async def material_chunks(self, material_id: str) -> list[ChunkRow]: ...
    async def chunks_by_id(self, ids: list[int]) -> list[ChunkRow]: ...
    async def record_miss(self, tool: str, query: str, course_id: UUID | None) -> None: ...
    async def request_sync(
        self, platforms: list[str], course_id: UUID | None, timeout_s: float
    ) -> SyncOutcome: ...
