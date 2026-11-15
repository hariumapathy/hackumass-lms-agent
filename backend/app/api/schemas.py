"""S02 API contract: request/response models and SSE chat events.

Frontend TS types are generated from FastAPI's OpenAPI schema (`make types`).
SSE events are documented in app/api/CONTRACT.md. Changing anything here is a
contract change (see AGENTS.md).
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Platform = Literal["canvas", "gradescope", "echo360", "piazza"]
ConnectionStatus = Literal["active", "needs_reconnect", "error", "disconnected"]
RecordStatus = Literal["active", "changed", "removed"]
ItemType = Literal["assignment", "exam", "quiz", "lab", "project", "other"]
PostKind = Literal["announcement", "piazza", "email"]
MaterialKind = Literal["file", "page", "syllabus", "transcript"]
ProcessingStatus = Literal["pending", "processing", "done", "failed", "skipped"]
StudySetType = Literal["plan", "quiz", "flashcards"]
StudyBlockStatus = Literal["proposed", "approved", "declined"]
CitationStatus = Literal["current", "changed", "removed", "locked"]


# ---------- errors ----------
class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------- account ----------
class Connection(BaseModel):
    platform: Platform
    status: ConnectionStatus
    expires_at: datetime | None = None
    last_sync_at: datetime | None = None
    last_error: str | None = None
    account_label: str | None = None


class Me(BaseModel):
    user_id: UUID
    display_name: str | None = None
    timezone: str
    model_choice: str | None = None
    connections: list[Connection]


class MePatch(BaseModel):
    timezone: str | None = None
    model_choice: str | None = None
    display_name: str | None = Field(default=None, max_length=80)


class ModelOption(BaseModel):
    id: str
    label: str
    provider: str
    tier: Literal["recommended", "experimental"]
    available: bool


class ModelsResponse(BaseModel):
    models: list[ModelOption]
    default: str


# ---------- connections and sync ----------
class CanvasConnectRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    expires_at: datetime | None = None


class LoginStartResponse(BaseModel):
    login_id: UUID
    mode: Literal["local", "hosted"]
    live_view_url: str | None = None


class LoginStatusResponse(BaseModel):
    state: Literal["pending", "succeeded", "failed", "expired"]
    error: str | None = None


class SyncRequest(BaseModel):
    platform: Platform | None = None
    course_id: UUID | None = None


class SyncStartResponse(BaseModel):
    sync_run_ids: list[UUID]


class SourceStatus(BaseModel):
    platform: Platform
    connection_status: ConnectionStatus
    last_sync_at: datetime | None = None
    running: bool = False
    stale: bool = False


class SyncStatusResponse(BaseModel):
    sources: list[SourceStatus]


# ---------- courses, items, posts, changes ----------
class SourceRef(BaseModel):
    platform: Platform
    source_url: str
    last_synced_at: datetime


class Item(BaseModel):
    id: UUID
    course_id: UUID
    course_code: str
    type: ItemType
    title: str
    due_at: datetime | None = None
    points: float | None = None
    status: RecordStatus
    sources: list[SourceRef]
    changed_fields: list[str] = []
    submitted: bool = False  # any live source says the student handed it in (never Overdue)


class Post(BaseModel):
    id: UUID
    course_id: UUID
    kind: PostKind
    title: str
    excerpt: str
    posted_at: datetime
    source_url: str
    status: RecordStatus


class Change(BaseModel):
    id: UUID
    entity_type: Literal["item", "post", "material"]
    entity_id: UUID
    course_code: str
    field: str
    old_value: Any = None
    new_value: Any = None
    detected_at: datetime
    seen: bool
    summary: str


class ChangesSeenRequest(BaseModel):
    ids: list[UUID]


class MaterialSummary(BaseModel):
    id: UUID
    title: str
    kind: MaterialKind
    processing_status: ProcessingStatus
    source_url: str


class CourseSummary(BaseModel):
    id: UUID
    code: str
    name: str
    term: str | None = None
    color: str | None = None
    upcoming_count: int
    platforms: list[Platform]


class CourseDetail(CourseSummary):
    items: list[Item]
    recent_posts: list[Post]
    materials: list[MaterialSummary]
    syllabus_excerpt: str | None = None


class Today(BaseModel):
    date: date
    timezone: str
    overdue: list[Item]
    due_today: list[Item]
    due_this_week: list[Item]
    upcoming_exams: list[Item]
    changes: list[Change]
    new_posts: list[Post]
    sources: list[SourceStatus]


# ---------- citations, chat, study ----------
class Citation(BaseModel):
    chunk_id: int
    title: str
    kind: str
    platform: Platform
    course_code: str
    page: int | None = None
    start_s: int | None = None
    end_s: int | None = None
    url: str
    deep_link: str
    quote: str
    last_synced_at: datetime
    status: CitationStatus
    file_id: UUID | None = None  # stored PDF: open in the app via GET /files/{file_id}#page=N


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


class Message(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    text: str
    citations: list[Citation] = []
    study_set_ids: list[UUID] = []
    block_ids: list[UUID] = []
    created_at: datetime


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    updated_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    messages: list[Message]


class StudySetSummary(BaseModel):
    id: UUID
    type: StudySetType
    title: str
    course_id: UUID | None = None
    created_at: datetime


class StudySet(StudySetSummary):
    payload: dict[str, Any]  # schema per type: S24


class StudyBlock(BaseModel):
    id: UUID
    title: str
    start_at: datetime
    end_at: datetime
    course_id: UUID | None = None
    item_id: UUID | None = None
    status: StudyBlockStatus


class StudyBlockDecision(BaseModel):
    block_ids: list[UUID] = Field(min_length=1)
    approve: bool


class StudyBlocksResponse(BaseModel):
    blocks: list[StudyBlock]


class CalendarFeed(BaseModel):
    url: str


# ---------- SSE chat events (see CONTRACT.md) ----------
class RunStartedEvent(BaseModel):
    type: Literal["run_started"] = "run_started"
    run_id: UUID
    conversation_id: UUID
    user_message_id: UUID


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    id: str
    label: str
    state: Literal["started", "done", "failed"]
    tool: str


class TextEvent(BaseModel):
    type: Literal["text"] = "text"
    delta: str


class StudySetEvent(BaseModel):
    type: Literal["study_set"] = "study_set"
    study_set: StudySet


class ApprovalRequiredEvent(BaseModel):
    type: Literal["approval_required"] = "approval_required"
    blocks: list[StudyBlock]
    summary: str


class CitationsEvent(BaseModel):
    type: Literal["citations"] = "citations"
    citations: list[Citation]
    dropped: list[int] = []


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    run_id: UUID
    message_id: UUID
    final_text: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    retryable: bool = False


ChatEvent = Annotated[
    RunStartedEvent
    | StatusEvent
    | TextEvent
    | StudySetEvent
    | ApprovalRequiredEvent
    | CitationsEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]

EVENT_MODELS: dict[str, type[BaseModel]] = {
    m.model_fields["type"].default: m
    for m in (
        RunStartedEvent,
        StatusEvent,
        TextEvent,
        StudySetEvent,
        ApprovalRequiredEvent,
        CitationsEvent,
        DoneEvent,
        ErrorEvent,
    )
}
