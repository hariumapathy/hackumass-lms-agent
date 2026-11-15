# Neal: progress

**Branch:** `dev/neal` · **Role:** A (data and sync) · **Last updated:** 2026-11-14 ~19:55 ET

_Only Neal (or Neal's agent) edits this file. Keep it short; replace stale lines._

## Done
- **S01 schema** on `dev/neal`: `supabase/migrations/0001_init.sql`, all row models in `backend/app/db/models.py`, S01-T01–T08 pass on local Supabase. Hari's S20-T05/T07 now run (no longer skipped).

- **S03 seed** on `dev/neal`: `make db-reset` loads the demo semester (fake embeddings, 0.5 s). Local login `demo@example.com` / `demo-password-311`. IDs match `mock_data.py`.

- **S10 sync framework** (`a97ab4a`): connector interface, diff, pipeline, Procrastinate queue (`0002_procrastinate.sql`), crypto, `make worker`, S16-lite 1:1 merge.

## In progress
- S11 Canvas connector (branch `neal/s11-canvas`) and S12 file processing (branch `neal/s12-processing`), built by parallel agents in my lane; I merge them into `dev/neal` after review.

## Next
- S11 Canvas → S12 file processing (tiktoken chunker; the Gemini embedding provider is already in `app/core/embeddings.py`).

## Blocked on / needs from others
- **B and C: review S01** (schema is the contract) so it can be marked `Ready`/`Done`.
- For seeding the **hosted** demo account: hosted `DATABASE_URL` (pooler connection string) and `GEMINI_API_KEY` (Hari). Local work doesn't need them.

## Contract change proposals
-

## Notes for other agents
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
