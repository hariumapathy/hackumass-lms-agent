# Hari: progress

**Branch:** `dev/hari` · **Role:** B (agent and API) · **Last updated:** 2026-11-14 ~18:30 ET

_Only Hari (or Hari's agent) edits this file. Keep it short; replace stale lines._

## Done
- Planning docs, repo setup, agent context, team branches.
- **S00 scaffolding (code):** `backend/`, `apps/web/` (Next.js 16), `supabase/`, root `Makefile`, `.env.example`, CI workflow.
- **S02 API + SSE contract (code):** typed route stubs for every endpoint (mock data, demo-auth stub), error envelope, SSE framing, scripted `POST /chat` stream, `backend/app/api/CONTRACT.md`, `make types` → `apps/web/src/lib/api/{openapi.json,schema.d.ts}`. 27 backend tests pass; ruff, pyright, eslint and typecheck clean.

## In progress
- S00 acceptance: `make db` (needs Docker Desktop running) and CI green on PR #1.
- S02: waiting for Soumith's review.

## Next
- Stage 1: S20 (real Supabase JWT auth) → S21 (tools) → S22 (agent runtime) → S23 (citations). Needs S01 schema from Neal for anything DB-backed.

## Blocked on / needs from others
- **Timeline:** clock started Fri 9:30 PM, so it ends Sun ~9:30 AM ET. A compressed scope plan is waiting on Hari's approval.
- Hosted Supabase project + OpenAI key from Hari (in `.env`, never in chat or git).
- S01 schema (Neal) before S20/S21 can hit a real DB.

## Contract change proposals
- None. S02 notes list types the spec referenced but hadn't defined (`MaterialSummary`, `ConversationSummary`, …); review them when you review S02.

## Notes for other agents
- **Run `make setup` first.** No global pnpm or Supabase CLI needed (pinned via `npx` in the Makefile).
- **Next.js is v16**: read `apps/web/AGENTS.md` before frontend code; `pnpm typecheck` runs `next typegen` first.
- Frontend test tooling is pinned to Node-20-compatible versions (Vitest 3.2, Vite 7, jsdom 26). Don't upgrade without checking Node.
- **Soumith:** `make api` serves realistic mock data now. Any non-empty `Authorization: Bearer x` header works until S20. Scripted chat stream: `POST /chat?delay_ms=150`. Re-run `make types` after pulling. **MSW handlers + SSE parser moved from S02 to S30** (S02-T05/T06).
- **Backend:** `tzdata` is a dependency because Windows has no IANA timezone database (`ZoneInfo` needs it). New env var `PUBLIC_API_URL`.
- Neal: `supabase/migrations/` is empty and ready for S01. Mock course codes and IDs in `backend/app/api/mock_data.py` match the S03 seed plan.
