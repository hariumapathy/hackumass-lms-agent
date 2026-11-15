# Development log

The relay baton. **Newest entry first.** Every session adds one entry at its start (header only) and fills it in as it goes; the last thing before a handoff is making sure it's complete. Protocol: [AGENTS.md → Relay sessions](../AGENTS.md#-relay-sessions-start-and-handoff-mandatory).

Keep entries short and factual. Link specs (`S11`), commits (short hash) and PRs. Don't repeat what specs already say; record what *happened*.

## Entry template
```markdown
## <YYYY-MM-DD HH:MM ET> · <person>'s laptop · <tool + model> · branch <dev/name>
**Hour:** H<n> (hacking began Fri Nov 13 20:30 ET; final Devpost submission Sun Nov 15 09:00 ET; code freeze 08:00)
**Done:** S__ (what, commit abc1234, PR #_) ...
**In progress (not finished):** S__: what's left, where the code is
**Decisions / design changes:** one line each (also in docs/decisions.md)
**Roadblocks:** what, what was tried, options
**State of main:** merged up to <hash>? tests green?
**Next steps (in order):** 1. ... 2. ... 3. ...
**Gotchas for the next agent:** ...
```

> **Agents editing this file with scripts:** match the newest dated entry, not the template above (an earlier `sed` inserted into the template by mistake).

---

