"""Chat (SSE) and conversations (S02 stubs).

POST /chat streams a SCRIPTED event sequence that follows the S02 ordering guarantees, so the
frontend can be built before the real agent runtime (S22) exists.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
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


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of chat events (see CONTRACT.md)",
        }
    },
)
async def chat(body: s.ChatRequest, user: User, delay_ms: int = 0) -> StreamingResponse:
    conversation_id = body.conversation_id or uuid4()
    return StreamingResponse(
        _stream(conversation_id, min(delay_ms, 2000) / 1000),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _demo_conversation() -> s.ConversationDetail:
    now = datetime.now(UTC).replace(microsecond=0)
    return s.ConversationDetail(
        conversation=s.ConversationSummary(
            id=DEMO_CONVERSATION_ID,
            title="CS 311 midterm prep",
            updated_at=now - timedelta(hours=1),
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


@router.get("/conversations", response_model=list[s.ConversationSummary])
async def conversations(user: User) -> list[s.ConversationSummary]:
    return [_demo_conversation().conversation]


@router.get("/conversations/{conversation_id}", response_model=s.ConversationDetail)
async def conversation(conversation_id: UUID, user: User) -> s.ConversationDetail:
    if conversation_id != DEMO_CONVERSATION_ID:
        raise not_found("Conversation")
    return _demo_conversation()
