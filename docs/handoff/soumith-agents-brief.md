# Soumith's frontend lane: brief for three parallel agents (Claude Code, Codex, Cursor)

**Updated:** 2026-11-14 ~19:40 ET (≈ H23). Written by Claude Code (Opus 5.5) on Soumith's laptop.
**Base for everyone:** `dev/soumith` (includes Stage 1 frontend `653d134` and e2e fixes `e266eb5`).
Final Devpost submission **Sun 09:00 ET**, our code freeze **08:00**, live demo 12:30.

Each agent reads **§0–§2 and §5–§8**, then **only its own lane in §3**.

---

## 0. Read first (~10 min)
1. [`AGENTS.md`](../../AGENTS.md): rules, relay protocol, **non-technical-student UI rules**, non-negotiables.
2. [`apps/web/AGENTS.md`](../../apps/web/AGENTS.md): **Next.js 16 differs from what you know.** Check `apps/web/node_modules/next/dist/docs/` before writing Next code.
3. The newest entry in [`docs/devlog.md`](../devlog.md).
4. The specs for your lane (§3). Contract: [`backend/app/api/CONTRACT.md`](../../backend/app/api/CONTRACT.md) (SSE) and `apps/web/src/lib/api/schema.d.ts` (REST, generated; **never edit by hand**).

## 1. Worktrees: one folder and branch per agent
All four folders sit side by side under `HackUmass 2026/`:

| Folder | Branch | Who |
|---|---|---|
| `hackumass-lms-agent/` (main checkout) | `dev/soumith` | **Nobody edits here.** Merge target only |
| `hackumass-lms-agent-claude/` | `soumith/claude` | **Claude Code** |
| `hackumass-lms-agent-codex/` | `soumith/codex` | **Codex** |
| `hackumass-lms-agent-cursor/` | `soumith/cursor` | **Cursor** |

Each worktree has its deps installed and its branch pushed. **Work only in your own folder.** Editing the same files as another agent is allowed; we merge afterwards.
```bash
cd ../hackumass-lms-agent-<you>/apps/web
pnpm test        # 30 passing at the start
```
- Commit + `git push` your branch after each verified piece. Small commits merge easier.
- **Every ~hour:** `git fetch origin && git merge origin/dev/soumith` to pick up what's been merged; fix conflicts on your side.
- **Merging into `dev/soumith`** is done in the main checkout by Claude (or Soumith) when a piece is green: `git merge origin/soumith/<agent>`, re-run tests, push. Then `dev/soumith` → `main` at handoff.
- Ignore the stray `.agents/` folder in the main checkout.

## 2. What already exists (don't rebuild it)
Stage 0 (S00 scaffold + S02 contract) is on `main` (Hari). On `dev/soumith`, **Stage 1 frontend runs entirely in mock mode** (MSW). 30 unit/component tests and 2 e2e tests are green, and lint, typecheck and `next build` are clean.

| Area | Files | Notes |
|---|---|---|
| **S30 shell + auth** | `src/app/{layout,page,providers}.tsx`, `src/app/auth/callback/`, `src/app/(app)/layout.tsx`, `src/components/{layout,auth,states}/`, `src/lib/auth/*`, `src/lib/config.ts` | Supabase (Google + magic link) when `NEXT_PUBLIC_SUPABASE_URL/ANON_KEY` are set; otherwise a **demo sign-in** ("Continue with demo data"). `RequireAuth`, sidebar ≥768 px / bottom tabs below |
| **API client** | `src/lib/api/client.ts` (`api()`, `ApiError`, `configureApi`, `isAbortError`), `src/lib/api/types.ts` | REST types = **re-exports of `schema.d.ts`**; SSE `ChatEvent` union hand-written from CONTRACT.md |
| **SSE** | `src/lib/api/sse.ts` (`SseParser`, `toChatEvent`, `streamChat`) | Split frames, CRLF, unknown events, pre-stream JSON errors, Stop (cancels reader) |
| **Mocks** | `src/mocks/{fixtures,handlers,server,browser}.ts`, `public/mockServiceWorker.js` | Fixtures mirror S03 (COMPSCI 311/320, MATH 235, STATS 315), dates relative to now. `createHandlers()` covers Stage 1 endpoints + scripted `POST /chat`; `sseResponse(events, {delayMs, hang})` helper |
| **S32 Today + course** | `src/components/{today,course}/*`, `src/app/(app)/{today,courses/[id]}` | |
| **S33 chat (Stage 1)** | `src/components/chat/*`, `src/app/(app)/chat/**` | `chat-state.ts` (pure reducer), `assistant-text.tsx` (markdown + citation chips; renderer config is **module-level on purpose**), `citation-card.tsx`, `status-list.tsx`, `chat-screen.tsx` |
| Placeholders ("Coming soon.") | `src/app/(app)/study/**`, `src/app/(app)/settings/`, `src/app/onboarding/` | Replaced by Codex (study) and Cursor (onboarding, settings) |
| Tests | `tests/*.test.ts(x)`, `tests/utils.tsx` (`renderWithProviders`, `fakeAuth`, `mockMatchMedia`), `tests/setup.ts`, `tests/next-navigation.ts`, `tests/e2e/*.spec.ts` | |