## 2026-11-14 19:25 ET · Neal's laptop · Claude Code (Opus 5.5) · branch dev/neal
**Hour:** ~H23 (Devpost draft due 23:59 tonight; final submission Sun 09:00, freeze 08:00)
**Start check:** main = c9acce2 (fast-forwarded into dev/neal); `make test` green (60 pass, 2 skip pending S01). Local Supabase started (Docker).
**Done:** **S01 schema**: `0001_init.sql` (enums, 19 tables, indexes incl. HNSW + GIN, RLS select-own for `authenticated`, no client writes, `connection_secrets` locked). Row models for every table (`TABLE_MODELS`). S01-T01–T08 + model/column check pass; S20-T05/T07 un-skipped and pass (made their emails unique so they re-run).
**Done (cont.):** **S03 seed** (`43824e4`): fixtures in `supabase/seed/`, `uv run app seed`, `make db-reset` = migrate + seed (0.5 s, fake embeddings). Local login `demo@example.com` / `demo-password-311`; IDs match `mock_data.py`. Also `core/embeddings.py` (fake + Gemini) and `core/hashing.py` (S10-T01). PR #8 (S01 + S03) open for B/C review. Merged main (Hari's S21) into dev/neal: 166 pass, 1 xfail; ruff/pyright/eslint/tsc/vitest green.
**Process notes (honest):** S01/S03 were still `Draft` (built on the handoff's instruction; review now in PR #8). S03 tests were written alongside the loader, not strictly failing-first.
**Decisions / design changes:** none (clarifications in S01/S03 implementation notes).
**Roadblocks:** none. Hosted Supabase secret key is in git-ignored `.env.hosted`; hosted `DATABASE_URL` + `GEMINI_API_KEY` still needed to seed the hosted demo with real embeddings.
**Next steps (in order):** 1. S10 sync framework. 2. S11 Canvas. 3. S12 processing (tiktoken chunker). 4. Merge PR #8 once B/C OK (or at handoff if green).
## 2026-11-14 19:20 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari · HANDOFF (Hari pauses; Neal starts)
**Hour:** ~H23 (Devpost draft due **23:59 tonight**; final submission Sun 09:00, freeze 08:00; judging 12:30)
**Start check:** main = fb07fb2; `make setup` ok; `make test` green (27 backend + 1 web).
**Done:**
- **S20 auth** (`84888b4`, PR #5, merged to main as `c9acce2`): Supabase tokens verified by `alg` (ES256 via the project JWKS, cached 10 min; HS256 via `SUPABASE_JWT_SECRET` if set). Route-table + repository-signature scans, error envelope (401/404/422/500, 503 retryable), `PATCH /me` validation, 10/min chat rate limit, JSON request logs without tokens or text, psycopg pool + `profiles` repository. Smoke-checked against the real `.env`: live JWKS fetch works, forged tokens get 401.
- **S21 plumbing** (`e537d8d`, PR #6, now included in the final dev/hari PR): tool args, `invoke` runner (SDK-shaped), course resolver, coverage/freshness, truncation, untrusted wrapping, local/relative times, status labels. Shared course-code normalizer in `backend/app/core/courses.py` (for S16).
- `GEMINI_API_KEY` is in Hari's `.env` (never in git). Checked: the native and OpenAI-compatible endpoints both answer 200. Models available include `gemini-2.5-flash` / `gemini-3.x-flash` and embeddings `gemini-embedding-001` / `gemini-embedding-2` (for S12: check 1536-dim output).
- Credits/notices: PyJWT, cryptography, psycopg.
**Tests:** 119 backend pass, 2 skip (S20-T05/T07, "pending S01"); web 1 pass; ruff/pyright/eslint/tsc clean; CI green.
**In progress (not finished):** nothing half-built. Parked on dependencies:
- S20 DB parts: wire `/me`, `PATCH /me`, `DELETE /me/data` + profile auto-create to `app/db/repositories/profiles.py`; un-skip `tests/integration/test_s20_db.py`. **Needs S01.** Storage cleanup needs S12, job cancellation needs S10.
- S21 tool SQL (hybrid search with RRF, misses rows) + T02, T04–T06, T09–T11. **Needs S01 + S03.** `fetch_latest` needs S10.
**Decisions / design changes:** `/me` routes keep S02 mock data (with the real user_id) until S01; tokens accepted by `alg`. In decisions.md and the S20 notes.
**Roadblocks:** none. The agent may not run `gh pr merge` (permission check); Hari merges PRs.
**State of main:** S20 merged (`c9acce2`). The final dev/hari PR (S21 + this handoff) is green → Hari merges it. Soumith's frontend (S30/S32/S33, mock mode) is on `dev/soumith`, not on main yet.
**Next steps (in order):**
1. **Hari:** Devpost draft before 23:59 (text in [pitch/devpost.md](pitch/devpost.md)); merge the dev/hari PR; decide Soumith's S02 follow-ups P6–P9 (see `dev/soumith` progress file).
2. **Neal:** S01 schema → S03 seed (IDs match `backend/app/api/mock_data.py`) → S10 → S11 → S12. Reuse `app/core/courses.py` in S16. Repository functions must start `(conn, user_id, ...)` (S20-T04 enforces it).
3. **Hari (after S01/S03):** wire the S20 DB parts → S21 tool SQL → S22 agent runtime on Gemini (key is ready) → S23 citations.
4. **Soumith:** frontend can now sign in for real against the hosted project and call `make api` (S20 is on main).
**Gotchas for the next agent:**
- Auth is real: `Bearer anything` → 401. Tests mint tokens with `tests/helpers.py`; `tests/conftest.py` forces test auth settings and the **local** `DATABASE_URL` (or `TEST_DATABASE_URL`), so tests never touch the hosted DB.
- psycopg async on Windows needs a selector loop: `make api` (`--reload`) is fine; tests use the `pytest_asyncio_loop_factories` hook.
- Python scripts on Windows: open files with `encoding="utf-8"` (cp1252 truncated a spec once).
- New FastAPI includes routers lazily: walk `route.original_router.routes` (see `_api_routes` in `test_s20_auth.py`).

## 2026-11-14 18:52 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari
**Hour:** ~H22.4 (Devpost draft due 23:59 tonight; final submission Sun 09:00, freeze 08:00)
**Start check:** main = 478380a; no new commits from Neal/Soumith yet; `make test` + `make lint` green; usage window reset.
**Done:**
- Step 0: **Gemini is t**In progress:** nothing half-done.abel, Devpost credits/built-with, pitch, hackathon.md (opt in to MLH Best Use of Gemini API).
- Fixed earlier devlog edits that had landed inside the entry template.
**In progress:** Step 0: apply the **Gemini-default decision** (docs/decisions.md) to S26 `models.yaml` default/tiers, S22 notes, S12 embeddings (Gemini embedding at 1536 dims, else alternative), 03 stack table + diagram label, `.env.example`, settings default, Devpost credits + hackathon.md (MLH Best Use of Gemini API opt-in).
**State of the hosted DB:** Supabase project `hackumass-lms-agent`, ref `eahciwnufpjuzqlxqdni`, us-east-1, free plan, org ParkTheBus (Hari), created 17:30 ET. URL `https://eahciwnufpjuzqlxqdni.supabase.co`; auth uses **JWKS** (`/auth/v1/.well-known/jwks.json`), so S20 needs no JWT secret. Public URL + publishable key are in Hari's `.env`; **service role key, DB connection string, GEMINI_API_KEY are secrets** (Hari fills them in and shares via a password manager, never git/chat). No migrations applied yet (S01).
**Next steps (in order):** 1. Finish step 0. 2. S20 real JWT auth (JWKS). 3. S21 agent tools (needs S01 schema from Neal for DB queries; build against seed fixtures meanwhile).

## 2026-11-14 18:10 ET · Soumith's laptop · Claude Code (Opus 5.5) + Codex in parallel · branch dev/soumith
**Hour:** ~H22.5. Devpost draft due 23:59 tonight (Hari); final submission Sun 09:00, code freeze 08:00.

**Done:**
- Synced `dev/soumith` with `main` (`478380a`). Earlier Stage 1 work from before PR #1 was ported onto main's scaffold; the old local branch is kept only as a local backup (not pushed).
- **S02 reviewed from the frontend side: approved.** Generated types cover what the UI needs; remaining gaps are Stage 2/3 follow-ups (P6–P9 in [progress/soumith.md](progress/soumith.md)), not blockers.
- **S30 / S32 / S33 (chat part), mock mode** (`653d134`, pushed to `dev/soumith`): Supabase sign-in + demo sign-in, protected shell (sidebar / bottom tabs), typed API client on `schema.d.ts`, SSE parser + `streamChat` (S02-T05/T06 done here), MSW handlers + fixtures, Today view + course page, streaming chat with status list, citation chips/cards, final_text, Try again, Stop, past chats. **30 web tests green; lint, typecheck, `next build` clean.** E2E specs written (S30-T07, S32-T08), not yet run.
- **Three agents in parallel on role C** (Claude Code, Codex, Cursor): shared brief [handoff/soumith-agents-brief.md](handoff/soumith-agents-brief.md). One worktree + branch each: `../hackumass-lms-agent-claude` (`soumith/claude`), `../hackumass-lms-agent-codex` (`soumith/codex`), `../hackumass-lms-agent-cursor` (`soumith/cursor`); the main checkout stays on `dev/soumith` as merge target. Overlap allowed, merged afterwards. Lanes: **Codex** = S33 study sets + approvals; **Cursor** = S31 onboarding → S34 settings; **Claude** = shell/Today/course QA, merges, docs.
- **E2E green** (`e266eb5`): S30-T07 and S32-T08 pass in mock mode (Playwright Chromium installed). Next 16 dev-only instant-navigation checks limited to opted-in segments (`manual-warning`), since every screen waits for the browser-side sign-in.

**In progress (not finished):** Codex: S33 Stage 2. Cursor: S31 → S34. Claude: merging agent branches as they go green.
- Claude (done since): mock mode now shows “We couldn’t start the demo in this browser” + Try again instead of an endless skeleton (S30-T08, `dd6e581`); screenshot QA at 1280 and 375 px of landing, Today, course, chat, citation card: fixed course-page item colors (S32-T09); phone chat composer handed to Codex (brief §3.A item 9).
**Codex update (soumith/codex):** S33 streamed study-set cards and Add/Skip approval actions implemented tests-first; 34 web tests passing. Study-mode mocks added. Study detail/list pages next. Contract change proposal P7 pending: reloaded approvals cannot show their outcome. Cross-lane change: SSE test expects the study-mode stream for exam prep; no dependencies or contract changes.

- Claude (20:40): merged Cursor's S31 (`b54a81b`, Cursor stopped after it) and fixed its e2e: the mock worker started twice under React Strict Mode, so live logins “expired” mid-flow (`startMockWorker` now idempotent, S30-T09); UMass step says “Echo360 connected”. All 4 e2e + 57 unit tests green. Canvas-expiry banner on every signed-in screen (S34-T06). **S34 settings page handed to Codex** (brief §3.B update).
**Codex study-page update (soumith/codex):** Checkpoint 3fb81e0 committed before fetching/merging origin/dev/soumith (already current, no conflicts). Read the three-agent brief; only section 3.A owned. Finished /study list and plan/quiz/flashcard detail pages, local plan progress, keyboard controls, resolved-map/fallback citation lookup, malformed-payload and fetch-error states. Study REST handlers isolated in handlers-study.ts. Tests-first: missing study-screen import failed before implementation; now 41 unit/component tests + all 3 Chromium e2e tests pass (S33-T11 at 375 px), lint/typecheck/production build pass. Build via node node_modules/next/dist/bin/next build: npm wrapper hit a Turbopack subprocess error; direct Node succeeded. Installed pinned Playwright Chromium locally. No dependencies/contracts changed. P7 approval outcomes on conversation reload still pending. Ready for Claude to merge and update spec/pitch/progress status per the shared brief.

- Claude (21:10): **Codex stopped too, so Claude built S34 Settings**: accounts (status, Refresh, Reconnect, Disconnect with confirm), profile (name, time zone), calendar (Google/Apple/Outlook buttons, masked link, copy, new link with confirm), privacy (Delete my data, type DELETE), Advanced → AI choice grouped Recommended/Experimental (Gemini default). S34-T01–T05 + banner T06; 69 unit + 5 e2e green, lint/typecheck/build clean. **All role-C MVP screens now exist in mock mode.**

- Claude (21:35): **Codex hit its usage limit; Claude finished its lane.** Codex had completed study cards, approvals and study pages (S33-T07–T11). Done now: phone chat layout (message box at the bottom, stays above the tab bar; e2e S33-T12) and a bug where a new chat showed no suggested questions (disabled query counted as loading; S33-T13). Codex's uncommitted duplicate Settings in its worktree is superseded by `46b03e6`. Spec index statuses for S30/S32/S33 corrected. PR `soumith/claude` → `dev/soumith`.

**Decisions / design changes (Soumith OK'd):**
- Frontend REST types are re-exports of generated `schema.d.ts`; only SSE event types are hand-written (from CONTRACT.md).
- Node-20 pins kept: MSW 2.15 (not 3), supabase-js 2.109, `clsx` + `tailwind-merge` instead of shadcn's Node-22 `cn` package.
- Mock mode without Supabase env shows a demo sign-in ("Continue with demo data"); real Supabase sign-in is used whenever the URL + publishable key are set.
- Specs S30/S32/S33 implemented while still `Draft`, with Soumith's go-ahead (relay time pressure).

**Roadblocks:**
- This laptop has no Python / `uv` / `make`: backend tests and `make api` can't run here; web checks run with `pnpm` in `apps/web`. Frontend not yet tried against the real backend stubs.
- Supabase publishable key isn't on this laptop, so real sign-in is untested (demo sign-in works).

**State of main:** `478380a`; `dev/soumith` is ahead with `653d134` (web green). Not merged to main yet.

**Next steps (in order):**
1. Codex: S33 study sets + approval card (brief §3.A). Cursor: S31 onboarding → S34 settings (brief §3.B).
2. Claude: mock-mode service-worker failure message, 375 px QA, merge green agent branches into `dev/soumith`, then PR `dev/soumith` → `main` (brief §3.C).
3. Hari: S20 auth (then real sign-in can be tested with the publishable key), answer S02 follow-ups P6–P9.
4. Anyone with Python: run the web app against `make api` (set `NEXT_PUBLIC_API_MOCKS=0`, `NEXT_PUBLIC_API_URL=http://localhost:8000`) to catch mock/backend drift.

**Gotchas for the next agent:** see brief §5 (Node-20 pins, shadcn `cn` imports, MSW 2 option names, jsdom AbortSignal shim in `tests/setup.ts`, module-level react-markdown config, Suspense for `useSearchParams`).

**Cursor (19:35, branch `soumith/cursor`): S31 onboarding built, S34 not started. Handing the rest to Claude.**
- Done: `src/components/connect/*` (welcome, guided Canvas paste, Gradescope/Echo360 live login with 2 s polling + 409 resume, calendar step with Google/Apple/Outlook links, "Getting your classes" step polling `/sync/status`, resume from `/me` + localStorage, `?reconnect=` → back to `/settings`), `src/app/onboarding/page.tsx`, `src/mocks/handlers-account.ts` (all §3.B endpoints, incl. `/models` with Gemini default, PATCH `/me`, DELETE `/me/data`, calendar rotate), `src/components/ui/dialog.tsx` (hand-written: the shadcn CLI tries to install `cn`). Cross-lane: additive API methods in `client.ts` (+ optional `ApiError.details`), type re-exports in `types.ts`, one spread line in `handlers.ts`.
- Verified: `tests/s31-onboarding.test.tsx`, 14 passing (T01–T05, T07, T08). **Not yet run:** full `pnpm test`, `lint`, `typecheck`, `build`, and the e2e `tests/e2e/s31-onboarding.spec.ts` (T06 + a T05 reconnect test). Run these before merging.
- Left to do: (1) run the checks above and fix anything; (2) **S34 settings** (brief §3.B item 2): mocks and the dialog are ready; reuse `CalendarButtons`/`useCalendarFeed` from `connect/calendar-step.tsx` and `canvasReady`/`LiveLogin` as needed; tests S34-T01…T06; (3) Canvas-expiry banner (< 10 days) also on Today/app shell (S34 rule 1); (4) tick S31 acceptance criteria in the spec.
- Gaps: no UMass Canvas screenshots for the guide yet (text steps only); the S02 409 response doesn't include the existing `login_id` (UI falls back to the id saved in sessionStorage; ask Hari to add `details.login_id`); P6 (no counts, so the last step shows the class count from `/courses`); P8 (no reason for unavailable models).
- e2e on Windows here: set `PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\ms-playwright` (the sandbox points Playwright at an empty cache).

---

## 2026-11-14 17:55 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari · HANDOFF
**Hour:** ~H21.5 (hacking began Fri 20:30 ET). **~6 h to the Devpost draft deadline (Sat 23:59), ~15 h to final submission (Sun 09:00), code freeze 08:00.** (Earlier docs said 18:15/18:40; the real time at this handoff was 17:55.)

**Done (all on `main` after PR #1 merge):**
- Planning docs, specs S00–S34 + new **S17**, AGENTS.md (relay START/HANDOFF protocol, non-technical-student rules, hackathon deliverables, vendoring rule), devlog, `/start` `/handoff` prompts, PR template.
- **S00 scaffolding** (`1695e7b`): backend (FastAPI), apps/web (Next.js 16), supabase/, Makefile, .env.example, CI. CI green.
- **S02 API + SSE contract** (`7c3745d`): typed stubs + mock data for every endpoint, error envelope, SSE framing, scripted `POST /chat` (`?delay_ms=`), `backend/app/api/CONTRACT.md`, `make types` → `apps/web/src/lib/api/`. 27 backend tests.
- Hackathon facts ([hackathon.md](hackathon.md)), pitch kit + Devpost draft ([pitch/](pitch/pitch.md)), category **Best UMass Hack**.
- MCP review → **borrow the pieces** (S14 reworked, S17 added, [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).
- Non-technical-student design: S31 simplified onboarding, S11 token expiry default, S34 model under Advanced, S13 one-UMass-login stretch.

**In progress (not finished):** nothing half-built. S02 awaits Soumith's review (status "In progress"). S00 `make db` untested (Docker Desktop was off).

**Decisions / design changes:** relay protocol with green self-merge; `make` + pinned `npx` tools; Best UMass Hack; non-technical-student rules; Canvas token kept for MVP; MCP pieces borrowed (Option A). All in [decisions.md](decisions.md).

**Roadblocks / waiting on humans:**
- 🚨 **Hari: create the Devpost draft before 23:59 tonight** (text in [pitch/devpost.md](pitch/devpost.md); category Best UMass Hack; add Neal + Soumith; GitHub link).
- **Compressed scope plan still needs Hari's OK** (Echo360 S15 → stretch; minimal S16/S26/S34). Until approved, follow the stage order in specs/README.md but prefer demo-critical work.
- Hosted Supabase + OpenAI key: Hari puts them in `.env` (never in git/chat). Docker Desktop must run for `make db`.
- Specs are still `Draft`: the team should mark Stage 0/1 specs `Ready` quickly (a teammate skim is enough).

**State of main:** PR #1 merged at this handoff (CI green; `make test` + `make lint` green).

**Next steps (in order):**
1. **Neal (A):** S01 schema → S03 seed (mock IDs in `backend/app/api/mock_data.py` match the seed plan) → S10 → S11 → S12.
2. **Hari (B):** S20 real JWT auth → S21 tools → S22 agent runtime → S23 citations (needs S01 for DB-backed tools; use seed).
3. **Soumith (C):** review S02 → S30 shell (MSW handlers + SSE parser moved here) → S32 Today → S33 chat, against `make api` mocks. Follow the non-technical UI rules.
4. Anyone: keep [pitch/pitch.md](pitch/pitch.md) "What actually works" true.

**Gotchas for the next agent:**
- Next.js is **v16**: read `apps/web/AGENTS.md` first. Frontend test tools pinned for **Node 20** (Vitest 3.2, Vite 7, jsdom 26).
- No global pnpm/Supabase CLI: `make` runs pinned versions via `npx`. Re-run `make types` after API changes.
- `current_user` in `backend/app/api/deps.py` is a **stub** until S20 (any `Bearer x` works). Backend needs `tzdata` on Windows. New env var `PUBLIC_API_URL`.
- Two agent sessions shared one checkout earlier; if you run parallel sessions, commit only your own paths.

---

_Earlier entry (superseded by the handoff above):_

## 2026-11-14 18:15 ET · Hari's laptop · Claude Code (Opus) · branch dev/hari
**Hour:** ~H22 (hacking began Fri Nov 13 20:30 ET; **final Devpost submission Sun 09:00 ET**, code freeze 08:00; judging 12:30)
**Done:**
- Hackathon facts captured in [docs/hackathon.md](hackathon.md); pitch kit + Devpost draft in [docs/pitch/](pitch/pitch.md).
- Planning docs, specs S00–S34 (Draft), AGENTS.md, workflow, branches `dev/hari|neal|soumith`, roles (Neal A, Hari B, Soumith C).
- **S00 scaffolding** (commit 1695e7b, PR #1): `backend/` (FastAPI `/health`), `apps/web/` (Next.js 16), `supabase/`, `Makefile`, `.env.example`, CI. `make test` + `make lint` green locally.
- Reviewed three third-party MCP servers (Gradescope, Piazza, Canvas). Findings: [docs/research/mcp-servers-review.md](research/mcp-servers-review.md).
- Relay protocol + this devlog + start/handoff prompts.
- **S02 API + SSE contract** (commit `7c3745d`, PR #1): typed stubs for every endpoint backed by `backend/app/api/mock_data.py`, error envelope, SSE framing, scripted `POST /chat` stream (`?delay_ms=` for UI work), `backend/app/api/CONTRACT.md`, `make types` → `apps/web/src/lib/api/{openapi.json,schema.d.ts}`. 27 backend tests pass; ruff, pyright, eslint and typecheck clean.

**In progress (not finished):**
- **S02:** needs Soumith's review (spec status still "In progress"). MSW handlers + frontend SSE parser (S02-T05/T06) **moved to S30**. Auth is still the demo stub until S20.

**Decisions / design changes:** relay protocol (green self-merge to `main` at handoff); scaffolding uses `make` + pinned `npx` tools (see S00 notes).

**Roadblocks:**
- 🚨 **Devpost draft must exist by Sat 11:59 PM** (Hari creates it, adds Neal + Soumith; text in docs/pitch/devpost.md). Choose ONE `[HACKUMASS]` category (see hackathon.md).
- **Time:** ~14.5 h to final submission at 18:40. Proposed compressed plan (cut Echo360 S15 to stretch, minimal S16/S26/S34) **awaits Hari's approval**; not yet applied to docs.
- **MCP server approach awaits Hari's decision** (recommended: borrow pieces into our connectors; see research doc).
- Docker Desktop wasn't running on Hari's laptop → `make db` (local Supabase) untested.
- Hosted Supabase project + OpenAI key: Hari will create them and put values in `.env` (never in git or chat).

**State of main:** `a768196` (docs only). PR #1 (`dev/hari` → `main`): roles + S00 (+ S02 when done); CI not yet reported at time of writing.

**Next steps (in order):**
1. Soumith reviews S02; Hari decides on merging PR #1 (roles + S00 + S02) once CI is green.
2. Neal (A): S01 schema + S03 seed, then S10 → S11 → S12.
3. Hari (B): S20 → S21 → S22 → S23.
4. Soumith (C): S30 → S32 → S33 against the S02 mocks/types.

**Gotchas for the next agent:**
- Next.js is **v16**: read `apps/web/AGENTS.md` before frontend code. Frontend test tooling is pinned for **Node 20**.
- No global pnpm/Supabase CLI needed: `make` runs pinned versions via `npx`.
- `current_user` in `backend/app/api/deps.py` is a **stub** until S20: any `Authorization: Bearer x` works.
- Backend depends on `tzdata` (Windows has no IANA timezone database). Re-run `make types` after any API change.
