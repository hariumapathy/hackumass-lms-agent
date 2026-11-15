# Neal: progress

**Branch:** `dev/neal` · **Role:** A (data and sync) · **Last updated:** 2026-11-14 ~19:55 ET

_Only Neal (or Neal's agent) edits this file. Keep it short; replace stale lines._

## Done
- **S01 schema** on `dev/neal`: `supabase/migrations/0001_init.sql`, all row models in `backend/app/db/models.py`, S01-T01–T08 pass on local Supabase. Hari's S20-T05/T07 now run (no longer skipped).

- **S03 seed** on `dev/neal`: `make db-reset` loads the demo semester (fake embeddings, 0.5 s). Local login `demo@example.com` / `demo-password-311`. IDs match `mock_data.py`.

## In progress
- S10 sync framework.

## Next
- S11 Canvas → S12 file processing (tiktoken chunker; the Gemini embedding provider is already in `app/core/embeddings.py`).

## Blocked on / needs from others
- **B and C: review S01** (schema is the contract) so it can be marked `Ready`/`Done`.
- For seeding the **hosted** demo account: hosted `DATABASE_URL` (pooler connection string) and `GEMINI_API_KEY` (Hari). Local work doesn't need them.

## Contract change proposals
-

## Notes for other agents
- Local DB: `make db` (Docker must be running) then `make db-reset` (migrations + seed). Integration tests use the local DB only.
- Seed lookups: `seed_id("hackumass-mock", "item/hw5")` == `mock_data.mid("item/hw5")`.
- pgvector lives in schema `extensions`: write `%s::extensions.vector` when casting a parameter; `<=>` works as-is.
- Clients (`authenticated`) can only SELECT their own rows; `anon` gets nothing. All writes go through the backend.
- Integration tests: `tests/integration/db.py` has `AsUser(conn, user_id)` (run SQL as a signed-in student), `create_auth_user`, `insert_minimal_rows`. Use unique emails: tests re-run against the same DB.
