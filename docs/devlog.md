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
0. **FIRST (Hari's next session): apply the Gemini-default decision** (docs/decisions.md): update S26 `models.yaml` default + tiers, S22 `model_for` notes, S12 embeddings provider/dimension (verify Gemini embedding output dims = 1536 or pick alternative), 03 stack table + diagram LLM label, `.env.example` comments (GEMINI_API_KEY required, OPENAI_API_KEY optional), Devpost credits + hackathon.md (opt in to MLH Best Use of Gemini API). Hari gets a free key at aistudio.google.com and puts it in `.env`.
**Gotchas for the next agent:** ...
- **Hosted Supabase project created (2026-11-14 17:30 ET):** `hackumass-lms-agent`, ref `eahciwnufpjuzqlxqdni`, us-east-1, free plan, org ParkTheBus (Hari). URL `https://eahciwnufpjuzqlxqdni.supabase.co`; auth uses **JWKS** (`/auth/v1/.well-known/jwks.json`), so S20 needs no JWT secret. Public URL + publishable key are in Hari's `.env`; **service role key and DB connection string are secrets**: Hari shares them via a password manager, never git/chat. No migrations applied yet (S01).
```

---

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
