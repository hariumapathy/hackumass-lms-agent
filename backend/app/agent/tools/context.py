"""RunCtx: what the harness passes to every tool (never chosen by the model)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.clock import Clock

StatusEmitter = Callable[[str, str, str], Awaitable[None]]  # (tool, label, state)


@dataclass
class RunCtx:
    user_id: UUID
    timezone: str
    clock: Clock
    conn: Any = None  # psycopg AsyncConnection; None in pure unit tests
    allowed_chunk_ids: set[int] = field(default_factory=set)
    status_emitter: StatusEmitter | None = None
