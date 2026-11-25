# Local demo: live-test findings

Verified on Neal's laptop, 2026-11-14. Fixes are on main in `4d64086`; relay verification in `893eb0d`. No tokens, keys, or private course text belong in this report.

## Fixed and verified

| Issue | What happened | Resolution / evidence |
|---|---|---|
| Live login never opened on Windows | `POST /connections/{piazza,gradescope}/login` → 503: Playwright can't start a browser on the API's selector loop (NotImplementedError); bundled chrome.exe then failed with 'spawn UNKNOWN' | Playwright on its own Proactor-loop thread; visible window uses installed Edge/Chrome on Windows; `make setup` installs Chromium; live Piazza login + import + chat citation verified (Hari, 2026-11-15) |
| Demo API served stale code on Windows | `uvicorn --reload` reload hung / orphaned worker kept :8000 | `make demo-api` runs `uv run app serve` (no reload) |
| Removed posts read ': status changed' on Today | Change summaries only knew field names | 'X was removed' / 'X is back' (`app/core/change_text.py`) |
| Wrong Canvas host | Token validation hit `umass.instructure.com` and returned 404 | Corrected to official `umamherst.instructure.com` in defaults, guide, examples and specs; live token accepted |
| Dashboard ignored real data | Today/courses/items/changes/citations returned the mock semester even in DB mode | User-scoped DB routes; live account showed eight courses and 125 canonical deadlines; syllabus/announcement citations verified |
| Disconnect was a no-op | API returned success while keeping the connection and secret | Connection/secret removal and queued platform-job cancellation; isolation/idempotency integration test passes |
| Views stayed stale after imports | UI invalidated when work was queued, but did not watch for completion | Status monitoring invalidates cached views; live manual Refresh changed Today from updating to fresh without reloading |
| Merge waited behind bulk files | First import had courses/materials but no canonical deadlines until file jobs ran | Merge uses manual priority, ahead of bulk processing; queue-priority regression passes |
| Onboarding could declare readiness before merge | Platform fetch finished before canonical deadlines existed | Status includes queued/running merge jobs; readiness regression passes |
| Unreadable credentials left runs stuck | Decryption failed before run status was finalized | Run and connection become needs-reconnect; failing-first regression now passes |
| Slow first tab visits | Next dev compiled each route on first visit | `make demo-web` builds/starts production; real navigation and production build verified |
| Broken Google sign-in option | Local provider was not configured | Local demo hides Google; explicit opt-in for environments with a configured provider; email-link login verified |
| Local sign-in used stale runtime config | Existing local Supabase ignored the corrected callback allowlist; old API settings did not match | Restarted Supabase without resetting data and API via demo launcher; email sign-in works |

## Open issues / follow-ups

These were identified while inspecting the live rehearsal's screens and backing code. Destructive actions were not exercised against the live student's account.

| Priority | Issue | Evidence and next action |
|---|---|---|
| P1 | Delete my data leaves stored files and queued jobs | `backend/app/api/routes/account.py` deletes DB rows only; Storage/job cleanup is explicitly pending and S20-T07 is expected-failing. Complete cleanup before treating privacy deletion as finished |
| Implemented on review branch (S39) | Account switching reused cached views in synthetic two-user regression | Browser QueryClient is shared; query keys such as `me`/`courses` omit user ID and `auth-provider.tsx` does not clear the cache on sign-out/account changes. Add a two-user regression, cancel in-flight queries and clear/scope caches. S39 reproduced the browser-state issue with synthetic A/B accounts and now replaces account caches, resets local state and fences REST/SSE/late auth callbacks. Nine new regressions pass. This is not a cross-user DB authorization leak; changes remain unmerged for review |
| ~~P2~~ fixed (S25) | Calendar UI offers sample-data subscriptions for live accounts | Visible Settings/onboarding links contain `demo-token`; `calendar.py` builds the feed from mock items. Complete S25 or hide the controls for the live demo |
| ~~P2~~ fixed (S25, live-verified 2026-11-14) | Study-session approval is not persisted | `study.py` decision endpoint changes copies of mock blocks only. Complete S25 before claiming Add/Skip saves real study sessions |
| ~~P2~~ fixed 2026-11-14 (Echo360 hidden in Settings, onboarding and the sources bar) | Echo360 Connect is shown despite missing backend support | Live onboarding/Settings show it; `LoginManager` only registers Gradescope and returns 422 for Echo360. Hide/label unavailable while S15 remains stretch |
| P2 | Already-open tabs can retain the previous UI after a rebuild | This follow-up saw the old Canvas settings link until page reload; the fresh page had the corrected link. Reload rehearsal tabs after restarting/rebuilding; consider a deployment/version refresh notice |

