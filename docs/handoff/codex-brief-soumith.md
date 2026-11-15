# Codex brief: Soumith's frontend lane (role C), parallel with Claude

**Written:** 2026-11-14 ~19:05 ET (≈ H22.5) by Claude Code (Opus 5.5) on Soumith's laptop.
**For:** Codex, working **at the same time** as Claude Code on Soumith's frontend work.
**Base:** `dev/soumith` @ `653d134` (pushed). Final Devpost submission **Sun 09:00 ET**, our code freeze **08:00**, live demo 12:30.

---

## 0. Read first (in this order, ~10 min)
1. [`AGENTS.md`](../../AGENTS.md): rules, relay protocol, **non-technical-student UI rules**, non-negotiables.
2. [`apps/web/AGENTS.md`](../../apps/web/AGENTS.md): **Next.js 16 differs from what you know.** Read the bundled docs in `apps/web/node_modules/next/dist/docs/` before writing Next code.
3. The newest entry in [`docs/devlog.md`](../devlog.md).
4. Your specs (section 3): [S33](../specs/S33-chat-and-study-ui.md) (study cards + approvals part), [S31](../specs/S31-onboarding-and-connect.md), then [S34](../specs/S34-settings.md). Also the backend side they use: [S24](../specs/S24-study-sets.md) (payload shapes), [S25](../specs/S25-approvals-and-calendar.md) (proposal pattern).
5. The contract: [`backend/app/api/CONTRACT.md`](../../backend/app/api/CONTRACT.md) (SSE) and `apps/web/src/lib/api/schema.d.ts` (REST, generated; **never edit by hand**).

## 1. Your worktree (already created for you)
Three folders, side by side:
| Folder | Branch | Who |
|---|---|---|
| `hackumass-lms-agent/` (main checkout) | `dev/soumith` | **Nobody edits here.** Merge target only |
| `hackumass-lms-agent-claude/` | `soumith/claude` | Claude Code |
| `hackumass-lms-agent-codex/` | `soumith/codex` | **You (Codex)** |

You work only in `hackumass-lms-agent-codex/` (made from `dev/soumith`, deps installed, pushed to origin). Separate worktrees = no stepping on each other mid-edit. **Editing the same files is OK; we merge afterwards.**
```bash
cd ../hackumass-lms-agent-codex/apps/web
pnpm test        # should show 30 passing
```
- Commit + `git push` on `soumith/codex` after each verified piece (small commits merge easier).
- Pull Claude's latest with `git fetch origin && git merge origin/soumith/claude` every hour or so; resolve conflicts on your side.
- Final merge: `soumith/claude` and `soumith/codex` → `dev/soumith` (in the main checkout), then `dev/soumith` → `main` at handoff.
- Ignore the stray `.agents/` folder in the main checkout.

