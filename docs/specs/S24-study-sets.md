# S24 — Study sets (plans, quizzes, flashcards)

| | |
|---|---|
| **Status** | In progress (Hari): tool, validation, citation filter, SSE event, routes done (in-memory store); DB save waits for S01 |
| **Stage** | 2 |
| **Role** | B |
| **Depends on** | S22, S23 |
| **Folders** | `backend/app/agent/tools/study_sets.py`, `backend/app/api/routes/study_sets.py` |

## Purpose
Let the agent produce **structured** study material the UI renders as interactive cards, where every item is backed by validated citations. Implemented as a tool (`create_study_set`) rather than free-form JSON so it works across model providers (S26).

## Inputs
`create_study_set` arguments:
```python
class CreateStudySetArgs(BaseModel):
    type: Literal["plan", "quiz", "flashcards"]
    title: str                         # <= 80 chars
    course: str | None                 # resolved like S21
    exam_item_id: str | None           # optional link to the exam item
    plan: StudyPlan | None = None      # exactly one of plan/quiz/flashcards matches `type`
    quiz: Quiz | None = None
    flashcards: Flashcards | None = None

class StudyPlan(BaseModel):
    days: list[PlanDay]                # 1..14
class PlanDay(BaseModel):
    date: date; minutes: int           # 15..240
    topics: list[str]                  # 1..5
    tasks: list[PlanTask]              # 1..6
class PlanTask(BaseModel):
    text: str; chunk_ids: list[int]    # >= 1

class Quiz(BaseModel):
    questions: list[QuizQuestion]      # 3..15
class QuizQuestion(BaseModel):
    type: Literal["mcq", "short"]
    prompt: str
    choices: list[str] | None          # exactly 4 when mcq
    answer_index: int | None           # 0..3 when mcq
    answer_text: str | None            # when short
    explanation: str
    chunk_ids: list[int]               # >= 1

class Flashcards(BaseModel):
    cards: list[Card]                  # 5..40
class Card(BaseModel):
    front: str; back: str; chunk_ids: list[int]   # >= 1
```

## Outputs
- Tool returns `{study_set_id, type, title, counts}` (small; the model doesn't need the payload back).
- `study_sets` row with `payload` = validated model + resolved `citations` map `{chunk_id: Citation}`.
- SSE `study_set` event (via S22) with the full `StudySet`.
- `GET /study-sets`, `GET /study-sets/{id}`.

## Behavior and rules
1. Pydantic validation of shape and bounds; errors returned to the model as a readable message listing the problems (the model retries; max 2 attempts, then the tool returns failure and the agent explains).
2. Every `chunk_ids` list is validated with S23 `validate_ids` against `allowed_chunk_ids`. Items left with **zero** valid IDs are removed; if more than 30% of items are removed, the tool returns an error asking the model to search and cite properly.
3. Plan dates must be between today and the exam date (if `exam_item_id`), in the student's timezone; out-of-range days are rejected.
4. MCQ: `answer_index` within choices; choices unique.
5. Study sets are immutable once created (new request = new set).

## Example
"Make me 5 flashcards on DP" → `create_study_set(type="flashcards", title="CS 311 DP flashcards", course="CS 311", flashcards={cards:[{front:"What does memoization store?", back:"Solutions to subproblems…", chunk_ids:[8812]}, …]})` → `{study_set_id:"…", type:"flashcards", title:"…", counts:{cards:5}}`.

## Acceptance criteria
- [ ] Quiz, plan and flashcards generated from seed data via a real model render correctly (S33)
- [ ] No item without a valid citation is saved

## Test plan
| ID | Test | Type |
|---|---|---|
| S24-T01 | Valid payload for each type saves and returns summary | integration |
| S24-T02 | MCQ with 3 choices / bad answer_index rejected with readable error | unit |
| S24-T03 | Items with only invalid chunk IDs are removed | unit |
| S24-T04 | >30% items removed → tool error asking to cite | unit |
| S24-T05 | Plan dates outside today..exam rejected | unit |
| S24-T06 | Type/payload mismatch rejected | unit |
| S24-T07 | `study_set` SSE event emitted with resolved citations | runtime |
| S24-T08 | `GET /study-sets/{id}` returns only the caller's set | integration |

## Out of scope
Spaced repetition scheduling, quiz grading of free-text answers by AI (UI reveals answers; stretch: AI grading).

## Implementation notes (2026-11-14, Hari)
- `backend/app/agent/tools/study_sets.py` (tool + models), registered in `AGENT_TOOLS`; label "Making your flashcards…". Tests: `tests/unit/test_s24_study_sets.py` (T01–T08; T01/T08 run against the in-memory store).
- The tool puts the full `StudySet` in `RunCtx.study_sets`; the runtime emits `study_set` after the answer and saves it via the chat store. The model only gets `{study_set_id, type, title, counts, removed_uncited_items}`.
- Fixable problems (over 30% uncited items, plan dates out of range) raise `ToolRejected` → `"create_study_set rejected: …"` to the model. Shape errors → `"Invalid arguments …"`. Retries are bounded by `max_turns`.
- Nested argument schemas are flattened for Gemini (`$ref` inlined, no `anyOf` null, no titles).
- **Not yet:** saved payloads don't include a resolved `citations` map (the UI can call `GET /citations?ids=`); DB persistence after S01.