## Demo verification and limits

- Real Canvas connection, import, Today, course details, Gemini answers, and syllabus-page/announcement citation cards were verified. A replacement token supplied afterward was accepted through Reconnect Canvas; its import completed and Today showed a fresh timestamp.
- Base run: 440 backend tests passed, 1 skipped, 1 expected failure; 71 frontend tests and six browser tests passed; lint, formatting, types and production build passed.
- Canvas updates are periodic (about 20 minutes) plus manual Refresh, not a Canvas Live Events feed. Search currently uses fake embeddings with keyword retrieval in the local demo; Gemini chat is real.
- Gradescope/Duo login is still a manual verification task, not a demonstrated failure. Echo360 is unimplemented stretch work.
- Hosted Supabase secret is unnecessary for this run: API, worker, Auth and Storage target the local Docker stack; its local keys are obtained by the demo launcher.


## Post-hackathon deletion regressions — review branch, 2026-11-24

Synthetic local accounts reproduced clear-data returning success while leaving files, ignoring Storage failure, replaying a deleted sync and stale merge, duplicate browser starts after a delayed generation lookup, and stale writes after lock loss/child-task request exit. S40 now covers these with durable retry, user work barriers, generation checks and guarded DB leases. Settings still offers deletion when loading is blocked. Backend588 pass/1 optional skip; the optional actual local Storage round-trip passed separately; frontend102 and6 mock browser E2E pass. No real student's data was cleared. [Spec](specs/S40-complete-data-deletion.md), [recovery and remaining Storage fault gate](deployment/data-deletion.md). These changes are on the implementation branch, not main.


## Post-hackathon retrieval regressions — review branch, 2026-11-24

Synthetic searches returned removed materials/posts and direct reads exposed removed material excerpts; six initial assertions failed. S41 filters owned non-removed parents before lexical/vector candidate limits and direct reads.11 focused cases now pass, including vector crowding and a foreign-parent mismatch. Historical citation resolution deliberately remains available with changed/removed status, and current tool results retain changed status. No live course sources/model calls; no claim that the later embedding/publication/freshness plan is complete.


## Post-hackathon Canvas absence regressions — review branch, 2026-11-24

Mocked HTTP plus local DB reproduced files disappearing after a capped second import, a module-only fallback, or403 on a later file page. Non-list JSON was treated as an empty successful listing and could remove all previous files. S42 marks truncated/module lists incomplete and rejects malformed list payloads.20 new cases and66 focused connector/pipeline checks pass; complete shorter listings still remove real absences. These are fixture reproductions, not fresh live Canvas failures. Full discovery and permission changes remain separate policies.


## Post-hackathon presence-restoration regressions — review branch, 2026-11-24

Import→removal→identical return left item sources, posts and files removed; changed course links could also stay removed. Canonical merge omitted the “is back” status event. Five original synthetic DB regressions reproduced this. S43 restores observed presence separately from content, preserves IDs/hash/version/chunks, avoids unchanged reprocessing, and emits one appropriate back event. Nine new cases cover concurrency, multi-source items, genuine field changes, submitted state and owner isolation. Failed/missing indexing recovery is still separate work.


## Post-hackathon indexing-delivery regressions — review branch, 2026-11-25

A source could commit before a later fetch failed, losing its in-memory processing request. S44 adds private encrypted transactional intents and leased recovery. Tests also reproduced metadata runs stranded by callback failure and a real Procrastinate unique-key failure when a running job retried beside a replay. Delivery now tolerates duplicates through execution/completion guards.16 new cases and644 backend checks pass; failed-processor retry/classification and source publication/disconnect races remain separate gates. Live Gemini synthetic chat/app G01 checks pass; this is not a fresh real-course retrieval evaluation.
