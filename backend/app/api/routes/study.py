"""Study sets (S24) and study-block decisions (S25). In agent mode they read the chat store;
in scripted mode (no model key) they return the S02 mock data."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.core.errors import not_found

router = APIRouter(tags=["study"])
User = Annotated[UserCtx, Depends(current_user)]


def _store(request: Request):  # noqa: ANN202
    runtime = getattr(request.app.state, "chat_runtime", None)
    return runtime.store if runtime is not None else None


async def _sets(request: Request, user: UserCtx) -> list[s.StudySet]:
    store = _store(request)
    return [mock.study_set()] if store is None else await store.study_sets(user.user_id)


@router.get("/study-sets", response_model=list[s.StudySetSummary])
async def study_sets(
    user: User, request: Request, course_id: UUID | None = None
) -> list[s.StudySetSummary]:
    sets = await _sets(request, user)
    if course_id:
        sets = [x for x in sets if x.course_id == course_id]
    return [s.StudySetSummary(**x.model_dump(exclude={"payload"})) for x in sets]


@router.get("/study-sets/{study_set_id}", response_model=s.StudySet)
async def study_set(study_set_id: UUID, user: User, request: Request) -> s.StudySet:
    found = next((x for x in await _sets(request, user) if x.id == study_set_id), None)
    if found is None:
        raise not_found("Study set")
    return found


@router.post("/study-blocks/decision", response_model=s.StudyBlocksResponse)
async def decide_blocks(
    body: s.StudyBlockDecision, user: User, request: Request
) -> s.StudyBlocksResponse:
    from app.core.settings import get_settings
    from app.db.pool import connection
    from app.db.repositories.calendar import decide

    if get_settings().data_source == "db":
        async with connection() as conn:
            return s.StudyBlocksResponse(
                blocks=await decide(
                    conn, user.user_id, body.block_ids, body.approve, request.app.state.clock.now()
                )
            )
    status: s.StudyBlockStatus = "approved" if body.approve else "declined"
    wanted = set(body.block_ids)
    blocks = [
        b.model_copy(update={"status": status}) for b in mock.study_blocks() if b.id in wanted
    ]
    return s.StudyBlocksResponse(blocks=blocks)