Run the app in mock mode: `apps/web/.env.local` with `NEXT_PUBLIC_API_MOCKS=1` (Supabase vars empty) → `pnpm dev` → "Continue with demo data". Use a normal Chrome/Edge window; the Claude desktop browser pane can't register the mock service worker.

## 3. Lanes
Specs are still status `Draft`; Soumith has OK'd building from them. Follow each spec exactly, **tests first** (test IDs in test names, confirm they fail, then implement). If a spec is wrong or unclear: stop, note it in your commit + the devlog, don't silently work around it. **Don't change the API contract** (schema/SSE); list needed changes for Hari instead.

### 3.A Codex: S33 Stage 2, study sets + approvals (demo-critical: "Prep me for the CS 311 midterm")
Specs: [S33](../specs/S33-chat-and-study-ui.md) (study cards + approvals), [S24](../specs/S24-study-sets.md) (payload shapes), [S25](../specs/S25-approvals-and-calendar.md) (proposal pattern).
1. **Chat events:** extend `chat-state.ts`: `Turn.studySets: StudySet[]` (from `study_set`) and `Turn.approval: {blocks, summary} | null` (from `approval_required`). Today both fall into `default:`.
2. **Inline cards in chat** (`chat-screen.tsx` `TurnView`): one card per study set ("Study plan · 5 days", "Practice quiz · 10 Qs", "Flashcards · 20") linking to `/study/[id]`. Plus the **approval card** listing blocks in local time with **Add** / **Skip** → `POST /study-blocks/decision {block_ids, approve}`; buttons lock after a decision; copy: "Added. They'll show up in your calendar app on its next refresh."
3. **`/study/[studySetId]`** (`GET /study-sets/{id}`):
   - **Plan:** list of days; checkboxes saved in localStorage.
   - **Quiz:** one question at a time; MCQ reveal + explanation + citations; "Show answer" for short answers; score; retry.
   - **Flashcards:** flip (click/Space), prev/next (arrows), shuffle, "Got it / Again" piles (local only).
   - All keyboard-operable.
4. **`/study`**: list from `GET /study-sets`.
5. **Citations on study items:** S24 says payloads carry a resolved `citations` map, but the **backend mock only has `cards[].chunk_ids`** (`backend/app/api/mock_data.py` `study_set()`). Use the map if present, else `GET /citations?ids=`. Reuse `CitationCard`.
6. **Mocks:** put new handlers in **`src/mocks/handlers-study.ts`** (export `studyHandlers(f)`), add one line to spread them in `createHandlers`. Cover `GET /study-sets`, `GET /study-sets/{id}` (plan, quiz, flashcards), `POST /study-blocks/decision`, and a scripted chat variant emitting `study_set` + `approval_required` (after the last `text`, before `citations`).
7. **Tests:** S33-T07, T08, T09 + a runtime test that the two events render cards; e2e S33-T11.
8. **Known contract gap:** reloaded conversations can't show whether blocks were added or skipped (`Message` has only `block_ids`). Render without the outcome and note it ("P7 pending", see `docs/progress/soumith.md`).

