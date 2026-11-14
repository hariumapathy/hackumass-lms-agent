# Hari: progress

**Branch:** `dev/hari` · **Role:** B (agent and API) · **Last updated:** 2026-11-14 17:40 ET

_Only Hari (or Hari's agent) edits this file. Keep it short; replace stale lines._

## Done
- Planning docs, repo setup, agent context, team branches.
- **S00 scaffolding (code):** `backend/` (FastAPI `/health`, settings, CLI stub, package layout), `apps/web/` (Next.js 16 + Tailwind + Vitest), `supabase/` (CLI init), root `Makefile`, `.env.example`, CI workflow. `make test` and `make lint` pass locally (S00-T01, S00-T02).

## In progress
- S00 acceptance: `make db` (needs Docker Desktop running) and CI green on PR #1.

## Next
- S02 (API + SSE contract), then Stage 1: S20 → S21 → S22 → S23.

## Blocked on / needs from others
- **Timeline:** clock started Fri ~9:30 (AM or PM to confirm); scope needs compressing (see message to team).
- Hosted Supabase project + OpenAI key from Hari (put in `.env`, never in chat or git).

## Contract change proposals
-

## Notes for other agents
- **Run `make setup` first.** No global pnpm or Supabase CLI needed (pinned via `npx` in the Makefile).
- **Next.js is v16**: read `apps/web/AGENTS.md` before frontend code; `pnpm typecheck` runs `next typegen` first.
- Frontend test tooling is pinned to Node-20-compatible versions (Vitest 3.2, Vite 7, jsdom 26). Don't upgrade without checking Node.
- Neal: `supabase/migrations/` is empty and ready for S01.
