# 05 — Roadmap

> Draft for a team of 3. Who takes which role is still open ([06](06-open-questions.md)).

## Demo script first (write in hour 1, build backward)
1. Sign in → connect Canvas (token) → log in to Gradescope/Echo360 via embedded live browser with a Duo push → "4 courses, 23 items, 12 lectures synced."
2. **Today view:** ranked deadlines, a "changed" badge on a moved exam, a source link on every item.
3. **"Prep me for the CS 311 midterm"** → study plan + quiz + flashcards, each citing the exact slide or lecture timestamp.
4. **"Why trust this":** click citations live (slide, Echo360 timestamp, edited announcement).
5. Switch the model in settings, ask again.
6. Subscribe to the `.ics` feed → deadlines appear in their calendar.

## MVP cut line
**Must have:** Canvas (token) + Gradescope and Echo360 (cloud browser) · Today view · chat and study mode with verified citations · `.ics` feed · curated model picker · seeded backup account.

**Stretch, in order (owner):** Piazza (A) → MCP server (B) → in-Canvas side panel / extension (C) → Campuswire → email → grade tracking.

**Scope warning:** even with three people, do 3 integrations well rather than 6 badly.

## Roles

| Role | Owns | Folders |
|---|---|---|
| **A: Data and sync** | Schema + migrations, sync worker + job queue, Canvas / Gradescope / Echo360 connectors, live-view login (backend side), parsing + embeddings, merge + change detection, `fetch_latest` jobs, demo seed data | `db/`, `backend/connectors/`, `backend/sync/` |
| **B: Agent and API** | FastAPI + JWT check, agent tools, Agents SDK agent + prompts, SSE stream, citation guardrail, approvals, `create_study_set`, `.ics` feed, model picker backend + model test script | `backend/api/`, `backend/agent/` |
| **C: Frontend and product** | Next.js app, auth, onboarding + connect flow (incl. live-view embed), Today view, chat UI on SSE, study cards (plan / quiz / flashcards), citation chips, settings, polish + mobile; leads demo script, slides and video | `apps/web/` |

**Contracts (agreed together in hours 0–2, then changed only by agreement):**
1. **DB schema** in `db/` (A writes, B reads, C reads via Supabase for the dashboard).
2. **API + SSE event format** (B defines, C consumes): endpoints, event types (`status`, `text`, `study_set`, `approval_required`, `citations`, `done`, `error`).
3. **Seed data** in `db/seed/`: a realistic fake semester loaded on day one, so B and C build against real-shaped data before A's connectors are done.

## 36-hour plan

| Hours | A: Data and sync | B: Agent and API | C: Frontend and product |
|---|---|---|---|
| **0–2 (together)** | Demo script, schema, API/SSE contract, seed data, repo + Supabase setup | ← same | ← same |
| 2–10 | Worker + job queue; Canvas token sync (courses, assignments, announcements, files); parsing + embeddings | FastAPI + JWT; tools (`get_items`, `search_materials`, `get_changes`, `get_material`); agent streaming over SSE | Next.js shell, auth, Today view on seed data, chat UI consuming SSE |
| **Checkpoint H10** | *A question about real Canvas data answered end to end in the UI* | | |
| 10–18 | Cloud-browser login + Gradescope sync; Echo360 transcripts; `fetch_latest` jobs | Citation guardrail; `create_study_set`; approvals + `add_study_block`; `.ics` feed | Onboarding + connect flow (token paste, live-view embed); study cards; citation chips; approval prompt |
| **Checkpoint H18** | *Study mode with verified citations from real data; Gradescope connected* | | |
| 18–24 | Merge + change detection; sync freshness / reconnect status | Curated model picker + model test script; `get_course_overview` | Settings + model picker UI; "changed" badges; freshness + Reconnect UI |
| **Checkpoint H24: MVP feature freeze** | *Full demo run-through* | | |
| 24–30 | Demo seed account (backup); stretch: Piazza | Run model test script, fix prompt/tool issues; stretch: MCP server | Polish, loading/empty states, mobile; slides draft |
| 30–36 | Bug fixes only (code freeze H30) | Bug fixes only | Demo script rehearsal, 2-min video, slides |

Repo layout: see [03](03-architecture.md#where-each-piece-lives-in-the-repo).