### 3.B Cursor: S31 onboarding, then S34 settings
Specs: [S31](../specs/S31-onboarding-and-connect.md) (**simplified for non-technical students on `main`, read it carefully**), [S34](../specs/S34-settings.md), [S11](../specs/S11-canvas-connector.md) (Canvas connect endpoint), [S13](../specs/S13-browser-sessions.md) (live login endpoints), [S26](../specs/S26-model-picker-and-evals.md) (`/models`), [S25](../specs/S25-approvals-and-calendar.md) (calendar feed).
1. **S31 onboarding** (replace `src/app/onboarding/page.tsx`, keep `RequireAuth`; components in `src/components/connect/`):
   - Guided Canvas step: `POST /connections/canvas {token, expires_at?}`, with friendly error messages.
   - Live-login steps: `POST /connections/{platform}/login` + poll `GET .../login/{login_id}` every 2 s; 409 = resume polling.
   - Calendar step: `GET /calendar/feed` with an "Add to Google Calendar" button, not a raw URL.
   - Wrap-up step: poll `GET /sync/status`.
   - **Resume** at the first incomplete step (derived from `/me`). **`?reconnect=<platform>`** jumps to that step and returns to `/settings` (Today already links to `/onboarding?reconnect=echo360`).
   - Plain language: never "token", "sync", "API" or "model" in headings or buttons; follow S31's wording and the pictures-style guide.
   - Tests S31-T01…T06.
2. **S34 settings** (`src/app/(app)/settings/`, components in `src/components/settings/`):
   - Connections (Reconnect / Disconnect with a confirm dialog / Refresh) and profile (timezone).
   - Calendar: "Add to Google Calendar" plus Rotate with a confirm dialog.
   - Privacy: **Delete my data** (type DELETE to confirm, then sign out).
   - **Model choice only under Settings → Advanced** (Gemini is the default, see `docs/decisions.md`).
   - Token-expiry banner at < 10 days.
   - Tests S34-T01…T06.
3. **Mocks:** put new handlers in **`src/mocks/handlers-account.ts`** (export `accountHandlers(f)`), add one line to spread them in `createHandlers`. Cover `POST /connections/canvas`, login start/poll, `DELETE /connections/{p}`, `GET /models`, `PATCH /me`, `DELETE /me/data`, `GET /calendar/feed`, `POST /calendar/feed/rotate`.
4. Shared UI you'll need: `npx shadcn@4.23.0 add dialog` (then fix the `cn` import, §5).

### 3.C Claude Code: integration, shell polish, QA, docs
1. Fix: mock mode hangs on the loading skeleton if the service worker can't register (show a clear message plus "Try again" instead).
2. Browser QA of shell / Today / course / chat at desktop and 375 px; fix layout issues in those files.
3. Merge green work from `soumith/codex` and `soumith/cursor` into `dev/soumith` (run all tests after each merge), keep the devlog / progress / spec index / pitch "What actually works" current, and open the PR `dev/soumith` → `main` at handoff.
4. When a laptop with Python is available: run the web app against Hari's `make api` stubs to catch mock/backend drift.

