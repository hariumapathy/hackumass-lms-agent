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



## 2026-11-25 · Neal's laptop · Codex · S46 immediate WIP review checkpoint
**Done:** S45 committed/pushed `8b569bd`. S46 spec/cases/design/implementation plan and synthetic DB regressions written; partial connector checkpoints from current-feature delegation included.
**In progress / broken:** shared ConnectorContext checkpoint interface and source execution/credential revision fences are not implemented. Initial focused regression run: 3 failed, 2 passed before maxfail; failures reproduce overlapping imports, publication after disconnect and replacement-account status poisoning. This WIP tip is for review only, not deployment.
**Decision:** user explicitly requested pushing unfinished changes immediately for a friend's review. Keep PR34 draft and main unchanged. Do not present S46 as green or complete.
**Next:** implement S46 grant revision/migration, serialization, queue binding and guarded source/status writes; legacy jobs fail closed; connection → secret → runs/jobs lock order. Run focused/full/static checks, update docs, push completion separately. Worker remains paused; running API/web are the earlier checked checkpoint.

## 2026-11-25 · Neal's laptop · Codex · S45 bounded processing repair
**Done:** classified content-free processing failures, four-attempt per-revision ledger/backoff and duplicate-claim guards, worker retry ownership, configuration/permanent/auth stop states and scoped operator resume. Binary sources require Storage; single file access does not expire entire Canvas grant. Failed-source status uses hash guards; credential replacement/auth resume is transactional. Nonblocking stale recovery revalidates current state; bounded legacy post/material repair skips active processors and real metadata discovery has its own finite budget.
**Evidence:** initial14 failures; review regressions caught downloader status mismatch, missing Storage degradation, stale recovery reopening blocked states, busy locks stalling scheduler, stale failure marking new source failed, same-reference auth reset and orphan replacement budget remaining1. Final32 new tests/full676 backend pass/1 optional Storage skip; static checks green. Existing old-chunk tests now expect typed failures and preserve their atomicity assertions. RAG/security review no further blocking issue after fixes.
**Limits:** successful source/index publication, stale-active-worker takeover/disconnect and embedding provenance remain next. No frontend/public API changes; previous102 frontend/6 browser/build checkpoint and real synthetic Gemini G01 remain applicable. Worker paused for DB fixtures; API/web still live. Only additive0005 applied locally; no reset/seed.
**Next:** commit/push S45 separately, restart checked worker/API checkpoint, then RS06 execution/publication fencing as its own spec/test/design/code cycle. S44 pushed1bacbb9; user permits discretionary merges, held until integrated related gates pass. Gemini retained, cost/provider work deferred.

## 2026-11-25 · Neal's laptop · Codex · S44 durable indexing delivery
**Done:** additive private encrypted processing_intents outbox committed with each new/changed source, pending legacy observation recovery, owner/revision/token dispatch leases and ID-only job args. Recovery no longer requires a successful full source fetch. Worker per-intent execution/DB locks and completion guards tolerate duplicate delivery; completed payloads removed, clear-data purges outbox.
**Red/green evidence:** initial6 regressions failed; notification failure and a real Procrastinate doing/replay/retry UniqueViolation exposed2 further defects. Fixed notification finalization and removed unsafe todo queueing lock while retaining execution locks/revision checks.16 new tests pass; full644 backend/1 optional Storage skip, Ruff/format/pyright green. Current-feature re-review no further major defect. Existing frontend102/6 browser/build checkpoint unchanged.
**Live setup:** earlier missing-key report was local configuration, not invalid credentials. Supplied Gemini credential validated and saved only in ignored `.env`; real synthetic chat and app G01 eval passed (1/1, actual get_items,9.72s). API/web HTTP smoke healthy; no fresh live-course/Google verification. Worker paused for DB fixtures. See evals/2026-11-25-gemini-smoke.md. Existing encryption key was absent; local launcher generated one, no retained data reset.
**Scope/gates:** S44 is delivery durability. RS05 failed/stuck processors, RS06 source publication/disconnect, signed refs and Storage orphan/backup recovery remain explicit gates. Only additive0004 applied locally and migration history recorded. User now permits discretionary merges; hold this related foundation until integrated checks/retry gates pass, defer cost/provider work.
**Next:** commit/push S44 separately; restart worker checkpoint, then S45 failed/stuck processing classification/recovery through its own spec/test/design/code cycle. S43 pushed5ff4d95; PR34 stays draft; main untouched.

## 2026-11-24 · Neal's laptop · Codex · S43 source restoration
**Done:** observed removed sources restore presence before content classification; changed course links return active. Identical return retains content hashes/IDs/version/current chunks/processing state and unchanged counters, without requeue. Posts/materials write guarded one-time back events; canonical merge writes back only when a removed item actually becomes live, separate from genuine field changes.
**Evidence:** initial5 DB failures, final9 new cases green incl concurrent restores, live multi-source canonical, incomplete unseen sources, changed deadline/title and submitted state. Full backend628 pass/1 optional local Storage skip; Ruff/format/pyright green. Current-feature review no blocking defect; two suggested concurrency/real-change cases added and pass. No frontend/public contract changes; previous102 frontend/6 E2E/build checkpoint retained.
**Next:** commit/push S43 separately; start and HTTP-smoke local demo; durable indexing intent/recovery as the next separate spec. S42 pushed `4385cb1`; main remains untouched; failed/missing processing remains explicitly unresolved until next feature.

## 2026-11-24 · Neal's laptop · Codex · S42 Canvas listing completeness
**Done:** capped Files listing marks course materials incomplete; module fallback always non-authoritative for absence. Pagination rejects malformed/non-list JSON instead of silently inferring emptiness. Existing per-course/table removal skip retained; no schema/API/SSE/seed changes or live calls.
**Evidence:** initial13 regressions failed/4 controls passed.20 new cases now pass, including99/100/101, cross-page exact-cap/overflow, missing module details, two-pass DB cap/module/partial403, genuine complete removal and malformed/partial failure.66 focused checks passed before final2 page-boundary additions; final backend619 pass/1 optional Storage skip and all static checks green. RAG review no blocking defect. Frontend unchanged from102/6 E2E/build checkpoint.
**Gotcha:** module discovery retains all earlier course materials (including syllabus under existing table-level grouping), not full file discovery or permission revocation. S41 pushed `73ffe9a`; implementation PR34 stays draft/unmerged.
**Next:** commit/push S42 separately, then identical-content restoration through its own spec/test/design/code cycle. Keep Gemini; preserve imported local data; server restart before final handoff still pending.

