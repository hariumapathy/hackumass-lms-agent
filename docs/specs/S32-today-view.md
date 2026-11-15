# S32 — Today view and course pages

| | |
|---|---|
| **Status** | In progress (Neal): database integration and live Canvas dashboard verified; frontend regressions green |
| **Stage** | 1 (Today on seed data); course page + changes polish in Stage 3 |
| **Role** | C (UI); B implements `GET /today`, `/courses`, `/items`, `/changes` (deterministic queries, no AI) |
| **Depends on** | S30, S02 |
| **Folders** | `apps/web/src/app/today/`, `apps/web/src/app/courses/`, `backend/app/api/routes/today.py` |

## Purpose
The deterministic dashboard: what's overdue, due today, due this week, upcoming exams, what changed, and new announcements, with a source link on every item and freshness per source. **No LLM involved**, so it's instant and can't hallucinate.

## Inputs
`GET /today` → `Today` (S02); `GET /courses/{id}` → `CourseDetail`; `POST /changes/seen`.

## Outputs (screen)
```
┌ Today · Thu Nov 13 ─────────────────────── Canvas 12m · Gradescope 40m · Echo360 ⚠ 3d ┐
│ ⚠ 2 changes: "CS 311 Midterm 1 moved Nov 18 → Nov 20"  [Mark seen]                    │
│ Overdue (1)        STATS 315 HW 6 · due yesterday 11:59 PM        [Canvas]           │
│ Due today (2)      COMPSCI 320 Lab 4 · 11:59 PM                   [Gradescope]       │
│ This week (5)      ...                                                               │
│ Upcoming exams     COMPSCI 311 Midterm 1 · Thu Nov 20, 7 PM · CHANGED  [Canvas][Piazza]│
│ New announcements  MATH 235 · "Office hours moved" · 2h ago        [Canvas]          │
│ [Ask about your week →]                                                             │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Backend rules for `GET /today` (B)
1. Window computed in the student's timezone: `overdue` = due before now, not removed, within the last 7 days; `due_today` = due between now and local end of day; `due_this_week` = after today through 7 days; `upcoming_exams` = type exam within 30 days.
2. `changes` = unseen, last 14 days; `new_posts` = last 72 hours.
3. Each item includes `sources` (all platforms it was merged from) and `changed_fields`.
4. `sources` freshness from S10 `/sync/status` logic.
5. Pure query functions with an injected clock (testable).
6. **Submitted work is done work** (2026-11-15, split doc B1): `Item.submitted` is true when any live source's `item_sources.raw.submitted` is true (Canvas `include[]=submission`; Gradescope status column/score). Submitted items never appear in `overdue`; elsewhere the UI shows a small SUBMITTED badge and no late/soon colouring. The agent's `get_items` returns `submitted` too. No schema change; a resync updates the flag even when the hash is unchanged. Tests: `test_submitted_db.py`, `test_submitted_*` in the S11/S14 connector tests, S32-T11.

## Frontend behavior (C)
1. Sections hidden when empty; whole-page empty state when nothing is due ("Nothing due this week 🎉").
2. Items: course color chip, title, local due time + relative, type icon, status badge (`CHANGED`, `REMOVED`), source chips linking to `source_url` (new tab).
3. Change banner: summaries; "Mark seen" → `POST /changes/seen`, banner clears, item badges clear.
4. Freshness bar: per source; `needs_reconnect` shows "Reconnect" → `/onboarding?reconnect=<p>`; stale shows ⚠ with "Sync now" → `POST /sync`.
5. "Ask about your week" opens chat prefilled.
6. Course page: header (code, name, platforms), items list (all, grouped upcoming/past), recent posts, materials list (title, kind, processing status), "Ask about this course" button.
7. Auto-refresh every 5 minutes and on window focus.

## Acceptance criteria
- [ ] Renders correctly on seed data at desktop and 375 px widths
- [ ] Every item shows at least one working source link
- [ ] Timezone handling correct (items near midnight land in the right section)

## Test plan
| ID | Test | Type |
|---|---|---|
| S32-T01 | Backend: section bucketing across local midnight and DST | unit |
| S32-T02 | Backend: removed items excluded; changed items flagged | integration |
| S32-T03 | Backend: changes only unseen in last 14 days | integration |
| S32-T04 | UI: sections render and hide when empty; full empty state | component |
| S32-T05 | UI: change banner "Mark seen" calls API and clears badges | component |
| S32-T06 | UI: needs_reconnect source shows Reconnect link | component |
| S32-T07 | UI: source chips link to `source_url` in new tab | component |
| S32-T08 | E2E (mocked): Today → course page → back | e2e |
| S32-T09 | Course page: upcoming/past items with course color and source links | component |

## Out of scope
Grades, drag-and-drop planning, notifications.

## Demo integration verification (2026-11-14, Neal)
- User authorized fixing the existing demo specs on main. Database routes now use scoped queries for Today, course summaries/details, items, changes, mark-seen and citations. Empty accounts return empty lists; another student's course returns 404. No schema/API contracts changed.
- Today uses the profile timezone and injected app clock, including DST, seven-day overdue, 30-day exams, unseen changes from 14 days, and posts from 72 hours. Mark-seen persists and clears item badges.
- The app polls import status every 3 seconds while running (30 seconds idle), invalidating Today/course/profile caches on completion. Five-minute Today refresh remains. Import status includes pending merges so onboarding waits for canonical deadlines.
- Regression tests: `tests/integration/test_s32_dashboard_db.py`, `test_s11_connect_route_db.py`, web `tests/s32-sync-refresh.test.tsx`. S32-T10 = completion invalidates cached views; S32-T11 = pending merge stays running and runs before bulk processing. Live Canvas → local DB → Today verified.
