# Neal: progress

**Branch:** `dev/neal` · **Role:** A (data and sync) · **Last updated:** 2026-11-14 ~19:55 ET

_Only Neal (or Neal's agent) edits this file. Keep it short; replace stale lines._

## Done
- **S01 schema** on `dev/neal`: `supabase/migrations/0001_init.sql`, all row models in `backend/app/db/models.py`, S01-T01–T08 pass on local Supabase. Hari's S20-T05/T07 now run (no longer skipped).

## In progress
- S03 seed data (loader `uv run app seed`, fixtures in `supabase/seed/`, IDs match `backend/app/api/mock_data.py`).

## Next
- S10 sync framework → S11 Canvas → S12 file processing + embeddings.

## Blocked on / needs from others
- **B and C: review S01** (schema is the contract) so it can be marked `Ready`/`Done`.
- For seeding the **hosted** demo account: hosted `DATABASE_URL` (pooler connection string) and `GEMINI_API_KEY` (Hari). Local work doesn't need them.

## Contract change proposals
-

## Notes for other agents
- Local DB: `make db` (Docker must be running) then `make db-reset`. Integration tests use the local DB only.
- pgvector lives in schema `extensions`: write `%s::extensions.vector` when casting a parameter; `<=>` works as-is.
- Clients (`authenticated`) can only SELECT their own rows; `anon` gets nothing. All writes go through the backend.
- Integration tests: `tests/integration/db.py` has `AsUser(conn, user_id)` (run SQL as a signed-in student), `create_auth_user`, `insert_minimal_rows`. Use unique emails: tests re-run against the same DB.
