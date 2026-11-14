"""Study sets and study-block decisions (S02 stubs; real logic in S24, S25)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user
from app.core.errors import not_found

router = APIRouter(tags=["study"])
User = Annotated[UserCtx, Depends(current_user)]


@router.get("/study-sets", response_model=list[s.StudySetSummary])
async def study_sets(user: User, course_id: UUID | None = None) -> list[s.StudySetSummary]:
    sets = [mock.study_set()]
    if course_id:
        sets = [x for x in sets if x.course_id == course_id]
    return [s.StudySetSummary(**x.model_dump(exclude={"payload"})) for x in sets]


@router.get("/study-sets/{study_set_id}", response_model=s.StudySet)
async def study_set(study_set_id: UUID, user: User) -> s.StudySet:
    found = mock.study_set()
    if found.id != study_set_id:
        raise not_found("Study set")
    return found


@router.post("/study-blocks/decision", response_model=s.StudyBlocksResponse)
async def decide_blocks(body: s.StudyBlockDecision, user: User) -> s.StudyBlocksResponse:
    status: s.StudyBlockStatus = "approved" if body.approve else "declined"
    wanted = set(body.block_ids)
    blocks = [
        b.model_copy(update={"status": status}) for b in mock.study_blocks() if b.id in wanted
    ]
    return s.StudyBlocksResponse(blocks=blocks)