## 2026-11-24 · Neal's laptop · Codex · S41 current-source retrieval
**Done:** current lexical/vector/hybrid search and direct material reads exclude owned removed parents before candidate limits; historical citation lookup unchanged. Internal read/overview results retain changed/current source status. No public API/SSE/schema/seed changes; Gemini unchanged.
**Evidence:** initial6 source/metadata regressions failed, historical resolution guard passed. Final11 new cases (including nearest-vector crowding, foreign-parent mismatch and changed posts) and full backend599 pass/1 optional Storage skip; Ruff/format/pyright green. Optional actual local Storage check passed at S40 separately. Previous frontend102/6 E2E/build remains applicable; no frontend change. Current-feature RAG review found no blocking defect.
**Next:** commit/push S41 separately; Canvas incomplete-listing/removal safety next through its own spec/cases/design/plan/red-tests/code workflow. S40 pushed `6b970ee`; PR34 remains draft/unmerged. Reapply no resets and respect recorded Storage failure/backup deployment gates.

## 2026-11-24 · Neal's laptop · Codex · S40 complete saved-data cleanup
**Done:** additive internal migration0003, durable pending/complete generation, resumable rows/files/job cleanup, worker recovery and acknowledgment-safe running-job redaction. Auth retained. Protected request/SSE/tool leases share the guarded DB session; active child leases drain before release; escaped tasks are refused. Old sync/merge/login attempts cannot revive deleted work; stale scheduler and public feed paths recheck ownership. Settings retains privacy retry when /me fails.
**Red/green evidence:** first6 DB cases failed against old code; further red regressions caught old login/merge, duplicate windows, killed-lock writes, child lease writes and inaccessible Settings retry. Final33 focused tests pass; full backend588 pass/1 optional skip, then actual local Storage synthetic two-user round-trip passed separately. Frontend102 tests,6 mock browser E2E, build/lint/types and backend Ruff/format/pyright pass. Independent security re-review no further blocking defect.
**Review/operations:** new internal schema proposal is separate/unmerged; only additive0003 applied to local retained DB and migration history, no reset/seed. Requires direct/session DB pooling; user-session admission8 vs pool10. External Storage upload failure/orphan reconciliation and backup expiration/restore remain explicit launch gates, see deployment/data-deletion.md. No real student's data deleted, no secrets logged or committed.
**Next:** commit/push S40 separately; then next individual sync/RAG fix (removed-source retrieval). Main remains untouched; Gemini retained. Server restart/HTTP smoke at stable handoff still required.

## 2026-11-24 · Neal's laptop · Codex · S39 browser account isolation
**Done:** AuthProvider owns a per-identity QueryClient and keyed UI subtree; sign-out/identity change cancel/fence REST+SSE, clear old query/mutation caches and reset local drafts/history. Same-user refresh retains state. Late bootstrap/401 cannot overwrite/logout a newer identity. Security review found pending logout could resurrect A via token refresh; shared logout sequencing/non-null event suppression plus two red regressions close it. No server contracts/dependencies changed.
**Evidence:** original synthetic two-user test visibly showed user B with A's cached data/draft (6/7 red). Final9 S39 tests green; 24 focused auth/SSE, full101 frontend, lint/types/build and6 mock browser E2E green. Last backend baseline569 pass/1 skip/1 xfail remains applicable; no backend change. Security re-review no additional critical defect.
**Next:** commit/push this fix, then complete data deletion as its own spec/test/design/implementation cycle. S37/S38 remote verified; PR34 draft/unmerged; Gemini unchanged.

## 2026-11-24 · Neal's laptop · Codex · S38 JWT issuer binding
**Done:** server-configured exact JWT issuer required for HS256/JWKS tokens; default SupabaseURL/auth/v1 and validated trusted override for custom deployments. Synthetic fixtures carry realistic issuer, old negative/expiry/signature/cache checks retained. No API/schema/SSE changes, no live credentials. Red API tests showed wrong issuer accepted before fix; then 45 focused auth checks passed. Independent current-feature security review found no critical defects.
**Checks:** full backend569 pass / 1 skip / 1 xfail; ruff/format/pyright green. S37 already committed `87617f2` and verified on GitHub despite SSH push acknowledgement failure; branch tracking repaired via HTTPS, no force push. Implementation draft PR #34 open/unmerged.
**Next:** commit/push S38 separately, then browser account-cache isolation. User said keep going without routine questions; all main merges remain forbidden until explicitly authorized. Gemini unchanged.

## 2026-11-24 03:45 ET · Neal's laptop · Codex · branch codex/post-hackathon-implementation
**Authorization:** user now approves sequential spec → test cases → design/implementation plan → failing tests → code → checks → commit/push, one fix at a time, overnight; Gemini retained; never merge main until user explicitly says done. Review branch includes planning commits, main unchanged. Handoff before 07:00 ET or earlier if usage ends.
**S37 done:** explicit production API/worker config guard, secret-safe diagnostics, disabled browser mode, no hosted→local fallback. Initial 32 failing tests then green; current-feature security review found noncanonical IP bypass, libpq authority overrides and CORS canonicalization; 11 new red regressions then all 43 focused green. Full suite checkpoint 546 pass/1 skip/1 xfail before final 11 regressions; final full repeat: 557 pass / 1 skip / 1 xfail. Frontend baseline92 green; static checks green. No DB/API/SSE/seed contracts changed. See S37 + deployment/production-configuration.md.
**Setup/research:** pinned make setup succeeded. Docker was stopped; CUA launch failed/stalled, Docker Desktop CLI startup succeeded without resetting volumes, local integration checks restored. Security skill installed from reviewed pinned official source; tooling/MCP/eval research in research/post-hackathon-dev-tooling.md. No MCP accounts/telemetry/exporters installed.
**Next:** commit/push S37; JWT issuer binding as the next individual fix, then browser account-cache isolation and deletion, then sync correctness. Don't prewrite batches of future specs. Keep checkpoints and exact red/green evidence per fix; restart/verify demo server at stable handoff.

## 2026-11-23 · Neal's laptop · Codex · course-chat / student UX planning amendment
**Scope:** user requests General Chat plus course-specific chats/projects with aligned context, memory and tools; make the app easy for ordinary students, modern/responsive/maroon; find UI skills and add everything to design/implementation plans. Continued on `post-hackathon-plan/changes`; application code remains untouched.
**Done:** [course chats and UX brief](post-hackathon/course-chats-and-ux.md), integrated design and P15/P16 implementation/test gates, packet/handoff/progress/index updates. Server-enforced course/project scope (not prompt hints), explicit General, optional projects, inspectable student-approved memory, migration of existing S36 chats, source/permission/canonical-merge boundaries. UX includes plain labels, visible scope, phone composer, SSE/scroll/Stop, task-based novice usability and accessibility.
**Research:** inspected primary Anthropic frontend-design, Vercel interface-guideline/React-performance skills; current OpenAI curated catalog; assistant-ui thread/composer patterns; official UMass #840028 palette and WCAG2.2. Candidates recorded with links; no skill/dependency installed/copied. Existing Tailwind/shadcn and SSE stack retained in the proposal.
**Validation:** documentation link/whitespace/content checks; existing baseline from preceding packet remains 419 offline backend / 92 frontend + lint/types. No new application tests, UI mockup/runtime change or live check; P15/P16 tests are plans, not implemented.
**Next:** review course/general/project navigation and memory policy, prototype/test novice tasks, then Ready specs/contracts and failing tests only after implementation approval. Keep PR #33 draft/unmerged; no server restart needed for documentation.

