# S33 — Chat and study UI

| | |
|---|---|
| **Status** | In progress (Soumith): chat + study cards + approvals + study pages built in mock mode (Claude + Codex); S33-T01–T13 green |
| **Stage** | 1 (chat + citations), 2 (study cards + approvals) |
| **Role** | C |
| **Depends on** | S30; S22/S23 (chat), S24 (study sets), S25 (approvals) |
| **Folders** | `apps/web/src/app/chat/`, `apps/web/src/app/study/`, `apps/web/src/components/chat/`, `apps/web/src/components/study/` |

## Purpose
The conversational interface: send a message, watch progress and the answer stream in, see verified citation chips, interact with study sets (plan, quiz, flashcards), and approve or skip proposed study blocks.

## Inputs
- SSE events from `POST /chat` (S02).
- `GET /conversations`, `GET /conversations/{id}`, `GET /study-sets/{id}`, `POST /study-blocks/decision`.

## Outputs (screen states)
```
User: Help me prep for my CS 311 midterm
  ✓ Checking your CS 311 exams…
  ✓ Reading the syllabus and Piazza…
  ⟳ Pulling Tuesday's lecture from Echo360…
Assistant: Midterm 1 is Thu Nov 20, 7 PM ⚠ moved from Nov 18 [Canvas announcement] [Piazza @412] ...
  ┌ Study plan · 5 days ┐  ┌ Practice quiz · 10 Qs ┐  ┌ Flashcards · 20 ┐   (open → /study/[id])
  ┌ Add 5 study sessions to your calendar?  Fri 4–5 PM … [Add] [Skip] ┐
```

## Behavior and rules
**Chat**
1. Send: Enter (Shift+Enter for newline); disabled while a run is active; "Stop" aborts the stream.
2. `status` events render as a compact checklist (started → spinner, done → check, failed → warning); collapses after `done`.
3. `text` deltas append to the assistant bubble (markdown rendered: lists, bold, code). While streaming, `[cite:chunk_N]` markers render as small placeholder dots.
4. On `citations`: markers become numbered chips `[1]`, `[2]`; dropped markers disappear. Chip hover/tap opens a **citation card**: title, course, page or timestamp, quote, "last synced", status badge (changed/removed/locked text from S23), "Open source" (uses `deep_link`).
5. On `done`: replace bubble text with `final_text` (authoritative), keep chips.
6. On `error`: keep partial text, show inline error with Retry (resends the same message) when `retryable`.
7. Conversation list (sidebar on desktop, sheet on mobile) from `GET /conversations`; opening one loads messages with stored citations.
8. Suggested prompts on an empty chat: "What's due this week?", "Did anything change?", "Prep me for my next exam".

**Study sets** (`/study/[id]` and inline cards from `study_set` events)
9. **Plan:** day-by-day list with minutes, topics, tasks; each task's citation chips; checkboxes stored locally (localStorage, per set).
10. **Quiz:** one question at a time; MCQ select → reveal correct/incorrect + explanation + citations; short answer → "Show answer" reveal; score at the end; retry.
11. **Flashcards:** flip on click/space; next/prev with arrows; shuffle; "Got it / Again" piles (local only).

**Approvals**
12. `approval_required` renders a card listing proposed blocks (local times); **Add** → `POST /study-blocks/decision {approve:true}` → "Added. They'll show up in your calendar app on its next refresh." **Skip** → approve:false. Buttons disabled after a decision; decision persisted (reloading the conversation shows the outcome).

## Errors and edge cases
| Case | Expected behavior |
|---|---|
| Unknown event type | Ignored (forward compatible) |
| `citations` never arrives (error) | Markers removed; text shown without chips |
| Very long answer | Smooth scrolling; "jump to latest" button when user scrolled up |

## Acceptance criteria
- [ ] Scripted mock stream renders all states correctly
- [ ] Citation chips open cards with working links
- [ ] Quiz and flashcards fully keyboard-operable
- [ ] Approval decision reflected in UI and backend

## Test plan
| ID | Test | Type |
|---|---|---|
| S33-T01 | Status checklist transitions started → done/failed | component |
| S33-T02 | Text deltas accumulate; markers show placeholders while streaming | component |
| S33-T03 | `citations` event converts valid markers to numbered chips, removes dropped | component |
| S33-T04 | `done.final_text` replaces streamed text | component |
| S33-T05 | Retry on retryable error resends the message | component |
| S33-T06 | Citation card shows status badge for changed/removed | component |
| S33-T07 | Quiz: MCQ reveal, scoring, retry | component |
| S33-T08 | Flashcards: flip, next/prev, keyboard controls | component |
| S33-T09 | Approval card: Add/Skip call API once and lock buttons | component |
| S33-T10 | Stop button aborts the stream | component |
| S33-T11 | E2E (mocked): ask → stream → open quiz → answer → approve blocks | e2e |
| S33-T12 | E2E (mocked, 375 px): message box stays above the bottom tabs, empty and after a long chat | e2e |
| S33-T13 | New chat shows suggested questions that send when tapped (rule 8) | component |

## Out of scope
Voice input, editing past messages, sharing study sets.
