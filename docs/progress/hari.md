# Hari: progress

**Branch:** `dev/hari` · **Role:** B (agent and API) · **Last updated:** 2026-11-14 ~19:40 ET

_Only Hari (or Hari's agent) edits this file. Keep it short; replace stale lines._

## Done
- Planning docs, repo setup, agent context, team branches.
- **S00 scaffolding** and **S02 API + SSE contract** (on `main`).
- **S20 auth (code):** real Supabase JWT verification (JWKS ES256 for the hosted project, HS256 fallback), route-table + repository-signature scans, error envelope incl. 500, `PATCH /me` validation, 10/min chat rate limit, JSON request logs without tokens/text, psycopg pool + `profiles` repository. 60 backend tests pass, 2 skip pending S01.

## In progress
- S20 DB parts: wire `/me`, `PATCH /me`, `DELETE /me/data` and profile auto-create to `app/db/repositories/profiles.py` **once S01's `profiles` table exists**; un-skip `tests/integration/test_s20_db.py`.
- **S21 plumbing done** on branch `hari/s21-tools` (args, runner, course resolver, coverage, truncation, untrusted wrapping, labels, times). Next: the tools' SQL once S01/S03 land.

## Next
- S21 DB-backed tools on the S03 seed → S22 agent runtime (Gemini) → S23 citations.

## Blocked on / needs from others
- **Neal:** S01 schema (S20 DB parts, S21 queries) and S03 seed.
- **Hari (human):** Devpost draft before Sat 23:59 ET. `GEMINI_API_KEY` in `.env` before S22. `SUPABASE_SERVICE_ROLE_KEY` (the new "secret key") in `.env` when the sync worker / delete-my-data needs it. Never in chat or git.
- **Soumith's S02 follow-ups P6–P9** (see soumith.md) need a decision; none blocks Stage 1.

## Contract change proposals
- None.

## Notes for other agents
- **Auth is real now (S20):** the API needs a real Supabase access token; `Bearer anything` returns 401. The web app's demo/MSW mode is unaffected. Tests mint tokens with `tests/helpers.py` (`auth_header()`); `tests/conftest.py` forces test-only auth settings and the **local** `DATABASE_URL`, so tests never touch the hosted project.
- **Windows + psycopg async:** needs a selector event loop. `make api` (`--reload`) is fine; don't run uvicorn on Windows without `--reload`. Tests use the `pytest_asyncio_loop_factories` hook.
- **Neal:** the course-code normalizer + alias table is in `backend/app/core/courses.py` (shared). Please reuse it in S16 rather than writing a second copy.
- New repository rule enforced by S20-T04: every public function in `app/db/repositories/*.py` starts `(conn, user_id, ...)`.
- Run `make setup` first. No global pnpm or Supabase CLI needed. Next.js is v16 (read `apps/web/AGENTS.md`). Frontend test tooling pinned for Node 20.
- Python scripts on Windows: open files with `encoding="utf-8"` (the default cp1252 truncated a doc once).