## 2. What already exists (don't rebuild it)
Stage 0 (S00 scaffold + S02 API contract) is on `main` (Hari, PR #1). Commit `653d134` on `dev/soumith` adds Stage 1 frontend, **all in mock mode** (MSW), 30 web tests green, lint + typecheck + `next build` clean:

| Area | Files | Notes |
|---|---|---|
| **S30 shell + auth** | `src/app/{layout,page,providers}.tsx`, `src/app/auth/callback/`, `src/app/(app)/layout.tsx`, `src/components/{layout,auth,states}/`, `src/lib/auth/*`, `src/lib/config.ts` | Supabase (Google + magic link) when `NEXT_PUBLIC_SUPABASE_URL/ANON_KEY` are set; otherwise a **demo sign-in** ("Continue with demo data"). `RequireAuth`, sidebar ≥768px / bottom tabs below (`useMediaQuery`) |
| **API client** | `src/lib/api/client.ts` (`api()`, `ApiError`, `configureApi`, `isAbortError`), `src/lib/api/types.ts` | REST types are **re-exports of `schema.d.ts`**. SSE `ChatEvent` union is hand-written from CONTRACT.md |
| **SSE** | `src/lib/api/sse.ts` (`SseParser`, `toChatEvent`, `streamChat`) | Handles split frames, CRLF, unknown events, pre-stream JSON errors, Stop (cancels reader) |
| **Mocks** | `src/mocks/{fixtures,handlers,server,browser}.ts`, `public/mockServiceWorker.js` | Fixtures mirror S03 (COMPSCI 311/320, MATH 235, STATS 315), dates relative to now. Handlers cover Stage 1 endpoints + scripted `POST /chat`. `sseResponse(events, {delayMs, hang})` helper |
| **S32 Today + course** | `src/components/today/*`, `src/components/course/*`, `src/app/(app)/{today,courses/[id]}` | |
| **S33 chat (Stage 1 part)** | `src/components/chat/*`, `src/app/(app)/chat/**` | `chat-state.ts` (pure reducer: `newTurn`, `applyEvent`, `settleStatus`), `assistant-text.tsx` (markdown + citation chips; renderer config is **module-level on purpose**: per-render objects remount the DOM on every delta), `citation-card.tsx`, `status-list.tsx`, `chat-screen.tsx` |
| Placeholders | `src/app/(app)/study/**`, `src/app/(app)/settings/`, `src/app/onboarding/` | Show "Coming soon." **These are yours to replace** (section 3) |
| Tests | `tests/{s00-smoke,s30-shell,s32-today,s33-chat,sse}.test.ts(x)`, `tests/utils.tsx` (`renderWithProviders`, `fakeAuth`, `mockMatchMedia`), `tests/setup.ts`, `tests/next-navigation.ts` (`routerMock`, `navState`), `tests/e2e/*.spec.ts` (not yet run) | |

Run the app in mock mode: create `apps/web/.env.local` with `NEXT_PUBLIC_API_MOCKS=1` (leave Supabase vars empty) → `pnpm dev` → "Continue with demo data".

## 3. Your work (Codex), in order
Specs are still status `Draft`; Soumith has OK'd building from them. Follow each spec exactly, **tests first** (test IDs in test names, confirm they fail, then implement), stay in your files (section 4). If a spec is wrong or unclear: stop and note it in your PR + the devlog; don't silently work around it.

### 3.1 S33 Stage 2: study sets + approvals (demo-critical: "Prep me for the CS 311 midterm")
1. **Chat events.** Extend `chat-state.ts`: `Turn.studySets: StudySet[]` (from `study_set` events) and `Turn.approval: { blocks: StudyBlock[]; summary: string } | null` (from `approval_required`). Today both fall into the `default:` branch.
2. **Inline cards in chat** (`chat-screen.tsx` `TurnView`): one card per study set ("Study plan · 5 days", "Practice quiz · 10 Qs", "Flashcards · 20") linking to `/study/[id]`; the **approval card** listing proposed blocks in local time with **Add** / **Skip** → `POST /study-blocks/decision {block_ids, approve}`; buttons lock after a decision; copy: "Added. They'll show up in your calendar app on its next refresh."
3. **`/study/[studySetId]`**: `GET /study-sets/{id}`. Payload shapes are in **S24** (`plan.days[]`, `quiz.questions[]`, `flashcards.cards[]`, every item has `chunk_ids`). Plan: day list, local checkboxes (localStorage per set). Quiz: one question at a time, MCQ reveal + explanation + citations, short-answer "Show answer", score, retry. Flashcards: flip (click/Space), prev/next (arrows), shuffle, "Got it / Again" piles (local only). Fully keyboard-operable.
4. **`/study`**: list from `GET /study-sets` (`StudySetSummary[]`).
5. **Citations on study items:** S24 says the saved payload includes a resolved `citations` map `{chunk_id: Citation}`, but the **backend mock payload has only `cards[].chunk_ids`** (see `backend/app/api/mock_data.py` `study_set()`). Handle both: use the map if present, else resolve via `GET /citations?ids=`. Reuse `CitationCard` and the chip style from `assistant-text.tsx`.
6. **Mocks:** add MSW handlers + fixtures for `GET /study-sets`, `GET /study-sets/{id}` (one each: plan, quiz, flashcards), `POST /study-blocks/decision`, and a scripted chat variant that emits `study_set` + `approval_required` (order per CONTRACT.md: after last `text`, before `citations`).
7. **Tests:** S33-T07 (quiz), T08 (flashcards), T09 (approval card calls API once + locks), plus a runtime test that `study_set` / `approval_required` events render cards. E2E S33-T11 if Playwright is set up (see gotchas).
8. **Known contract gap (don't change the contract):** reloading a conversation can't show whether blocks were added or skipped, because `Message` only has `block_ids` and there's no "get blocks" endpoint. Render reloaded approvals without the outcome and note it in the devlog ("Contract change proposal P7 pending"). Claude is raising P7 with Hari.

### 3.2 S31 onboarding (simplified for non-technical students on `main`, re-read it)
- Replace `src/app/onboarding/page.tsx` (keep `RequireAuth`). Guided Canvas step: `POST /connections/canvas {token, expires_at?}`, friendly mapping of `invalid_token` etc.; live-login steps via `POST /connections/{platform}/login` + poll `GET .../login/{login_id}` every 2 s; `?reconnect=<platform>` mode (the Today view already links to `/onboarding?reconnect=echo360`); resume at first incomplete step from `/me`. **Plain language:** never show "token"/"sync"/"API" in headings; follow S31's wording.
- Mocks for those endpoints. Tests S31-T01…T06.

### 3.3 S34 settings (Stage 3, only if 3.1 and 3.2 are done)
`src/app/(app)/settings/`. Model choice lives under **Settings → Advanced** (non-technical rule; Gemini is the default model per `docs/decisions.md`).

## 4. Preferred lanes (overlap is allowed; we merge afterwards)
| Owner | Files |
|---|---|
| **Codex** | `src/components/chat/**`, `src/app/(app)/chat/**`, `src/components/study/**` (new), `src/app/(app)/study/**`, `src/app/onboarding/**`, `src/components/connect/**` (new), `src/app/(app)/settings/**`, `src/components/settings/**` (new), **`src/mocks/**`** (Claude won't edit mocks from now on), `tests/s33-*.test.tsx`, `tests/s31-*.test.tsx`, `tests/s34-*.test.tsx`, `tests/e2e/s33*`, `tests/e2e/s31*` |
| **Claude** | `src/app/{layout,page,providers}.tsx`, `src/app/auth/**`, `src/app/(app)/{layout.tsx,today,courses}`, `src/components/{layout,auth,today,course,states}/**`, `src/lib/{auth,config.ts,time.ts,platforms.ts}`, `tests/{s00-smoke,s30-shell,s32-today,sse}*`, `tests/e2e/s30*`, `tests/e2e/s32*`, `playwright.config.ts`, all of `docs/` (devlog, progress, spec index, pitch) |
| **Shared: append-only, small** | `src/lib/api/{client,types,sse}.ts` (add methods/types, don't reshape existing ones), `src/components/ui/**` (`npx shadcn@4.23.0 add <x>` is fine), `tests/utils.tsx`, `tests/setup.ts`, `package.json` + `pnpm-lock.yaml` (say in your commit message which deps you added) |

Edit anything you need; staying mostly in your lane just keeps the final merge small. Mention cross-lane edits in your commit message.

## 5. Environment and gotchas (each of these cost time already)
- **Node:** laptop has Node 24, but the team pins **Node-20-compatible** tooling. Don't upgrade past: Vitest 3.2, Vite 7, `@vitejs/plugin-react` 4, jsdom 26, **MSW 2.15** (MSW 3 needs Node 22), **`@supabase/supabase-js` 2.109** (2.110+ needs Node 22). Check `npm view <pkg>@<ver> engines` before adding a dep.
- **shadcn 4** generates imports from its own `cn` package (Node 22 only). We use `@/lib/utils` (`clsx` + `tailwind-merge`). After `shadcn add`, run: `sed -i 's|import { cn } from "cn"|import { cn } from "@/lib/utils"|' src/components/ui/*.tsx` and make sure `cn` didn't get added to `package.json`.
- **MSW 2** option is `onUnhandledRequest` (MSW 3's `onUnhandledFrame` doesn't exist here). Import `http`, `HttpResponse` from `"msw"`; `setupServer` from `"msw/node"`.
- **jsdom vs Node fetch:** `tests/setup.ts` wraps `fetch` to translate jsdom `AbortSignal`s into Node ones; without it, any fetch with a `signal` throws in tests. Keep it.
- **Abort checks:** use `isAbortError(e)` / `signal.aborted`, never `instanceof DOMException` (cross-realm).
- **react-markdown:** keep `components`, plugins and `urlTransform` as module-level constants (see `assistant-text.tsx`).
- **Next 16 + `cacheComponents`:** pages using `useSearchParams` need a `<Suspense>` boundary (see `src/app/(app)/chat/page.tsx`). Client pages read params with `useParams()`.
- **No `make`, Python or `uv` on this laptop:** `make test` / `make api` don't work here. Run web checks from `apps/web`: `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`. Mock mode replaces `make api`.
- **Playwright:** `pnpm test:e2e` starts its own mock-mode dev server on port 3100 (see `playwright.config.ts`). The browser isn't installed yet: `pnpm exec playwright install chromium` (Claude is doing this; skip if `~/AppData/Local/ms-playwright` has chromium).
- **Windows / Git Bash:** prefix `git show origin/main:<path>` with `MSYS_NO_PATHCONV=1` or paths get mangled. CRLF warnings on commit are harmless.
- **Next.js rewrites `apps/web/AGENTS.md`** when `next dev` runs; commit it if it changes, don't fight it.

## 6. UI rules you must follow (from AGENTS.md / docs/01-vision.md)
- Plain language: no "token", "sync", "MCP", "model", "API" or error codes in the main UI. Buttons say "Try again", "Reconnect Gradescope", "Refresh".
- One clear action per problem; never a dead end. Mobile works at 375 px. Keyboard + `aria-live="polite"` for streaming/status.
- **The UI never builds platform URLs:** links come only from API fields (`source_url`, `url`, `deep_link`). Any URL inside model text renders as plain text (already enforced in `assistant-text.tsx`).
- Writes need a click: study blocks are only proposals until the student presses **Add**.

## 7. Definition of done for each piece
Tests from the spec written first (IDs in names) and passing · `pnpm test && pnpm lint && pnpm typecheck && pnpm build` green · acceptance criteria ticked in the spec · commit + push `soumith/codex` · short devlog note (append under the current Soumith entry: "Codex: …") · PR into `dev/soumith` with what changed, which spec IDs, and anything you couldn't do.

## 8. What Claude is doing meanwhile (don't duplicate)
1. Approving S02 from the frontend side and recording the open follow-ups (P6 sync counts for onboarding, P7 block outcomes on reload, P8 `ModelOption.unavailable_reason`, P9 typed study-set payload / SSE types in OpenAPI) in `docs/progress/soumith.md`.
2. Installing Playwright chromium and running the S30/S32 e2e tests; checking the shell, Today and course pages in a real browser at desktop and 375 px; fixing what breaks there.
3. Devlog entry, progress file, spec index statuses, pitch "What actually works".
4. At handoff: merge your PR into `dev/soumith`, then PR `dev/soumith` → `main` when everything is green.
