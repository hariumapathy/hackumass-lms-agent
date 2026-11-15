# S36 — Sessions (chats with their study sets) + rename/delete

| | |
|---|---|
| **Status** | In progress (Hari's Session A, 2026-11-15) |
| **Stage** | 3 |
| **Role** | B + C |
| **Depends on** | S22, S24, S33, S35 |
| **Folders** | `backend/app/api/routes/chat.py`, `backend/app/agent/store.py`, `db_store.py`, `backend/app/db/repositories/chat.py`, `apps/web/src/app/(app)/sessions`, `apps/web/src/components/chat`, `components/study`, `components/layout/app-shell.tsx` |

## Purpose
The Study tab becomes **Sessions**: one row per chat conversation (title, last updated) with the flashcards / quiz / plan made in it attached as chips. Students can rename and delete chats; deleting a chat keeps its study sets.

## Interface (small, additive contract change; Hari approved in the session prompt)
```text
GET    /conversations            -> ConversationSummary[]   (+ study_sets: StudySetSummary[], default [])
PATCH  /conversations/{id}       {title: str 1..80}  -> ConversationSummary   404 if not yours
DELETE /conversations/{id}       -> 204; messages cascade; study_sets.conversation_id -> null   404 if not yours
GET    /study-sets               StudySetSummary (+ conversation_id: uuid | null)
```
`ChatStore.save_study_set(user_id, study_set, conversation_id)`, `rename_conversation(user_id, id, title) -> ConversationSummary | None`, `delete_conversation(user_id, id) -> bool`. The runtime passes the run's conversation id when saving.

## Behavior and rules
1. Every query is scoped to `user_id`; someone else's id is a 404 (same as unknown).
2. Title is trimmed; empty after trim → 422.
3. Scripted mode (no runtime/store): the demo conversation can be renamed (not persisted) / deleted (204); any other id is 404.
4. UI: sidebar + phone tab "Sessions" → `/sessions`. Row: title, "Updated …", chips (Flashcards/Quiz/Plan) linking to `/study/[id]`; the row opens `/chat/[id]`. A "..." menu: Rename (inline input, Enter saves, Esc cancels), Delete (confirm: "Delete this chat? Its flashcards and quizzes stay in Sessions."). A "New chat" button. Study sets with no chat appear under "Saved study sets".
5. `/study`, `/study/[id]`, `/chat`, `/chat/[id]` keep working (`/study` redirects to `/sessions`).

## Test plan
| ID | Test | Type |
|---|---|---|
| S36-T01 | Runtime saves a study set with the run's conversation_id; GET /conversations lists it under that conversation | runtime |
| S36-T02 | PATCH renames (trimmed), 404 for another user's / unknown id, 422 for blank | runtime (memory store) |
| S36-T03 | DELETE removes the conversation; study set stays with conversation_id null; 404 for other user | runtime (memory store) |
| S36-T04 | DbChatStore: save with conversation_id, list with study_sets, rename, delete cascades messages + sets null, user isolation | integration (local DB) |
| S36-T05 | Sessions page lists conversations with chips, empty state, saved study sets section | component |
| S36-T06 | Rename inline (Enter saves, Esc cancels) and Delete via confirm dialog | component |
| S36-T07 | Nav shows "Sessions" (no "Study") on sidebar + phone tabs | component |

## Out of scope
Search across sessions, pinning, sharing.
