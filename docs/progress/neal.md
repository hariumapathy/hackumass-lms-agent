# Neal: progress

**Branch:** `dev/neal` · **Role:** A (data and sync) · **Last updated:** 2026-11-14 ~19:55 ET

_Only Neal (or Neal's agent) edits this file. Keep it short; replace stale lines._

## Done
- **S01 schema** on `dev/neal`: `supabase/migrations/0001_init.sql`, all row models in `backend/app/db/models.py`, S01-T01–T08 pass on local Supabase. Hari's S20-T05/T07 now run (no longer skipped).

- **S03 seed** on `dev/neal`: `make db-reset` loads the demo semester (fake embeddings, 0.5 s). Local login `demo@example.com` / `demo-password-311`. IDs match `mock_data.py`.

- **S10 sync framework** (`a97ab4a`): connector interface, diff, pipeline, Procrastinate queue (`0002_procrastinate.sql`), crypto, `make worker`, S16-lite 1:1 merge.

- **S11 Canvas connector** + **S12 file processing** merged into `dev/neal` (321 tests green). Canvas connect: `app.connectors.canvas.service.connect_canvas(conn, user_id, token)` → `CanvasConnectResult`; raises `InvalidCanvasToken` (`code="invalid_token"` → 400) or `PlatformError` (→ 503).
- **S16 merge + change detection** merged into `dev/neal` (369 tests green): one item per real deadline across Canvas/Gradescope; only S16 writes item change rows.
- **Merge steward** rules + check script (`docs/handoff/merge-steward.md`, `scripts/merge-steward-check.sh`).

## In progress
- Parallel agents in my lane (each on its own branch; I review and merge into `dev/neal`): **S13 + S14** browser login + Gradescope (`neal/s13-s14-gradescope`).

## Next
- S11 Canvas → S12 file processing (tiktoken chunker; the Gemini embedding provider is already in `app/core/embeddings.py`).

## Blocked on / needs from others
- **B and C: review S01** (schema is the contract) so it can be marked `Ready`/`Done`.
- For seeding the **hosted** demo account: hosted `DATABASE_URL` (pooler connection string) and `GEMINI_API_KEY` (Hari). Local work doesn't need them.

## Contract change proposals
-

## Notes for other agents
- **Hari:** `POST /connections/canvas` can call `connect_canvas(...)` above. S20 delete-my-data can call `app.sync.processing.delete_user_files(user_id)` (removes Storage files under `users/{user_id}/`) and drop the T07 xfail.
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
