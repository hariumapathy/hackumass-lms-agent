"""Connector interface (S10). Every platform connector (S11 Canvas, S14 Gradescope, ...) yields
these normalized records; the sync pipeline diffs and stores them. Connectors never touch the DB.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.db.models import ItemType, MaterialKind, Platform, PostKind


class AuthExpired(Exception):  # noqa: N818 (name fixed by the S10 spec)
    """Session/token no longer valid -> connection `needs_reconnect`, no retry."""


class SourceAccessError(Exception):
    """One file is unavailable; this alone does not prove the entire platform grant expired."""


class PlatformError(Exception):
    """Transient platform failure (5xx, timeout, rate limit) -> retried with backoff."""


class SyncScope(BaseModel):
    kind: Literal["full", "course", "item", "material"] = "full"
    course_platform_id: str | None = None  # required for course/item/material
    platform_id: str | None = None  # required for item/material

    @model_validator(mode="after")
    def _check(self) -> "SyncScope":
        if self.kind != "full" and not self.course_platform_id:
            raise ValueError(f"scope {self.kind!r} needs course_platform_id")
        if self.kind in {"item", "material"} and not self.platform_id:
            raise ValueError(f"scope {self.kind!r} needs platform_id")
        return self

    def key(self) -> str:
        """Queueing-lock key: identical scopes share one job."""
        return ":".join([self.kind, self.course_platform_id or "", self.platform_id or ""])


class ConnectorContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: UUID
    platform: Platform
    secret: SecretStr  # Canvas token or Playwright storage_state JSON
    last_success_at: datetime | None = None
    clock: Any  # app.core.clock.Clock (a Protocol; pydantic can't isinstance-check it)
    # Filled by the connector during fetch: (course_platform_id, table) pairs it could NOT list
    # completely (windowed listings, hidden tabs). Full-scope removal skips them (S10 rule 5).
    # table is one of "item_sources", "materials", "posts".
    incomplete: set[tuple[str, str]] = Field(default_factory=set)


class AccountInfo(BaseModel):
    account_label: str | None = None
    platform_user_id: str | None = None
    expires_at: datetime | None = None


class DownloadRef(BaseModel):
    """Where S12 downloads the file; credentials are added by the worker at download time."""

    url: str
    size_bytes: int | None = None
    filename: str | None = None


class TranscriptCue(BaseModel):
    start_s: int
    end_s: int
    text: str


class NCourse(BaseModel):
    record: Literal["course"] = "course"
    platform_id: str
    name: str
    code: str | None = None
    term: str | None = None
    source_url: str


class NItem(BaseModel):
    record: Literal["item"] = "item"
    platform_id: str
    course_platform_id: str
    type: ItemType = "other"
    title: str
    description: str | None = None
    due_at: datetime | None = None
    points: float | None = None
    source_url: str
    source_updated_at: datetime | None = None
    raw: dict[str, Any] = {}


class NMaterial(BaseModel):
    record: Literal["material"] = "material"
    platform_id: str
    course_platform_id: str
    kind: MaterialKind
    title: str
    mime_type: str | None = None
    download: DownloadRef | None = None
    text: str | None = None
    cues: list[TranscriptCue] | None = None
    recorded_at: datetime | None = None
    source_url: str
    source_updated_at: datetime | None = None


class NPost(BaseModel):
    record: Literal["post"] = "post"
    platform_id: str
    course_platform_id: str
    kind: PostKind
    title: str
    body: str
    author: str | None = None
    posted_at: datetime
    source_url: str
    source_updated_at: datetime | None = None


NormalizedRecord = NCourse | NItem | NMaterial | NPost


class Connector(Protocol):
    platform: Platform

    async def validate(self, ctx: ConnectorContext) -> AccountInfo:
        """Raises AuthExpired when the token/session is invalid."""
        ...

    def fetch(self, ctx: ConnectorContext, scope: SyncScope) -> AsyncIterator[NormalizedRecord]:
        """Yields normalized records. Raises AuthExpired / PlatformError."""
        ...


_REGISTRY: dict[str, Connector] = {}


def register_connector(connector: Connector) -> None:
    _REGISTRY[connector.platform] = connector


def get_connector(platform: str) -> Connector:
    if platform not in _REGISTRY:
        raise LookupError(f"no connector registered for {platform!r}")
    return _REGISTRY[platform]
