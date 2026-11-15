# API contract: chat stream (SSE)

Spec: [docs/specs/S02-api-contract.md](../../../docs/specs/S02-api-contract.md). REST endpoints and their JSON types are described by FastAPI's OpenAPI schema (`/docs`, and `make types` → `apps/web/src/lib/api/schema.d.ts`). OpenAPI can't describe SSE, so this file is the source of truth for the chat stream. Event models live in `app/api/schemas.py` (`*Event`, `EVENT_MODELS`). **Changing anything here is a contract change** (team agreement required, see AGENTS.md).

## Request
`POST /chat` with `Authorization: Bearer <Supabase access token>` and JSON `{"conversation_id"?: uuid, "message": string (1..4000)}`.

Response: `200 text/event-stream`. Errors before the stream starts (401, 422, 429) use the normal JSON error envelope.

Stub only: `?delay_ms=<0..2000>` adds a delay between events so the UI can show streaming. The real runtime (S22) ignores it.

## Framing
Each event is one SSE frame:
```
event: <type>
data: <JSON object, single line>

```
- `data` never repeats `type`.
- Read the stream with `fetch` + a stream parser (not `EventSource`, which can't POST or send headers).
- Frames may arrive split across network chunks; buffer until a blank line.
- **Ignore unknown event types** (forward compatible).

## Events

| `event:` | `data` fields | When |
|---|---|---|
| `run_started` | `run_id` uuid, `conversation_id` uuid, `user_message_id` uuid | First event, always |
| `status` | `id` string (pairs started/done for one tool call), `label` human text, `state` `"started"\|"done"\|"failed"`, `tool` tool name | A tool starts or finishes |
| `text` | `delta` string | Answer text as it streams. May contain `[cite:chunk_<id>]` markers; render them as placeholders until `citations` arrives |
| `study_set` | `study_set` `StudySet` (`id, type, title, course_id?, created_at, payload`) | A study set was created and saved (payload schema: S24) |
| `approval_required` | `blocks` `StudyBlock[]` (status `proposed`), `summary` string | The agent proposed study blocks; show Add / Skip → `POST /study-blocks/decision` |
| `citations` | `citations` `Citation[]`, `dropped` int[] | After the last `text`: validated, resolved citations. Replace markers with chips; remove markers whose IDs are in `dropped` or missing |
| `done` | `run_id` uuid, `message_id` uuid, `final_text` string | Last event on success. `final_text` (invalid markers removed) is authoritative |
| `error` | `code` string, `message` string, `retryable` bool | Last event on failure. Keep partial text visible; offer Retry if `retryable` |

`Citation`: `chunk_id` int, `title`, `kind`, `platform`, `course_code`, `page?`, `start_s?`, `end_s?`, `url`, `deep_link`, `quote`, `last_synced_at`, `status` (`current|changed|removed|locked`), `file_id?` (2026-11-15: set when we hold the original PDF; the app shows it in its own viewer via REST `GET /files/{file_id}` with the student's Bearer token, opened at `#page=N`).

## Ordering guarantees
1. `run_started` is first.
2. `status` events for a tool: `started` before `done`/`failed` (same `id`).
3. `study_set` and `approval_required` come after the last `text`, before `citations`.
4. `citations` comes after the last `text`.
5. **Exactly one terminal event**, `done` or `error`, and it is the last event.

## Example
```
event: run_started
data: {"run_id":"…","conversation_id":"…","user_message_id":"…"}

event: status
data: {"id":"t1","label":"Checking your COMPSCI 311 exams…","state":"started","tool":"get_items"}

event: status
data: {"id":"t1","label":"Checking your COMPSCI 311 exams…","state":"done","tool":"get_items"}

event: text
data: {"delta":"Memoization stores solutions to subproblems [cite:chunk_8812]."}

event: citations
data: {"citations":[{"chunk_id":8812,"title":"Lecture 7 slides","page":12,"url":"…","status":"current", "…":"…"}],"dropped":[]}

event: done
data: {"run_id":"…","message_id":"…","final_text":"Memoization stores solutions to subproblems [cite:chunk_8812]."}

```
