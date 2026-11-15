# Hari: progress

**Branch:** `dev/hari` · **Role:** B (agent and API) · **Last updated:** 2026-11-14 20:30 ET (handoff)

_Only Hari (or Hari's agent) edits this file. Keep it short; replace stale lines._

## Done
- S00, S02 (on main). **S20** auth + DB-backed `/me` routes. **S21** six read tools (mock + DB, hybrid search). **S22** agent runtime on Gemini (`gemini-3.5-flash`, stream fix, CHAT_MODE). **S23** citation validation + DB resolution. **S24** `create_study_set`. **S26** eval runner + 15 goldens: **13/14 on the seed**.
- `DATA_SOURCE=mock|db` switch; DB chat store. **Connect Canvas route** (S11-T12), `POST /sync`, `/sync/status` on the DB. 432 backend tests with the local DB. Verified end to end on a real server with real Gemini.

## In progress
- PR #16 (DB mode, Connect Canvas, evals) waiting for Hari's merge.

## Next
- Dashboard endpoints on the DB (`/today`, `/courses`, `/items`, `/changes`, `/citations`), S25 study blocks + ICS feed.
- Real-data run when S11/S12 are on main (Hari connects Canvas in the app with a fresh token).

## Blocked on / needs from others
- **Neal:** S11/S12 on main for real Canvas data; the hosted DB needs migrations + seed if the demo uses it.
- **Hari (human):** merge PRs (the agent can't); Devpost draft; revoke the Canvas token pasted in chat.
- **Soumith:** S02 follow-ups P6–P9 still waiting on Hari's decision.

## Contract change proposals
- None. (Note: if `POST /chat` fails before the stream starts in DB mode, e.g. DB down, the runtime raises before `run_started`; wrapping it into an `error` event is a small follow-up.)

## Notes for other agents
- **Auth is real now (S20):** the API needs a real Supabase access token; `Bearer anything` returns 401. The web app's demo/MSW mode is unaffected. Tests mint tokens with `tests/helpers.py` (`auth_header()`); `tests/conftest.py` forces test-only auth settings and the **local** `DATABASE_URL`, so tests never touch the hosted project.
- **Windows + psycopg async:** needs a selector event loop. `make api` (`--reload`) is fine; don't run uvicorn on Windows without `--reload`. Tests use the `pytest_asyncio_loop_factories` hook.
- **Neal:** the course-code normalizer + alias table is in `backend/app/core/courses.py` (shared). Please reuse it in S16 rather than writing a second copy.
- **DB mode:** `DATA_SOURCE=db` makes the agent + `/me` use `DATABASE_URL`. Locally: `make db`, then seed the LOCAL DB (`DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres SUPABASE_URL=http://127.0.0.1:54321 uv run app seed --embeddings fake --reset`) and run with `EMBEDDINGS_PROVIDER=fake`.
- Tool outputs for S25: `add_study_block` should append `s.StudyBlock`s to `ctx.proposed_blocks` (+ `ctx.block_summary`); the runtime emits one `approval_required`.
- New repository rule enforced by S20-T04: every public function in `app/db/repositories/*.py` starts `(conn, user_id, ...)`.
- Run `make setup` first. No global pnpm or Supabase CLI needed. Next.js is v16 (read `apps/web/AGENTS.md`). Frontend test tooling pinned for Node 20.
- Python scripts on Windows: open files with `encoding="utf-8"` (the default cp1252 truncated a doc once).
