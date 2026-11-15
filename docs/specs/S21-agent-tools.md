# S21 — Agent tools

| | |
|---|---|
| **Status** | In progress (Hari): six read tools on mock data AND the DB (`DbToolData`, hybrid search); only seed-quality checks of hybrid vs vector-only remain |
| **Stage** | 1 (read tools + `fetch_latest`); `create_study_set` in S24, `add_study_block` in S25 |
| **Role** | B |
| **Depends on** | S01, S03, S20 (and S10 for `fetch_latest`) |
| **Folders** | `backend/app/agent/tools/` |

## Purpose
The functions the model can call. They read **our database only**, are scoped to the authenticated student, return small structured results with chunk IDs for citation, and report **coverage and freshness** so the agent knows when to call `fetch_latest`. Design rules: [03](../03-architecture.md#agent-and-tools).

## Inputs
- Tool arguments (Pydantic models below) chosen by the model.
- `RunCtx` (passed by the harness, never by the model): `user_id`, `timezone`, `clock`, `conn`, `allowed_chunk_ids: set[int]` (collector), `status_emitter`.

## Outputs
Every tool returns a `ToolResult` JSON envelope:
```json
{
  "results": [ ... ],
  "coverage": {
    "searched": ["canvas", "gradescope", "echo360"],
    "not_connected": ["piazza"],
    "needs_reconnect": [],
    "freshness": {"canvas": "12 minutes ago", "echo360": "3 days ago"},
    "stale": ["echo360"]
  },
  "truncated": false,
  "note": "optional hint, e.g. 'No results. Consider fetch_latest(course=...)'"
}
```

## Tools

| Tool | Arguments | Returns (`results` items) |
|---|---|---|
| `get_items` | `course: str \| None`, `type: ItemType \| None`, `from_date: date \| None`, `to_date: date \| None`, `include_past: bool = False` | `{item_id, course, type, title, due_local, due_in, points, status, changed_fields, sources: [platform]}` sorted by due date; max 50 |
| `get_changes` | `since_days: int = 7`, `course: str \| None` | `{course, entity, field, old, new, detected_local, summary}`; max 30 |
| `search_materials` | `query: str`, `course: str \| None`, `kind: Literal["slides","transcript","post","syllabus","any"] = "any"`, `source: Platform \| None`, `k: int = 8 (max 12)` | `{chunk_id, course, title, kind, page \| time, text, posted_or_recorded_local}` |
| `get_material` | `material_id: str`, `pages: str \| None` (e.g. `"10-20"`), `start_s: int \| None`, `end_s: int \| None` | `{chunk_id, page \| time, text}` for that range; max 20 pages / 20 minutes |
| `get_course_overview` | `course: str` | `{course_id, code, name, term, platforms, syllabus_chunks: [{chunk_id, text}], upcoming: [item summaries], counts}` |
| `fetch_latest` | `course: str \| None`, `source: Platform \| None`, `what: Literal["course","everything"] = "course"` | `{status: "completed" \| "running" \| "failed" \| "needs_reconnect" \| "not_connected", added, updated, sync_run_ids}` |
| `create_study_set` | see S24 | |
| `add_study_block` | see S25 | |

**`course` argument resolver:** accepts a course UUID, code (`"CS 311"`, `"COMPSCI 311"`), or name fragment; resolves via S16's normalization against the student's courses. Ambiguous/unknown → tool returns `results: []` and `note: "Unknown course 'X'. Known: COMPSCI 311, MATH 235, ..."`. (Lets weaker models pass human-readable names.)

## Behavior and rules
1. **Scoping:** every query filters by `ctx.user_id`. Tools never accept `user_id` as an argument.
2. **Search = hybrid:** vector top 30 (cosine on `embedding`, `is_current=true`) + full-text top 30 (`tsv`, `websearch_to_tsquery`) → Reciprocal Rank Fusion (k=60) → top `k`. Filters applied in both queries.
3. **Chunk ID collection:** every `chunk_id` returned by any tool is added to `ctx.allowed_chunk_ids`. Citations not in this set are dropped (S23).
4. **Untrusted wrapping:** text from posts (announcements, Piazza, email) is returned as `<untrusted source="piazza">…</untrusted>`; slide/transcript text as plain text. The system prompt (S22) explains this.
5. **Times** are returned as local strings in the student's timezone plus relative (`"in 6 days"`), so the model never does timezone math.
6. **Freshness:** `coverage` computed from `connections` + latest `sync_runs`. `stale` = older than 2× the platform's schedule interval.
7. **`fetch_latest`:** maps args to a `SyncScope`, calls `enqueue_sync(..., trigger="agent")` for each relevant connected platform, then `wait_for_sync(timeout_s=15)`. If still running, returns `status="running"` and the harness lets the run continue (the job finishes in the background). `needs_reconnect` / `not_connected` returned without enqueueing.
8. **Misses:** if `search_materials` returns 0 results (or all below a similarity floor of 0.2), insert a `misses` row and set `note` to suggest `fetch_latest`.
9. **Size limits:** each tool result ≤ ~6,000 tokens; truncate texts and set `truncated=true`.
10. **Status labels** (for SSE `status` events): each tool defines a human label from its args, e.g. `get_items(course="CS 311", type="exam")` → "Checking your CS 311 exams…".
11. Arguments validated by Pydantic; invalid args return a readable error string to the model (the SDK feeds it back), not an exception.
12. **Framework-agnostic:** tools are plain `async def tool(ctx: RunCtx, args: XArgs) -> ToolResult`; a thin adapter registers them with the Agents SDK (`function_tool`). Tests call the plain functions.

## Example
`search_materials(query="memoization", course="CS 311", k=2)` →
```json
{"results": [
  {"chunk_id": 8812, "course": "COMPSCI 311", "title": "Lecture 7 slides", "kind": "slides", "page": 12,
   "text": "[COMPSCI 311 · Lecture 7 slides · p.12]\nMemoization stores solutions to subproblems..."},
  {"chunk_id": 9930, "course": "COMPSCI 311", "title": "Lecture Nov 11", "kind": "transcript", "time": "23:41",
   "text": "...so when we memoize, we're trading memory for time..."}],
 "coverage": {"searched": ["canvas","echo360"], "not_connected": ["piazza"], "needs_reconnect": [],
              "freshness": {"canvas": "12 minutes ago", "echo360": "3 days ago"}, "stale": ["echo360"]},
 "truncated": false}
```

## Acceptance criteria
- [ ] All read tools return correct data against seed (S03)
- [ ] No tool can return another user's data (tested)
- [ ] Hybrid search beats vector-only on the seed relevance cases
- [ ] `fetch_latest` works end to end with a fake connector (S10)

## Test plan
| ID | Test | Type |
|---|---|---|
| S21-T01 | Course resolver: UUID, "CS 311", "COMPSCI 311", "algorithms" all resolve; unknown → helpful note | unit |
| S21-T02 | `get_items` filters by course/type/date and sorts by due; past excluded by default | integration |
| S21-T03 | `get_items` returns local times + relative strings in profile timezone | integration |
| S21-T04 | `get_changes` returns the seeded "Midterm moved" change | integration |
| S21-T05 | `search_materials` hybrid: keyword-only match found (FTS) and paraphrase found (vector) | integration |
| S21-T06 | `search_materials` excludes non-current chunks | integration |
| S21-T07 | Every returned chunk_id is added to `allowed_chunk_ids` | unit |
| S21-T08 | Post text is wrapped in `<untrusted>`; slide text is not | unit |
| S21-T09 | User isolation: tools with user B's ctx never return user A's rows | integration |
| S21-T10 | Zero results → `misses` row + fetch_latest hint | integration |
| S21-T11 | `fetch_latest`: completed within timeout; running after timeout; needs_reconnect without enqueue | integration |
| S21-T12 | Coverage marks stale/needs_reconnect/not_connected correctly | unit |
| S21-T13 | Oversized results are truncated with `truncated=true` | unit |
| S21-T14 | Invalid args return an error string, not an exception | unit |
| S21-T15 | Status label generation for each tool | unit |

## Out of scope
Grades tool (stretch), write tools other than S24/S25, web search.

## Implementation notes (2026-11-14, Hari)
Built so far (`backend/app/agent/tools/`, tests in `tests/unit/test_s21_tools.py`), none of it needs the DB:
- `args.py`: Pydantic argument models for the six read tools, `extra="forbid"` (the model can't pass `user_id`), `k ≤ 12`, page/time ranges capped at 20 pages / 20 minutes.
- `context.py`: `RunCtx`. `runner.py`: `ToolSpec` + `invoke(spec, ctx, raw_json) -> str`, matching the Agents SDK's `on_invoke_tool` shape so S22 only needs a thin adapter. Invalid JSON/args → `"Invalid arguments for <tool>: …"`. A crashing tool → a short retry hint with no internals. Each result is truncated, then its chunk IDs are added to `ctx.allowed_chunk_ids`.
- `courses.py`: course resolver (UUID, code with aliases, bare number like `"311"`, name fragment; ambiguous → "Which one?" note). The code normalizer lives in **`app/core/courses.py`** so S16 can reuse it instead of writing a second copy (heads-up to Neal).
- `coverage.py`: `compute_coverage(connections, now, source)`. `needs_reconnect`/`error` platforms are still searched (their older data is still there) and flagged. Stale = older than 2× the S10 schedule (Piazza assumed hourly). Never synced → `"never"` + stale.
- `results.py`: `ToolResult`, recursive chunk-ID collection, `wrap_untrusted` (escapes any `<untrusted`/`</untrusted` inside the text so a post can't close the wrapper), `wrap_post_text` (announcement → `canvas`, piazza, email), `truncate_result` (~6,000 tokens estimated as 24,000 characters; no tiktoken dependency; shortens long `text` fields, then drops the lowest-ranked results).
- `timefmt.py`: `local_time` ("Thu Nov 19, 7:00 PM"), `relative_time` ("in 6 days"), `ago`. `labels.py`: plain-language status labels (no "sync").

**Read tools** (`read.py`, registry `READ_TOOLS` in `tools/__init__.py`): all six tools are implemented against a `ToolData` interface (`data.py`), one student's data. `MockToolData` (`mock_source.py`, keyword search) backs them until S01. Tests on mock data: `tests/unit/test_s21_read_tools.py`. Arg models also treat `null` as "not given" (Gemini sends nulls).

**DB (done 2026-11-14):** `DbToolData` (`tools/db_source.py`) + `app/db/repositories/agent.py`: user-scoped SQL, hybrid search (vector top 30 with a 0.2 similarity floor + full-text top 30 → RRF k=60), misses rows, `fetch_latest` via S10 `enqueue_sync(trigger="agent")` + `wait_for_sync(15 s)`. Integration tests on a freshly seeded student: `tests/integration/test_s21_s22_db.py` (T02–T06, T09–T11). Turned on with `DATA_SOURCE=db`.

**Old next list (kept for history):** `DbToolData` (SQL: hybrid search with RRF, misses rows, user scoping), `fetch_latest` via S10's `enqueue_sync`/`wait_for_sync`, and the seed-based integration versions of T02, T04–T06, T09–T11.
