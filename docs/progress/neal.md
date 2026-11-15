# Neal: progress

**Branch:** `codex/calendar-piazza-ui` (latest user request: one review branch; no merge) · **Role:** demo integration across A/B/C · **Last updated:** 2026-11-14 22:34 ET

## Done
- Updated local main from remote `1b882c7`; read relay notes/specs and traced the Canvas → worker → DB → UI path.
- S32/S23: DB-backed Today, courses/details, items, changes/mark-seen and citations; user scoping, timezone/DST windows, empty-account and isolation regressions.
- S13-T06: disconnect deletes credentials + connection and cancels queued platform jobs. S10: unreadable credentials surface Reconnect, merges run ahead of bulk files, readiness includes pending merge.
- UI import completion refreshes caches automatically; production `make demo-web` removes dev compilation on navigation. Google sign-in hidden until configured.
- Corrected the original wrong Canvas host to `umamherst.instructure.com` (official UMass IT link).
- Live local check: fresh account → Canvas token accepted → eight courses, actual Today/course data → real Gemini answers with syllabus-page and announcement citations. Seeded backup kept separate.
- Checks: 440 backend passed, 1 skipped, 1 expected failure; 71 frontend; 6 browser tests; lint/format/types and production build green.

## In progress
- Claimed S25 Google Calendar/private feed + approvals, then S17 Piazza, per user request. Existing S13/S14 live Gradescope flow verified (20 courses, 238 assignments).
- Previous demo work: Production stack left running; manual Refresh completed (323 unchanged records, 125 canonical deadlines), and Today updated its freshness indicator without a page reload.

## Next
1. Finish S25 Calendar checks, commit separately and push this review branch; public Google/Apple subscription validation requires reachable HTTPS hosting. Local ICS download is supported.
2. S17 Piazza: saved-cookie/read-only spike, update design + implementation plan, failing fixtures, implementation, checks, separate commit. Human login may be required.
3. S35 responsive UMass UI: follow research and test plan; preserve SSE. Then S18 Campuswire feasibility. Keep Devpost and bug report honest.

## Blocked on / needs from others
- None for the Canvas/Today/chat demo. Hosted Supabase is not required locally.

## Contract change proposals
- None; schema and API response shapes unchanged.

## Notes for other agents
- Queue-touching tests are now safe next to a live worker: S10-T06 and S13-T06 defer to their own `test-*` queue (never `sync`) and only delete their own jobs. `test_s32_dashboard_db.py` (not mine) still inserts into the real queue: pause the live worker before running it, or switch it to a test queue.
- Disconnect: main's `sync_repo.disconnect` (Procrastinate-native cancel) is the one implementation; my duplicate `app/sync/disconnect.py` was dropped, its S13-T06 tests now cover `sync_repo.disconnect`.
- **E2E rehearsal (2026-11-14 ~20:40, no real accounts):** `scripts/fake_canvas.py` (fake Canvas on :8765 serving the S11 fixtures) → API on DB mode (`DATA_SOURCE=db CANVAS_BASE_URL=http://127.0.0.1:8765 EMBEDDINGS_PROVIDER=fake`) + `make worker` → `POST /connections/canvas` → sync `succeeded` (16 new; re-sync 16 unchanged) → 2 courses, 7 items (merged), 2 posts, 5 materials, PDF chunked. **Gap found (Hari's lane, already on his Next list):** `/today`, `/courses`, `/items`, `/changes`, `/citations` still return mock data in DB mode, so the Today view doesn't show synced data yet.
- Live login runs in the API process (window opens on the machine running `make api`; login state is in memory).
- S20 delete-my-data can call `app.sync.processing.delete_user_files(user_id)` (removes Storage files under `users/{user_id}/`).
- PyMuPDF is AGPL-3.0 (fine: repo is public; in credits).
- **Hari: heads-up on `api/routes/connections.py`.** S13 (role A) wires ONLY the bodies of `POST /connections/{platform}/login` and `GET /connections/{platform}/login/{login_id}`; schemas unchanged. If you're wiring other routes in that file, expect a small merge there.
- **Hari:** seed connections are canvas active (12 min ago), gradescope active (40 min), echo360 needs_reconnect (3 days). There are Piazza posts but **no Piazza connection** (S17 is stretch), so `compute_coverage` lists piazza under `not_connected` while search can still return Piazza posts. Want an `active` Piazza connection in the seed? Say so.
- **Hari (S26 evals):** seed has an injection post for the "must not follow" golden: Piazza `p411` in COMPSCI 311.
- **Hari (S20/S10 wiring):** `POST /sync` / `GET /sync/status` can call `app.sync.jobs.enqueue_sync(conn, user_id, platform, SyncScope, trigger)` and `app.db.repositories.sync` (`list_connections`, `running_platforms`, `last_success_at`). `fetch_latest` = `enqueue_sync(..., trigger="agent")` + `wait_for_sync(conn, user_id, run_id, timeout_s=15)`.
- **Hari:** seeded message text uses `[cite:chunk_<id>]` markers; `content.citations` holds resolved S02 `Citation` dicts.
- **Soumith (re P9):** seeded study-set payloads follow S24: `chunk_ids` per card/question plus a resolved `citations` map `{"<chunk_id>": Citation}`.
- Local DB: `make db` (Docker must be running) then `make db-reset` (migrations + seed). Integration tests use the local DB only.
- Seed lookups: `seed_id("hackumass-mock", "item/hw5")` == `mock_data.mid("item/hw5")`.
- pgvector lives in schema `extensions`: write `%s::extensions.vector` when casting a parameter; `<=>` works as-is.
- Clients (`authenticated`) can only SELECT their own rows; `anon` gets nothing. All writes go through the backend.
- Integration tests: `tests/integration/db.py` has `AsUser(conn, user_id)` (run SQL as a signed-in student), `create_auth_user`, `insert_minimal_rows`. Use unique emails: tests re-run against the same DB.
- Earlier fixes were authorized on main. Latest instruction overrides that: new features stay on the review branch, one commit each, no self-merge. Changes span shared backend and frontend folders.
- Runtime credentials live only in ignored local files / encrypted local DB. Never copy real account content or secrets into fixtures or docs.
- Existing local Supabase needed `make db-stop && make db` to pick up callback URL changes; no database reset was used. Use `nvm use 26` on this laptop (default shell Node 18 cannot build Next 16).
- Default demo embeddings remain fake (keyword retrieval); real Gemini chat and real material citations were verified. Re-embedding/provider changes require care; see S12.
- Pause the live worker before full integration tests: existing S10 tests manipulate the local sync queue. Resume with `make demo-worker` afterward.
