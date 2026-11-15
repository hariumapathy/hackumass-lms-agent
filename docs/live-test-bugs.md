# Local demo: live-test findings

Verified on Neal's laptop, 2026-11-14. Fixes are on main in `4d64086`; relay verification in `893eb0d`. No tokens, keys, or private course text belong in this report.

## Fixed and verified

| Issue | What happened | Resolution / evidence |
|---|---|---|
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
| P1, needs reproduction | Account switching may reuse another account's cached views | Browser QueryClient is shared; query keys such as `me`/`courses` omit user ID and `auth-provider.tsx` does not clear the cache on sign-out/account changes. Add a two-user regression, cancel in-flight queries and clear/scope caches. This is a code finding, not a demonstrated cross-user DB leak |
| P2 | Calendar UI offers sample-data subscriptions for live accounts | Visible Settings/onboarding links contain `demo-token`; `calendar.py` builds the feed from mock items. Complete S25 or hide the controls for the live demo |
| P2 | Study-session approval is not persisted | `study.py` decision endpoint changes copies of mock blocks only. Complete S25 before claiming Add/Skip saves real study sessions |
| P2 | Echo360 Connect is shown despite missing backend support | Live onboarding/Settings show it; `LoginManager` only registers Gradescope and returns 422 for Echo360. Hide/label unavailable while S15 remains stretch |
| P2 | Already-open tabs can retain the previous UI after a rebuild | This follow-up saw the old Canvas settings link until page reload; the fresh page had the corrected link. Reload rehearsal tabs after restarting/rebuilding; consider a deployment/version refresh notice |

## Demo verification and limits

- Real Canvas connection, import, Today, course details, Gemini answers, and syllabus-page/announcement citation cards were verified. A replacement token supplied afterward was accepted through Reconnect Canvas; its import completed and Today showed a fresh timestamp.
- Base run: 440 backend tests passed, 1 skipped, 1 expected failure; 71 frontend tests and six browser tests passed; lint, formatting, types and production build passed.
- Canvas updates are periodic (about 20 minutes) plus manual Refresh, not a Canvas Live Events feed. Search currently uses fake embeddings with keyword retrieval in the local demo; Gemini chat is real.
- Gradescope/Duo login is still a manual verification task, not a demonstrated failure. Echo360 is unimplemented stretch work.
- Hosted Supabase secret is unnecessary for this run: API, worker, Auth and Storage target the local Docker stack; its local keys are obtained by the demo launcher.