## 2026-11-23 · Neal's laptop · Codex · post-hackathon planning · branch post-hackathon-plan/changes
**User scope:** hackathon finished/presented; plan a deployable student/professor product, Google sign-in, optional LMS/course setup + later additions, Gmail, Google Calendar/ICS, affordable models and RAG/sync audit. Explicitly **no application code yet**. Three audit agents authorized. Latest remote main fetched: `be13793`; clean checkout branched from it.
**Done:** [post-hackathon packet](post-hackathon/README.md): three source audits, consolidated design, P00–P14 implementation/test/dependency plan, official Google/UMass/provider research and model/hosting cost scenarios. Cross-reviewed for connector/auth correctness, inline-file security and consistent 120-case retrieval benchmark. Updated stale documentation entry points. All proposed features remain Draft; no schema/API/seed changes, deployment, purchase or live-account access.
**Key findings:** local headed login cannot serve hosted GS/Piazza; incomplete deletion/cache-transition risks; production demo defaults; import caps/restoration/races and stranded indexing; removed-source retrieval/embedding identity; usage not persisted. Evidence and release gates in the audits, not reproduced exploit claims. Existing Calendar/Piazza/UMass UI/Sessions already on main. `origin/dev/soumith` has a non-ancestor historical patch but no app/test-path net diff; not merged.
**Review checkpoint:** packet commit `679c1d6` pushed; [draft PR #33](https://github.com/hariumapathy/hackumass-lms-agent/pull/33) open and intentionally unmerged.
**Validation:** existing offline backend 419 pass / 1 skip / 96 integration deselected; frontend 92 pass; ruff lint/format, pyright, ESLint and frontend types pass. DB integration, production build, E2E, live providers/accounts, load and semantic benchmark not run. Docs-only scope; prior demo counts not treated as fresh evidence.
**Next:** 1. User/team reviews cohort/budget, launch platform minimum, eligibility/professor scope, calendar directions and provider/Google approval ownership. 2. Convert approved P packages into narrow Ready specs + contract proposals; follow design → implementation plan → failing tests → code → verification → separate commits. 3. Implement only after go-ahead; first isolation/deletion and sync correctness/recovery, then staging and Google identity/selection. Start external Google/vendor review early.
**Handoff:** [exact next-agent instructions](post-hackathon/handoff.md). Stay on review branch; do not self-merge. No UI change/server restart in planning. Do not reset existing local/production data; never copy demo secrets. Node default is 18 here; audit used installed Node26 and no-experimental-webstorage option. Pricing checked 2026-11-23, not a binding quote.

## 2026-11-15 03:00 ET · Hari's laptop · Claude Code (Opus 5.5) · branch hari/sessions · Session A (parallel with B)
**Done:** **S36 Sessions** (spec + 12 new tests, tests first). The Study tab is now **Sessions** (sidebar + phone tabs): each chat with its flashcards / quiz / plan chips; "Saved study sets" lists sets whose chat was deleted. Chat rows (Sessions page + chat side list / phone "Past chats") have a **…** menu: **Rename** inline (Enter saves, Esc cancels) and **Delete** with the confirm text "Delete this chat? Its flashcards and quizzes stay in Sessions." **New chat** button in the phone chat header. Reopened chats show their study sets again. API (additive): `GET /conversations` includes `study_sets`, `StudySetSummary.conversation_id`, `PATCH`/`DELETE /conversations/{id}` (user-scoped, 404 otherwise); runtime saves sets with the run's conversation id (one line in `runtime.py`). `/study` redirects to `/sessions`; `/study/[id]` has "Back to Sessions" + "Open the chat". Polish: loading skeletons, empty states, no overflow at 375 px (study card fix), prefilled chat box focused. Checked in the browser on the real-data stack at laptop width and 375 px (rename, delete, chips).
**Shared files touched (small):** `schemas.py`, `CONTRACT.md`, `lib/api/*` (make types), `src/mocks/*`, `runtime.py` (one line), new route `app/(app)/sessions/`.
**State:** 488 backend + 88 web tests, lint, types green.
**Gotchas:** the browser pane can hold a stale Supabase session for a user that no longer exists in the local DB → `/me` 500 (FK) and `/chat` 401 sign-out; sign in again. A test account `sessions-test@example.com` now exists in the local DB with 2 saved study sets (harmless; not Hari's data). Menus open by mouse don't pre-highlight an item (Radix): keyboard users open with Enter.
**Next:** 1. merge Session B's PR and re-run tests on main; 2. rehearse the 3-minute demo with Sessions (ask for flashcards → open Sessions → chips → rename the chat); 3. Devpost text + video before 09:00.

## 2026-11-15 02:05 ET · Soumith's laptop · Claude Code (Opus 5.5) · branch friend/submissions-pdf-web · Session B (split doc)
**Done (tasks 1 + 2 of docs/handoff/split-2026-11-15.md, Session B):**
- **Submitted work never shows as Overdue** (`8b720cf`). Canvas assignments are fetched with `include[]=submission`, and Gradescope's status column/score is read. Both store `item_sources.raw.submitted` (no schema change). `Item.submitted` is new on `/today`, `/items` and the agent's `get_items`. Overdue skips submitted items; rows show a SUBMITTED badge. A resync updates the flag even when the content hash is unchanged (`sync/pipeline.py`, small edit). **Live:** real Canvas account (`live@example.com` on this laptop), one sync → Overdue 5 → 2. Rule: graded-as-missing doesn't count; excused does.
- **In-app PDF viewer for citations** (`2fd6748`). `GET /files/{material_id}` (new `routes/files.py`) streams the student's own stored original (row-scoped; another student's id → 404 and storage is never read). Citations carry `file_id` only for stored PDFs. The citation card gets **View** (new `components/files/file-viewer.tsx`): it fetches with the Bearer token into a blob URL and shows the browser's PDF viewer in a dialog at `#page=N`, with "Open in Canvas" as the fallback. No new library. **Live:** a real lecture PDF opened at p. 2/61 inside the app (laptop + 375 px).
- Tests: 508 backend (1 skip, 1 xfail) incl. `test_submitted_db.py`, `test_files_db.py`, `test_files_storage.py`; 84 web incl. S32-T11, FV-T01..03; ruff/pyright/eslint/tsc clean.
- Shared-file edits (small): `api/schemas.py` (`Item.submitted`, `Citation.file_id`), `api/routes/__init__.py` (register `files`), `agent/citations.py` (pass `file_id`), `api/CONTRACT.md` (Citation line), `lib/api/openapi.json` + `schema.d.ts` (regenerated: **Session A, re-run `make types` after merging**), `mocks/fixtures.ts` (`submitted`), `sync/processing/storage.py` (`download()`), decisions, pitch table, S32 rule 6.
**Not done:** PR not opened by the agent (`gh` is not installed on this laptop). **Task 3 (web search) dropped** by Soumith (decisions.md): course sources only.
**State of main:** Session A's PR #30 (S36 Sessions) merged into main as `9b0e67c`. This branch merged it (`c8b02c4`): no code conflicts, docs conflicts kept both sides, `make types` gives no drift. On the merged code: **514 backend** (1 skip, 1 xfail), **92 web + 6 e2e**, production build, ruff/pyright/eslint/tsc all green. PR to open/merge: https://github.com/hariumapathy/hackumass-lms-agent/compare/main...friend/submissions-pdf-web?expand=1
**Next (in order):** 1. Merge the PR above (green; already contains main). 2. Everyone: `git merge origin/main`. 3. Demo: after a Canvas resync, Today's Overdue only shows work the student hasn't handed in; ask about a lecture → citation → **View**.
**Gotchas:** Existing synced items only get `submitted` on the next sync (click sync / wait for the worker). The browser pane's PDF viewer takes 1–2 s to paint a 7 MB file after the spinner disappears. Mobile Safari may not show PDFs inline; "Open in Canvas" stays in the dialog.

## 2026-11-15 02:40 ET · Hari's laptop · Claude Code (Opus 5.5) · branch hari/sw-fix-and-prompts · HANDOFF (this session's context is nearly full)
**Done:** Hari ran the real-data demo; feedback split into two parallel sessions: **docs/handoff/split-2026-11-15.md** (Session A: Sessions tab + chat rename/delete + chat polish; Session B: submitted work out of Overdue, in-app PDF viewer for citations, optional web search). Fixed: localhost:3000 broken in Hari's regular Chrome but fine in incognito = leftover MSW mock service worker from earlier mock-mode testing kept serving fake API answers; real mode now unregisters it on load (test added). Manual fix for an already-affected browser: DevTools → Application → Service workers → Unregister, or Clear site data.
**Next:** paste the two prompts from the split doc into the two sessions.

## 2026-11-15 02:20 ET · Hari's laptop · Claude Code (Opus 5.5) · branch hari/real-data-demo
**Done:** **Real-data demo mode** for judging/video (Hari: "only my stuff, no mock data"): `make demo-real-api|worker|web` (+ optional `make demo-real-wipe`). Real mode = `CHAT_MODE=agent` (never the scripted fake answer), Gemini embeddings for real files, Canvas host `umamherst.instructure.com`, refuses to start without `GEMINI_API_KEY`. Audit: every route already reads only the DB in DB mode; the only leak was the scripted chat fallback. **Bug fixed:** Gemini embeddings crashed on every call (response has no `index`) → real files could never become searchable; regression test + live check (2 × 1536). Coverage no longer tells students to connect Echo360 (not offered). Dry run with a fresh account: onboarding step 1, empty Today, real agent answers "nothing connected yet", Canvas guide links the right host. Hari's local `.env` had `CANVAS_BASE_URL=https://umass.instructure.com` (wrong host) and `EMBEDDINGS_PROVIDER=openai` (unsupported): fixed the Canvas line; real mode overrides both.
**Next:** Hari runs docs/demo-runbook.md "⭐ Real-data demo" with his own email + fresh Canvas code; record the demo video; Devpost text before 09:00.

## 2026-11-15 01:50 ET · Hari's laptop · Claude Code (Opus 5.5) · branch hari/gradescope-live
**Done:** PR #26 (UMass UI) merged. **Gradescope live-verified on Windows** with Hari's account: login window → 258 imported, 238 assignments merged across 18 courses, shown on Today and answered in chat (S14 "Live verification on Windows"). Fix: courses with no upcoming work fold under "Show other courses (N)" (sidebar + Today) so years of past terms don't clutter navigation. 79 web tests.
**Gotcha:** don't run `pnpm build` while `pnpm dev` is running in the same folder: the dev server keeps working but loses its CSS (no maroon/yellow). Restart the dev server, or use `make demo-web` (production).
**State:** demo account now mixes seeded demo data and Hari's real Canvas-less Piazza/Gradescope data (two "COMPSCI 311" courses). For a clean real-data demo, sign in with a different email (runbook §5).

## 2026-11-15 01:30 ET · Hari's laptop · Claude Code (Opus 5.5) · branch hari/umass-ui
**Done:** PR #25 merged (Piazza live-verified, Windows live-login fixes). **S35 UMass UI** on `hari/umass-ui`: official palette (maroon `#840028`, black `#212721`, yellow `#FFC72C` highlight only), Fraunces + Geist, new sign-in, app frame, Today, Chat (follow-scroll + Jump to latest), Study/Settings polish; light/dark; 375 px + laptop checked in the browser; live Gemini chat with citation popovers works in the new UI. Prompt: plain-text math (no LaTeX). 78 web + 322 backend unit/runtime tests; lint, types, production build green. Details + pitfalls: S35 "Implementation".
**Next:** merge `hari/umass-ui`; rehearse the 3-minute demo with `docs/demo-runbook.md`; final Devpost text before 09:00 (code freeze 08:00).

## 2026-11-15 00:40 ET · Hari's laptop · Claude Code (Opus 5.5) · branch hari/test-calendar-piazza
**Done:** synced main (`10c3de8`, calendar + Piazza merged by Soumith); 477 backend + 75 web tests green. **Calendar re-verified live** (chat proposal → Add → downloaded .ics has the session at 3 PM ET). **Piazza live-verified with Hari's real account** after fixing the Windows live-login bugs (details: S17 "Live verification", live-test-bugs.md). Change summaries now plain language.
**Gotchas:** stop `make demo-worker` before running integration tests (it grabs queued test jobs: S13-T06 fails otherwise). An old orphaned `next dev` (PID from an earlier session) can hold :3000 and crash ("Jest worker…" 500s): kill it in Task Manager (node.exe) before `make demo-web`.
**Next:** merge this branch; UMass UI branch (S35).

## 2026-11-15 00:30 ET · Soumith's laptop · Claude Code (Opus 5.5) · HANDOFF (Soumith pauses; next laptop continues)
**Hour:** ~H28. Final submission **Sun 09:00**, code freeze **08:00**, judging 12:30.
**Done this session:**
- **S25 calendar: done + live-verified** on `codex/calendar-piazza-ui` (`22bf8aa`, pushed). Details in the entry below and in S25.
- **S17 Piazza branch `neal/s17-piazza`:** merged the calendar branch in (conflicts in pyproject/notices/devpost/S17 resolved keeping both), relocked. **Connect Piazza** added to Settings + onboarding (Piazza login wording), **Echo360 hidden** everywhere (`CONNECTABLE_PLATFORMS` in `apps/web/src/lib/platforms.ts`), tests first (S31-T09, S32-T10, S34-T01, e2e S31-T05/T06). 477 backend / 1 skip / 1 xfail with DB; web 75 + 6 e2e; lint/format/pyright/eslint/tsc clean. Docs: S17, spec index, pitch, live-test-bugs, decisions, feature-work-plan.
- Soumith approved merging both branches into main on Neal's behalf (decisions.md).
**Not done / not verified:**
- **Live Piazza login + import never ran** (session ended at the Canvas step of a fresh `live@example.com` account). Pitch marks Piazza 🟡 "don't demo live until verified".
- Manual import of the downloaded `.ics` into Google/Apple Calendar.
- PRs: `gh` was not logged in on this laptop, so PRs were **not opened by the agent**; Soumith opens/merges them on github.com (links in the final message / below).
**State of main:** `0176e57` (unchanged). To merge, **in this order**: 1) PR `codex/calendar-piazza-ui` → main; 2) PR `neal/s17-piazza` → main (contains the calendar commits too, so after #1 its diff is only Piazza + UI). Then `dev/soumith` merges main.
- Calendar PR: https://github.com/hariumapathy/hackumass-lms-agent/compare/main...codex/calendar-piazza-ui?expand=1
- Piazza PR: https://github.com/hariumapathy/hackumass-lms-agent/compare/main...neal/s17-piazza?expand=1
**Next steps (in order) for the next laptop:**
1. `/start`, confirm both PRs are merged into main (merge them if green and still open).
2. **Live Piazza check** (S17 "UI + verification" section): demo-runbook stack, a non-demo account, Settings → Connect Piazza, the student logs in themselves; check posts show on Today/course pages with working links and the chat can cite one. Record results in S17 + pitch. If it fails, keep Piazza hidden for the demo (remove it from `CONNECTABLE_PLATFORMS`).
3. Real Canvas on that same account (student pastes their own code in onboarding), then **rehearse the 3-minute demo** (pitch.md) end to end incl. calendar: ask to schedule a study session → Add → Settings → Download calendar.
4. Optional: import the `.ics` into a test Google Calendar (calendar-runbook.md); S35 UI polish only if time remains before 08:00 freeze.
5. Devpost: final text must match pitch "What actually works" (calendar ✅, Piazza only if step 2 passes, Echo360 future work).
**Gotchas (Windows):** see the 23:40 entry: killing `uvicorn --reload` orphans its worker (`spawn_main(parent_pid=…)`) which keeps serving :8000 with **old code**: after any branch switch, kill every python `uvicorn|spawn_main|app.exe` process and check `netstat -ano | findstr :8000`. `supabase_vector` restart loop is harmless. Docker CLI may not be on PATH (`%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin`). Stop the worker during `pytest` with the DB. Strip BOMs if editing docs with PowerShell 5. Secrets pasted in chat this session (Canvas token, Gemini key, Supabase secret) should be **rotated after the event**; only the Gemini key + Supabase secret are in this laptop's git-ignored `.env`.

## 2026-11-14 23:40 ET · Soumith's laptop · Claude Code (Opus 5.5) · branch codex/calendar-piazza-ui → main
**Hour:** ~H27 (final submission Sun 09:00, freeze 08:00, judging 12:30).
**Setup:** this laptop now has uv + Python 3.12 + make + Docker Desktop + gh; local Supabase via `make demo-db`-equivalent; API/worker/web from `scripts/demo-local.sh` with real Gemini.
**Done (S25 live end to end):** 453 backend (1 skip, 1 xfail) with DB; web 73; lint/format/pyright clean. In the browser as `demo@example.com`: Settings shows Download calendar (local feed); chat proposal → feed unchanged (24) → **Add** → 25 events, correct UTC; second proposal **Skip** → stays out. Fixed: card "Add 1 study sessions?" → "Add this study session?"; AI told students to approve "in your calendar" → tool result + prompt say "click Add below"; onboarding Download counts as added. Soumith approved merging on Neal's behalf (decisions.md).
**Gotchas:** `uvicorn --reload` under OneDrive did not reload, and killing the reloader on Windows **orphans the worker** (`spawn_main(parent_pid=…)`), which keeps serving port 8000 with old code. Check `netstat -ano | findstr :8000` and kill every python child after restarts. `supabase_vector` restarting is harmless on Windows (needs Docker TCP 2375; only Studio logs). PowerShell 5 `Set-Content -Encoding utf8` adds a BOM: strip it.
**Next:** 1. PR this branch → main, merge. 2. `neal/s17-piazza`: merge main, DB tests, live Piazza login (Soumith logs in), PR, merge. 3. Remaining to-dos from live-test-bugs.md / S35.

## 2026-11-14 22:38 ET · Neal's laptop · Codex · branch codex/calendar-piazza-ui
**Workflow / review:** latest user instruction replaces main-only work: design plan → implementation plan → failing feature tests → code → checks → separate feature commit, all on one review branch. No merge before user review. Planning/handoff checkpoint `f00a00f` pushed. Keep this entry current before approaching any usage limit.
**Done:** prior main `0176e57` includes live Gradescope verification and polished Devpost copy (`16c906b`) plus teammate queue-isolation fixes. Gradescope imported 20 courses / 238 assignments / 186 dated; independent five source-page date checks remain. S25 implemented: private ICS, approval persistence, actual agent tool, owner/overlap guards, DST validation, token rotation, log redaction, honest local-download UI. No schema/API shape changes. See S25 and calendar-runbook.md.
**Validation:** 452 backend passed / 1 skipped / 1 expected failure; then added an actual proposal-tool streaming test and reran its runtime suite (16 passed). Frontend 72 passed; six browser tests; lint/format/types and production build passed. Calendar manual Google/Apple import and public subscription still pending, explicitly not claimed. Worker paused for full DB tests and resumed with `make demo-worker`.
**In progress:** Calendar feature commit/checkpoint; S17/S35/S18 have planning documents only, no Piazza/UI/Campuswire implementation claim.
**Next (exact order):** 1. Finish/push S25 feature commit, then real UI approval/feed smoke if time. 2. S17 saved-session/read-only spike; inspect upstream before reuse, implement from failing fixtures if feasible, request human login only when needed. 3. S35 UMass UI, responsive/scroll/SSE checks. 4. S18 Campuswire feasibility. Keep docs/pitch/devpost.md ready for tonight's 23:59 draft deadline.
**Handoff gotchas:** stay on `codex/calendar-piazza-ui`, never self-merge despite default relay instructions. Use Node 26 on this laptop and `NODE_OPTIONS=--no-experimental-webstorage`; Python via uv. Local Supabase holds live imports: never run demo-db/db-reset. Pause live worker for queue-mutating integration tests, resume afterward. Secrets exist only in ignored local configuration/encrypted DB. Production web needs restart after a new build; browser pages may need reload. Remaining bugs in live-test-bugs.md. UI reference research and skill candidates are recorded in S35; nothing installed. Handoff must include current commits, dirty state and exact next test; never mark pending manual checks complete.

## 2026-11-14 22:11 ET · Neal's laptop · Codex · branch main · live-test inventory
**Done:** User requested a compiled bug list rather than a video. Added `docs/live-test-bugs.md`: ten resolved demo issues and six remaining findings, with live observations separated from code-confirmed gaps and the unproven account-switch cache risk. Replacement Canvas token accepted through the UI; refresh finished and Today showed the fresh timestamp. No credentials recorded in files or logs.
**Next:** P1 complete Storage/job cleanup in Delete my data; reproduce account-switch cache retention. Then S25 calendar/approval persistence and hide the unimplemented Echo360 connector. See the report for priorities/evidence. No implementation changes in this follow-up; previous green test/build results remain applicable.

## 2026-11-14 22:00 ET · Neal's laptop · Codex · branch main (explicit user request)
**Hour:** ~H25; Devpost draft due 23:59 tonight, final Sun 09:00, code freeze 08:00.
**Done:** S32/S23 database dashboard integration; S13-T06 disconnect; S10 merge priority/readiness and unreadable-credential recovery; UI refresh on import completion; production demo server; Google button opt-in. Live Canvas → eight courses → real Today/course pages → Gemini deadline answer and a cited midterm-scope answer (syllabus page + announcement), verified in the browser. No real data or credentials added to fixtures/git. Tests were written failing-first for the DB dashboard, disconnect, cache refresh, merge readiness/priority and unreadable credential fixes.
**Decisions / corrections:** original repo used the wrong Canvas hostname. Corrected defaults, guide and docs to `umamherst.instructure.com`, confirmed via UMass IT. No schema or API response changes. Details in decisions.md and owning specs.
**Roadblocks resolved:** old local Supabase callback configuration required a restart without resetting data; an old API was using different auth settings, restarted with `make demo-api`. Large initial file queue delayed the merge, so merges now get manual priority. Old unreadable credentials no longer leave runs queued forever.
**Validation:** 440 backend pass / 1 skip / 1 expected failure; 71 frontend pass; 6 browser tests; all lint/format/type checks and production build green. Dedicated live account is separate from seeded backup. Demo uses fake embeddings with keyword retrieval and real Gemini chat.
**State of main:** demo fixes committed and pushed as `4d64086` (remote at start `1b882c7`). Final manual Refresh succeeded: 323 unchanged records, 125 canonical deadlines; Today changed from updating to fresh without a page reload. Local API + worker + production web are the demo stack. Hosted Supabase not used.
**Next steps (in order):** 1. Rehearse live Canvas flow via demo-runbook.md. 2. S25 is still stubbed: skip calendar/approval-persistence demo steps until built. 3. Manual Gradescope login/Duo check. Devpost draft deadline still applies.
**Gotchas:** `make demo-db` resets all local data; do not run it after live imports unless intentional. `nvm use 26` on this laptop (default Node 18 cannot build Next); `NODE_OPTIONS=--no-experimental-webstorage` for frontend tests. Pause the worker during integration tests that manipulate the queue. Frontend public settings require a rebuild.

## 2026-11-14 21:30 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari · HANDOFF: demo gaps found by Hari (fix these first)
Hari ran `docs/demo-runbook.md` in a fresh clone: UI loads, but the demo feels stale. Root causes and fixes, **in this order** (Hari's agent hit its usage limit; next laptop please take these):
1. **Today / course pages always show the S02 mock semester**, even in DB mode: `backend/app/api/routes/dashboard.py` (`/today`, `/courses`, `/courses/{id}`, `/items`, `/changes`, `/changes/seen`, `/citations`) still return `mock_data`. Wire them to the DB when `get_settings().data_source == "db"` (same pattern as `/me` in `routes/account.py`; reuse `app/db/repositories/agent.py` queries: `list_items`, `list_changes`, `list_courses`, `chunks_by_id` + `app.agent.citations.resolve_rows`). Without this, a real Canvas connect only shows up in **chat**, never on Today. Biggest demo gap.
2. **Disconnect does nothing**: `DELETE /connections/{platform}` in `routes/connections.py` is still the S02 stub (204, no change), so Settings keeps showing "connected". In DB mode: set `connections.status='disconnected'` and delete its `connection_secrets` row (repository fn with `(conn, user_id, platform)`). Then Settings shows Connect again, and the Canvas token step can be used.
3. **Real Canvas test**: `POST /connections/canvas` is real (stores encrypted, queues the sync). It needs `make demo-worker` running to actually pull data. Then item 1 makes it visible. Use a **fresh** token. Real files are embedded with `EMBEDDINGS_PROVIDER` (demo default `fake` → keyword search only; for real data start api/worker with `EMBEDDINGS_PROVIDER=gemini`).
4. **Slow page switches** ("Rendering…" corner badge): that's Next.js **dev mode** compiling each page on first visit. For the demo, change `demo-web` in `scripts/demo-local.sh` to `pnpm build && pnpm start` (production server, fast navigation). Keep `make web` as dev mode.
5. **"Continue with Google" is not set up**: it needs a Google OAuth provider in Supabase (`supabase/config.toml` `[auth.external.google]` + client id/secret, and on the hosted project). Until then, **email link is the only working sign-in** (local inbox at http://127.0.0.1:54324). Either configure it or hide the button for the demo (Soumith).
**What's real today:** email-link sign-in; `/me` profile; chat with the real Gemini agent on the DB (deadlines, materials, citations, flashcards); Connect Canvas API + worker sync (S11/S12, untested with a live token); sync status. **What's still mock:** Today, course pages, items, changes, citations panel, disconnect, Google sign-in.

## 2026-11-14 20:30 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari · HANDOFF (Hari's backend is done for the MVP)
**Done since 20:25:** `POST /connections/canvas` wired to Neal's `connect_canvas` (DB mode): bad token → 400 `invalid_token` with a plain message; good token → stored **encrypted**, first `connect` sync queued (S11-T12, `tests/integration/test_s11_connect_route_db.py`). `POST /sync` + `GET /sync/status` real in DB mode. `ENCRYPTION_KEY` generated in Hari's local `.env` (API and worker must share it). Tests never get the hosted secret key. **432 backend tests pass with the local DB; lint clean.**
**Verified on a real server** (uvicorn `--reload`, `DATA_SOURCE=db`, local Supabase, real Gemini): local-Supabase JWT accepted, `/me` + `/sync/status` from the DB, `POST /chat` streamed run_started → 4 status → text → citations → done, conversation saved.
**State of main:** PR #16 (dev/hari) green locally, waiting for Hari's merge. Everything else from Hari is on main.

**Update 20:45 ET:** the steps below are now one command each: see **[demo-runbook.md](demo-runbook.md)** (`make demo-db`, `make demo-api`, `make demo-worker`, `make demo-web`). Verified in a browser: email-link sign-in (local Mailpit) → Today → chat answered by Gemini with citation chips. Fixed `supabase/config.toml` redirect URLs (`localhost:3000/**`), which had broken the local email sign-in.

### Run it yourself on real data (manual version; prefer the runbook)
1. `make setup` then `make db` (local Supabase; first run downloads images).
2. Seed the demo student into the LOCAL DB:
   `cd backend && DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_SERVICE_ROLE_KEY= uv run app seed --embeddings fake --reset`
3. API in DB mode against the local stack (one terminal):
   `eval "$(npx -y supabase@3.1.0 status -o env | grep '^JWT_SECRET=')"; cd backend && DATA_SOURCE=db EMBEDDINGS_PROVIDER=fake DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_JWKS_URL=http://127.0.0.1:54321/auth/v1/.well-known/jwks.json SUPABASE_JWT_SECRET="$JWT_SECRET" uv run uvicorn app.main:app --reload --port 8000`
4. Sync worker (second terminal, same env vars as step 3): `uv run app worker`. Needed for Canvas connect to actually pull data.
5. Web app: `apps/web/.env.local` with `NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321`, `NEXT_PUBLIC_SUPABASE_ANON_KEY=<PUBLISHABLE_KEY from npx -y supabase@3.1.0 status>`, `NEXT_PUBLIC_API_URL=http://localhost:8000`; then `make web`. Sign in as `demo@example.com` / `demo-password-311` (seeded) or a new account.
6. Real Canvas: in the app's Connect Canvas step, paste a **fresh** Canvas token (Canvas → Account → Settings → New Access Token). The worker syncs your real courses; then ask the chat. (For real embeddings use `EMBEDDINGS_PROVIDER=gemini` in steps 2–4, without `--embeddings fake`.)
7. Evals on the seed: `cd backend && EMBEDDINGS_PROVIDER=fake DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run app evals --db`.

**Not done (deliberately, not MVP-critical):** dashboard endpoints on the DB (`/today`, `/courses`, `/items`, `/changes`, `/citations` still return the S02 mock semester; Soumith's Today view shows mock data until they're wired), S25 `add_study_block` + ICS feed, `models.yaml` picker, Storage/job cleanup in `DELETE /me/data`, wrapping pre-stream DB errors on `/chat` into an `error` event.
**Next steps (in order):** 1. Hari: merge PR #16; Devpost draft before 23:59; revoke the Canvas token pasted in chat. 2. Whoever has budget: wire `/today` + `/courses` + `/items` + `/changes` to the DB (same `DATA_SOURCE` pattern as `/me`, queries like `app/db/repositories/agent.py`) so the Today view shows real data. 3. Decide the demo DB: hosted needs Neal's migrations + seed applied there and `DATA_SOURCE=db` in that environment; local works today (steps above). 4. Real-data rehearsal with a fresh Canvas token.

## 2026-11-14 20:25 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari
**Hour:** ~H24 (Devpost draft due 23:59; final submission Sun 09:00, freeze 08:00; judging 12:30)
**Done (PRs #9, #11 merged; newer commits on dev/hari → next PR):**
- **S22 agent runtime on Gemini** (`app/agent/runtime.py`): SSE events, max turns, timeout, cancel on disconnect, tracing off. Default model **`gemini-3.5-flash`** (2.5 closed to new keys; 3.8 overloaded). **Gemini stream fix** (`app/agent/gemini.py`): tool calls arrive with `index: null`, which broke parallel calls. `CHAT_MODE=auto|agent|scripted` (scripted = demo backup).
- **S21 tools** (six read tools) on `ToolData`: `MockToolData` (S02 mock semester) and **`DbToolData`** (hybrid search on the S01 schema; `fetch_latest` via S10 jobs).
- **S23 citations**: allowed IDs only, quote check (rapidfuzz), lenient markers (`[cite: chunk_N]`), deep links, DB resolution (user-scoped).
- **S24 `create_study_set`** (plan/quiz/flashcards, citation filter, date range). **S26 evals**: `uv run app evals [--db]`, 15 goldens incl. prompt injection.
- **DB mode** `DATA_SOURCE=db`: `DbChatStore` (conversations, messages, runs, study sets), `/me` routes on `profiles` (S20 DB parts), agent uses the profile timezone/model.
- Local Supabase running on Hari's laptop (`make db`), seeded with fake embeddings (`uv run app seed --embeddings fake`, env pointed at the local DB). **256 backend tests pass with the DB.** `tests/conftest.py` now pins `DATABASE_URL` to the local DB at import time (fixed Neal's S10-T06 picking up the hosted URL).
**Eval (seed DB, gemini-3.5-flash): 13/14 pass (93%)**, 0 errors, avg 9.2 s; injection ignored; flashcards OK; G04 uncited. Cost: ~9.6k input + 620 output tokens per question → roughly half a cent at Flash-class prices; Hari loaded $5 prepaid (enough for 1,000+ questions).
**Roadblocks / human items:** Gemini prepaid credits had run out (402) → Hari topped up. The agent may not run `gh pr merge` (permission check): Hari merges PRs. Hari shared a real Canvas token in chat: **not used or stored**; the plan is to connect through the app's Connect Canvas step once Neal's S11 is on main, with a **fresh** token (revoke the pasted one).
**Next steps (in order):**
1. Hari: merge the open dev/hari PR. Devpost draft before 23:59.
2. Hari's agent: dashboard endpoints on the DB (`/today`, `/courses`, `/items`, `/changes`, `/citations`) in DB mode; `POST /sync` + `GET /sync/status` via S10; S25 `add_study_block` + decision + ICS feed.
3. When Neal's S11 + S12 land on main: run the real pipeline locally (API `DATA_SOURCE=db` + worker), Hari connects Canvas with a fresh token in the app, then re-run the evals on real courses.
4. Before the demo: decide hosted vs local DB for the demo (hosted needs migrations + seed applied by Neal), and set `DATA_SOURCE=db` in that environment.
**Gotchas:** psycopg async on Windows needs a selector loop: scripts use `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)`; tests that call the app over HTTP with the DB use `httpx.ASGITransport` (not TestClient). Seed with fake embeddings ⇒ run the agent with `EMBEDDINGS_PROVIDER=fake` locally, or vector search mismatches. Bash heredocs with quotes failed in this tool: write edit scripts to files.

## 2026-11-14 20:20 ET · Soumith's laptop · Claude Code (Opus 5.5) · branch soumith/claude → dev/soumith
**Hour:** ~H24 (hacking began Fri 20:30 ET). Final submission Sun 09:00, code freeze 08:00, judging 12:30.
**Start check:** merged `main` @ `a081914` (steward already took dev/soumith in via PR #14; then S13/S14/S16 landed): no conflicts. Web: 70 unit/component + 6 e2e, lint, typecheck, build green on main's code. No Python/uv here, so backend tests and `make api` not run on this laptop.
**Done:**
- **All role-C MVP screens are on `main`** (S30–S34, mock mode): sign-in, onboarding, Today + course, chat + study cards + Add/Skip, study pages (plan/quiz/flashcards), Settings, Canvas-expiry banner. Built by Claude + Codex + Cursor in parallel worktrees; all merged.
- UI vs. main's API: contract unchanged except a doc comment on `PATCH /me`. **Live today:** auth (S20), UMass login start/poll (S13, local headed browser), `POST /chat` (real Gemini agent when the API has a key), conversations + study sets (in-memory). **Still stubs (`mock_data.py`):** `/today`, `/courses`, `/items`, `/changes`, `/citations`, `/me` (+PATCH, DELETE data), Canvas connect, disconnect, sync, `/models`, calendar, study-block decisions.
- Screenshot QA (1280 + 375 px) of chat with study cards, Settings, onboarding, study list/quiz: fixed the Canvas guide (step 2 showed one word per line on phones).
- Docs: **frontend runbook** `apps/web/README.md` (was create-next-app boilerplate): screens, mock vs real mode, real-backend checklist, gotchas. `.env.example` gains `NEXT_PUBLIC_API_MOCKS` + note that web vars go in `apps/web/.env.local`. Pitch “What actually works” gets the UI rows. `progress/soumith.md` rewritten with the **UI needs list**. Parallel-agents brief marked closed.
**Decisions / design changes:** none.
**Roadblocks:** UI not yet run against the real API (no Python on this laptop; publishable key not here).
**State of main:** `a081914` includes all frontend work; this entry + the Canvas-guide fix are on `dev/soumith` for the steward's next tick.
**Next steps (in order):**
1. **Hari:** wire the stub endpoints in demo order (`/today`, `/courses`, `/courses/{id}`, `/citations`, `/me` + PATCH, `/sync/status`, `POST /connections/canvas` → `connect_canvas`, study-block decisions, calendar, delete-my-data). UI needs no change: shapes match. Then `make types`.
2. **Hari:** Supabase redirect URL `http://localhost:3000/auth/callback`, Google provider (or email-link only), publishable key in `apps/web/.env.local` on the demo laptop.
3. **Anyone with Python + keys:** run the UI in real mode (`apps/web/README.md` § B) and walk the demo script; log drift in the devlog.
4. **Team:** decide localhost demo vs deployed URL (nothing deployed yet); decide P6–P9 + 409 `login_id` (`progress/soumith.md`).
**Gotchas:** web env vars only work from `apps/web/.env.local`; mock mode is the always-works backup demo; UI has no password sign-in (seed user uses a magic link via Inbucket).

## 2026-11-14 20:15 ET · Neal's laptop · Claude Code (Opus 5.5) · branch dev/neal
**Done (all on main):** PR #12 (S11 Canvas connector, S12 file processing + embeddings, S10 incomplete-listing fix), PR #15 (S16 cross-platform merge, S13 local live login, S14 Gradescope connector). Built by parallel agents in lane A, reviewed and integrated on dev/neal; 423 backend tests green. **Merge steward** running (docs/handoff/merge-steward.md): merged Hari (PR #13) and Soumith (PR #14) into main.
**Decisions:** merge steward (decisions.md). Only S16 writes item change rows. Connectors report incomplete listings via `ctx.incomplete`.
**Next steps (in order):** 1. Live checks with real accounts: paste a Canvas token (S11 acceptance), Gradescope NetID+Duo login (S13-T07/S14 spike). 2. Hosted Supabase: apply migrations + seed the demo account (needs hosted DATABASE_URL). 3. Hari: wire `POST /connections/canvas` → `connect_canvas`, `/sync` routes, disconnect (S13-T06), `delete_user_files` in delete-my-data. 4. Stretch: S17 Piazza.
**Gotchas:** live login opens Chromium on the machine running `make api`; web tests on Node 26 need `NODE_OPTIONS=--no-experimental-webstorage`; PyMuPDF is AGPL (credited).

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

- Claude: merged Cursor's S31 (`b54a81b`, Cursor stopped after it) and fixed its e2e: the mock worker started twice under React Strict Mode, so live logins “expired” mid-flow (`startMockWorker` now idempotent, S30-T09); UMass step says “Echo360 connected”. All 4 e2e + 57 unit tests green. Canvas-expiry banner on every signed-in screen (S34-T06). **S34 settings page handed to Codex** (brief §3.B update).
**Codex study-page update (soumith/codex):** Checkpoint 3fb81e0 committed before fetching/merging origin/dev/soumith (already current, no conflicts). Read the three-agent brief; only section 3.A owned. Finished /study list and plan/quiz/flashcard detail pages, local plan progress, keyboard controls, resolved-map/fallback citation lookup, malformed-payload and fetch-error states. Study REST handlers isolated in handlers-study.ts. Tests-first: missing study-screen import failed before implementation; now 41 unit/component tests + all 3 Chromium e2e tests pass (S33-T11 at 375 px), lint/typecheck/production build pass. Build via node node_modules/next/dist/bin/next build: npm wrapper hit a Turbopack subprocess error; direct Node succeeded. Installed pinned Playwright Chromium locally. No dependencies/contracts changed. P7 approval outcomes on conversation reload still pending. Ready for Claude to merge and update spec/pitch/progress status per the shared brief.

- Claude: **Codex stopped too, so Claude built S34 Settings**: accounts (status, Refresh, Reconnect, Disconnect with confirm), profile (name, time zone), calendar (Google/Apple/Outlook buttons, masked link, copy, new link with confirm), privacy (Delete my data, type DELETE), Advanced → AI choice grouped Recommended/Experimental (Gemini default). S34-T01–T05 + banner T06; 69 unit + 5 e2e green, lint/typecheck/build clean. **All role-C MVP screens now exist in mock mode.**

- Claude: **Codex hit its usage limit; Claude finished its lane.** Codex had completed study cards, approvals and study pages (S33-T07–T11). Done now: phone chat layout (message box at the bottom, stays above the tab bar; e2e S33-T12) and a bug where a new chat showed no suggested questions (disabled query counted as loading; S33-T13). Codex's uncommitted duplicate Settings in its worktree is superseded by `46b03e6`. Spec index statuses for S30/S32/S33 corrected. PR `soumith/claude` → `dev/soumith`.

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
