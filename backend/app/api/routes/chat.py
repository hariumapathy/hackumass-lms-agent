"""Chat (SSE) and conversations.

POST /chat runs the real agent (S22) when `app.state.chat_runtime` is set (a model key exists and
CHAT_MODE isn't "scripted"); otherwise it streams the SCRIPTED S02 sequence (frontend dev, tests
and the demo backup).
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, chat_rate_limit, current_user
from app.api.sse import sse_event
from app.core.errors import not_found

router = APIRouter(tags=["chat"])
User = Annotated[UserCtx, Depends(current_user)]

DEMO_CONVERSATION_ID = mock.mid("conversation/demo")
_TEXT = [
    "Midterm 1 is on **Thursday at 7 PM** (it moved 2 days later) ",
    "and covers material through dynamic programming, not graphs. ",
    "Memoization stores solutions to subproblems so each is solved once ",
    "[cite:chunk_8812]; in lecture it was described as trading memory for time ",
    "[cite:chunk_9930]. I made flashcards and proposed two study sessions.",
]


def scripted_events(conversation_id: UUID) -> list[s.ChatEvent]:
    run_id = uuid4()
    events: list[s.ChatEvent] = [
        s.RunStartedEvent(run_id=run_id, conversation_id=conversation_id, user_message_id=uuid4()),
        s.StatusEvent(
            id="t1", label="Checking your COMPSCI 311 exams…", state="started", tool="get_items"
        ),
        s.StatusEvent(
            id="t1", label="Checking your COMPSCI 311 exams…", state="done", tool="get_items"
        ),
        s.StatusEvent(
            id="t2",
            label="Searching slides and lectures…",
            state="started",
            tool="search_materials",
        ),
        s.StatusEvent(
            id="t2", label="Searching slides and lectures…", state="done", tool="search_materials"
        ),
    ]
    events += [s.TextEvent(delta=chunk) for chunk in _TEXT]
    events += [
        s.StudySetEvent(study_set=mock.study_set()),
        s.ApprovalRequiredEvent(
            blocks=mock.study_blocks(), summary="Add 2 study sessions for COMPSCI 311 Midterm 1?"
        ),
        s.CitationsEvent(citations=mock.citations([8812, 9930]), dropped=[]),
        s.DoneEvent(run_id=run_id, message_id=uuid4(), final_text="".join(_TEXT)),
    ]
    return events


async def _stream(conversation_id: UUID, delay_s: float) -> AsyncIterator[str]:
    for event in scripted_events(conversation_id):
        yield sse_event(event)
        if delay_s:
            await asyncio.sleep(delay_s)


async def _agent_stream(runtime, user: UserCtx, body: s.ChatRequest) -> AsyncIterator[str]:  # noqa: ANN001
    async for event in runtime.run(user, body):
        yield sse_event(event)


@router.post(
    "/chat",
    response_class=StreamingResponse,
    dependencies=[Depends(chat_rate_limit)],
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of chat events (see CONTRACT.md)",
        }
    },
)
async def chat(
    body: s.ChatRequest, user: User, request: Request, delay_ms: int = 0
) -> StreamingResponse:
    runtime = getattr(request.app.state, "chat_runtime", None)
    if runtime is not None:
        stream: AsyncIterator[str] = _agent_stream(runtime, user, body)
    else:
        stream = _stream(body.conversation_id or uuid4(), min(delay_ms, 2000) / 1000)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _demo_set_summary() -> s.StudySetSummary:
    st = mock.study_set()
    return s.StudySetSummary(
        **st.model_dump(exclude={"payload", "conversation_id"}),
        conversation_id=DEMO_CONVERSATION_ID,
    )


def _demo_conversation() -> s.ConversationDetail:
    now = datetime.now(UTC).replace(microsecond=0)
    return s.ConversationDetail(
        conversation=s.ConversationSummary(
            id=DEMO_CONVERSATION_ID,
            title="CS 311 midterm prep",
            updated_at=now - timedelta(hours=1),
            study_sets=[_demo_set_summary()],
        ),
        messages=[
            s.Message(
                id=mock.mid("message/u1"),
                role="user",
                text="Help me prep for my CS 311 midterm",
                created_at=now - timedelta(hours=1, minutes=1),
            ),
            s.Message(
                id=mock.mid("message/a1"),
                role="assistant",
                text="".join(_TEXT),
                citations=mock.citations([8812, 9930]),
                study_set_ids=[mock.study_set().id],
                block_ids=[b.id for b in mock.study_blocks()],
                created_at=now - timedelta(hours=1),
            ),
        ],
    )


def _store(request: Request):  # noqa: ANN202
    runtime = getattr(request.app.state, "chat_runtime", None)
    return runtime.store if runtime is not None else None


@router.get("/conversations", response_model=list[s.ConversationSummary])
async def conversations(user: User, request: Request) -> list[s.ConversationSummary]:
    store = _store(request)
    if store is None:
        return [_demo_conversation().conversation]
    return await store.conversations(user.user_id)


@router.get("/conversations/{conversation_id}", response_model=s.ConversationDetail)
async def conversation(conversation_id: UUID, user: User, request: Request) -> s.ConversationDetail:
    store = _store(request)
    if store is None:
        if conversation_id != DEMO_CONVERSATION_ID:
            raise not_found("Conversation")
        return _demo_conversation()
    detail = await store.conversation(user.user_id, conversation_id)
    if detail is None:
        raise not_found("Conversation")
    return detail


@router.patch("/conversations/{conversation_id}", response_model=s.ConversationSummary)
async def rename_conversation(
    conversation_id: UUID, body: s.ConversationRename, user: User, request: Request
) -> s.ConversationSummary:
    """S36: rename a chat (user-scoped; someone else's id is a 404)."""
    store = _store(request)
    if store is None:
        if conversation_id != DEMO_CONVERSATION_ID:
            raise not_found("Conversation")
        return _demo_conversation().conversation.model_copy(update={"title": body.title})
    renamed = await store.rename_conversation(user.user_id, conversation_id, body.title)
    if renamed is None:
        raise not_found("Conversation")
    return renamed


@router.delete("/conversations/{conversation_id}", status_code=204, response_class=Response)
async def delete_conversation(conversation_id: UUID, user: User, request: Request) -> Response:
    """S36: delete a chat and its messages; its study sets stay (conversation_id -> null)."""
    store = _store(request)
    if store is None:
        if conversation_id != DEMO_CONVERSATION_ID:
            raise not_found("Conversation")
        return Response(status_code=204)
    if not await store.delete_conversation(user.user_id, conversation_id):
        raise not_found("Conversation")
    return Response(status_code=204)