## 4. Preferred file lanes (overlap is allowed; this just keeps merges small)
| Agent | Mostly edits |
|---|---|
| **Codex** | `src/components/chat/**`, `src/app/(app)/chat/**`, `src/components/study/**`, `src/app/(app)/study/**`, `src/mocks/handlers-study.ts`, `tests/s33-*`, `tests/e2e/s33*` |
| **Cursor** | `src/app/onboarding/**`, `src/components/connect/**`, `src/app/(app)/settings/**`, `src/components/settings/**`, `src/mocks/handlers-account.ts`, `tests/s31-*`, `tests/s34-*`, `tests/e2e/s31*` |
| **Claude** | `src/app/{layout,page,providers}.tsx`, `src/app/auth/**`, `src/app/(app)/{layout.tsx,today,courses}`, `src/components/{layout,auth,today,course,states}/**`, `src/lib/{auth,config.ts,time.ts,platforms.ts}`, `tests/{s00-smoke,s30-shell,s32-today,sse}*`, `tests/e2e/{s30,s32}*`, `playwright.config.ts`, `next.config.ts`, all of `docs/` |
| **Shared: append-only, small** | `src/mocks/{handlers,fixtures}.ts` (one spread line each in `createHandlers`), `src/lib/api/{client,types,sse}.ts` (add methods/types, don't reshape existing ones), `src/components/ui/**` (shadcn adds), `tests/utils.tsx`, `tests/setup.ts`, `package.json` + `pnpm-lock.yaml` (name new deps in the commit message) |

Mention cross-lane edits in your commit message. **Docs:** only Claude edits `docs/` files other than your own devlog lines: append a short "Codex: …" / "Cursor: …" note under the newest Soumith devlog entry when you finish a piece.

## 5. Environment and gotchas (each of these already cost time)
- **Node:** the laptop has Node 24, but the team pins **Node-20-compatible** tooling. Don't upgrade past:
  - Vitest 3.2, Vite 7, `@vitejs/plugin-react` 4, jsdom 26.
  - **MSW 2.15**: MSW 3 needs Node 22.
  - **`@supabase/supabase-js` 2.109**: 2.110+ needs Node 22.
  - Check `npm view <pkg>@<ver> engines` before adding a dep.
- **shadcn 4** generates `import { cn } from "cn"` (Node-22-only package). We use `@/lib/utils` (`clsx` + `tailwind-merge`). After `shadcn add`: `sed -i 's|import { cn } from "cn"|import { cn } from "@/lib/utils"|' src/components/ui/*.tsx` and make sure `cn` wasn't added to `package.json`.
- **MSW 2:** the option is `onUnhandledRequest` (MSW 3's `onUnhandledFrame` doesn't exist here). Import `http`, `HttpResponse` from `"msw"` and `setupServer` from `"msw/node"`.
- **jsdom vs Node fetch:** `tests/setup.ts` wraps `fetch` to turn jsdom `AbortSignal`s into Node ones; without it, any fetch with a `signal` throws in tests. Keep it.
- **Abort checks:** use `isAbortError(e)` / `signal.aborted`, never `instanceof DOMException`.
- **react-markdown:** keep `components`, plugins and `urlTransform` module-level (per-render objects remount the DOM on every streamed delta).
- **Next 16:**
  - Pages using `useSearchParams` need `<Suspense>` (see `src/app/(app)/chat/page.tsx`).
  - Client pages read params with `useParams()`.
  - Dev-only instant-navigation checks run only on segments with `export const instant` (`next.config.ts`).
- **No `make`, Python or `uv` on this laptop.** Run web checks from `apps/web`: `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm test:e2e`. The e2e run starts its own mock server on :3100; Chromium is already installed. **Two agents running e2e at once collide on port 3100:** if it's busy, wait or run `pnpm exec playwright test --config ...` with another port.
- **Windows / Git Bash:** use `MSYS_NO_PATHCONV=1` before `git show origin/main:<path>`. CRLF warnings on commit are harmless; shell `sed` replacements that span lines fail on CRLF files, so use your editor.
- **Next.js rewrites `apps/web/AGENTS.md`** when `next dev` runs; commit it if it changes.

## 6. UI rules (AGENTS.md / docs/01-vision.md)
- Plain language: no "token", "sync", "MCP", "model", "API" or error codes in the main UI. Buttons say "Try again", "Reconnect Gradescope", "Refresh".
- One clear action per problem, never a dead end. Mobile works at 375 px. Keyboard access + `aria-live="polite"` for streaming/status.
- **The UI never builds platform URLs:** links come only from API fields (`source_url`, `url`, `deep_link`).
- Writes need a click: study blocks stay proposals until the student presses **Add**.

## 7. Definition of done for each piece
- Spec tests written first (IDs in names) and passing.
- `pnpm test && pnpm lint && pnpm typecheck && pnpm build` green.
- Acceptance criteria ticked in the spec.
- Commit + push your branch.
- One-line devlog note.
- Tell Soumith it's ready to merge.

## 8. Contract follow-ups already raised with Hari (don't duplicate)
P6 sync counts for onboarding · P7 block outcomes on reload · P8 `ModelOption.unavailable_reason` · P9 typed study-set payload / SSE types in OpenAPI. Details: [`docs/progress/soumith.md`](../progress/soumith.md).
