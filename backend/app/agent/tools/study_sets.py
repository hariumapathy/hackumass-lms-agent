"""`create_study_set` (S24): plans, quizzes and flashcards as validated structured data.

Every item must cite chunk IDs that tools returned in this run (S23 `validate_ids`); items left
without a valid citation are dropped, and if more than 30% are dropped the model is asked to
search and cite properly. The full set goes to `ctx.study_sets` (the runtime emits the
`study_set` SSE event and saves it); the model only gets a small summary back.
"""

from datetime import date, datetime
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agent.citations import validate_ids
from app.agent.tools.context import RunCtx
from app.agent.tools.courses import resolve_course
from app.agent.tools.results import ToolResult
from app.agent.tools.runner import ToolRejected
from app.api import schemas as s

MAX_DROPPED_SHARE = 0.30


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _nulls_mean_default(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None}
        return data


class PlanTask(_M):
    text: str = Field(min_length=1, max_length=300)
    chunk_ids: list[int] = Field(min_length=1)


class PlanDay(_M):
    date: date
    minutes: int = Field(ge=15, le=240)
    topics: list[str] = Field(min_length=1, max_length=5)
    tasks: list[PlanTask] = Field(min_length=1, max_length=6)


class StudyPlan(_M):
    days: list[PlanDay] = Field(min_length=1, max_length=14)


class QuizQuestion(_M):
    type: Literal["mcq", "short"]
    prompt: str = Field(min_length=1, max_length=500)
    choices: list[str] | None = None
    answer_index: int | None = None
    answer_text: str | None = None
    explanation: str = Field(min_length=1, max_length=800)
    chunk_ids: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def _answer_shape(self) -> "QuizQuestion":
        if self.type == "mcq":
            if not self.choices or len(self.choices) != 4:
                raise ValueError("mcq questions need exactly 4 choices")
            if len({c.strip().lower() for c in self.choices}) != 4:
                raise ValueError("mcq choices must be different")
            if self.answer_index is None or not 0 <= self.answer_index <= 3:
                raise ValueError("mcq answer_index must be 0, 1, 2 or 3")
        elif not self.answer_text:
            raise ValueError("short questions need answer_text")
        return self


class Quiz(_M):
    questions: list[QuizQuestion] = Field(min_length=3, max_length=15)


class Card(_M):
    front: str = Field(min_length=1, max_length=300)
    back: str = Field(min_length=1, max_length=600)
    chunk_ids: list[int] = Field(min_length=1)


class Flashcards(_M):
    cards: list[Card] = Field(min_length=5, max_length=40)


class CreateStudySetArgs(_M):
    type: Literal["plan", "quiz", "flashcards"]
    title: str = Field(min_length=1, max_length=80)
    course: str | None = None
    exam_item_id: str | None = None
    plan: StudyPlan | None = None
    quiz: Quiz | None = None
    flashcards: Flashcards | None = None

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _payload_matches_type(self) -> "CreateStudySetArgs":
        given = [k for k in ("plan", "quiz", "flashcards") if getattr(self, k) is not None]
        if given != [self.type]:
            raise ValueError(f"type is '{self.type}', so pass exactly one '{self.type}' payload")
        return self


def _items(args: CreateStudySetArgs) -> list[Any]:
    if args.plan:
        return [t for day in args.plan.days for t in day.tasks]
    if args.quiz:
        return list(args.quiz.questions)
    assert args.flashcards
    return list(args.flashcards.cards)


async def create_study_set(ctx: RunCtx, args: CreateStudySetArgs) -> ToolResult:
    items = _items(args)
    dropped_ids: set[int] = set()
    kept = 0
    for item in items:
        valid, dropped = validate_ids(item.chunk_ids, ctx.allowed_chunk_ids)
        item.chunk_ids = valid
        dropped_ids |= set(dropped)
        kept += bool(valid)
    removed = len(items) - kept
    if items and removed / len(items) > MAX_DROPPED_SHARE:
        raise StudySetRejected(
            f"{removed} of {len(items)} items cite sources you didn't get from search in this "
            "chat. Call search_materials first, then cite only the chunk_ids it returned."
        )

    today = ctx.clock.now().astimezone(ZoneInfo(ctx.timezone)).date()
    exam_date = await _exam_date(ctx, args.exam_item_id)
    if args.plan:
        for day in args.plan.days:
            day.tasks = [t for t in day.tasks if t.chunk_ids]
            if day.date < today or (exam_date and day.date > exam_date):
                last = exam_date.isoformat() if exam_date else "the future"
                raise StudySetRejected(
                    f"plan day {day.date} is outside {today.isoformat()}..{last}"
                )
        args.plan.days = [d for d in args.plan.days if d.tasks]
    elif args.quiz:
        args.quiz.questions = [q for q in args.quiz.questions if q.chunk_ids]
    elif args.flashcards:
        args.flashcards.cards = [c for c in args.flashcards.cards if c.chunk_ids]

    course_id = None
    if args.course and ctx.data is not None:
        course_id = resolve_course(await ctx.data.courses(), args.course).course
    payload = (args.plan or args.quiz or args.flashcards).model_dump(mode="json")  # type: ignore[union-attr]
    study_set = s.StudySet(
        id=uuid4(),
        type=args.type,
        title=args.title,
        course_id=course_id.id if course_id else None,
        created_at=ctx.clock.now(),
        payload=payload,
    )
    ctx.study_sets.append(study_set)
    counts = {k: len(v) for k, v in payload.items() if isinstance(v, list)}
    return ToolResult(
        results=[
            {
                "study_set_id": str(study_set.id),
                "type": args.type,
                "title": args.title,
                "counts": counts,
                "removed_uncited_items": removed,
            }
        ]
    )


class StudySetRejected(ToolRejected):
    """A problem the model can fix (uncited items, dates out of range)."""


async def _exam_date(ctx: RunCtx, exam_item_id: str | None) -> date | None:
    if not exam_item_id or ctx.data is None:
        return None
    for item in await ctx.data.items(None, None):
        if str(item.id) == exam_item_id and isinstance(item.due_at, datetime):
            return item.due_at.astimezone(ZoneInfo(ctx.timezone)).date()
    return None
