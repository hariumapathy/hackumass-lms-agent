# Neal: progress

**Branch:** `main` (explicit user request for this fix session) · **Role:** demo integration across A/B/C · **Last updated:** 2026-11-14 22:00 ET

## Done
- Updated local main from remote `1b882c7`; read relay notes/specs and traced the Canvas → worker → DB → UI path.
- S32/S23: DB-backed Today, courses/details, items, changes/mark-seen and citations; user scoping, timezone/DST windows, empty-account and isolation regressions.
- S13-T06: disconnect deletes credentials + connection and cancels queued platform jobs. S10: unreadable credentials surface Reconnect, merges run ahead of bulk files, readiness includes pending merge.
- UI import completion refreshes caches automatically; production `make demo-web` removes dev compilation on navigation. Google sign-in hidden until configured.
- Corrected the original wrong Canvas host to `umamherst.instructure.com` (official UMass IT link).
- Live local check: fresh account → Canvas token accepted → eight courses, actual Today/course data → real Gemini answers with syllabus-page and announcement citations. Seeded backup kept separate.
- Checks: 440 backend passed, 1 skipped, 1 expected failure; 71 frontend; 6 browser tests; lint/format/types and production build green.

## In progress
- Final production restart and manual Refresh check; saving verified work on main as requested.

## Next
1. Rehearse the local live-data demo using `docs/demo-runbook.md`; keep API, worker and production web running.
2. S25 calendar feed + approval persistence are still stubs; skip those demo steps until implemented under their spec.
3. Manual Gradescope NetID/Duo check remains for a teammate with that account.

## Blocked on / needs from others
- None for the Canvas/Today/chat demo. Hosted Supabase is not required locally.

## Contract change proposals
- None; schema and API response shapes unchanged.

## Notes for other agents
- User explicitly authorized work on main this session; changes span shared backend and frontend folders.
- Runtime credentials live only in ignored local files / encrypted local DB. Never copy real account content or secrets into fixtures or docs.
- Existing local Supabase needed `make db-stop && make db` to pick up callback URL changes; no database reset was used. Use `nvm use 26` on this laptop (default shell Node 18 cannot build Next 16).
- Default demo embeddings remain fake (keyword retrieval); real Gemini chat and real material citations were verified. Re-embedding/provider changes require care; see S12.
- Pause the live worker before full integration tests: existing S10 tests manipulate the local sync queue. Resume with `make demo-worker` afterward.
