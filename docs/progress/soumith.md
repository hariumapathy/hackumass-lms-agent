# Soumith: progress

**Branch:** `dev/soumith` · **Role:** C (frontend and product) · **Last updated:** 2026-11-14 ~19:05 ET

_Only Soumith (or Soumith's agent) edits this file. Keep it short; replace stale lines._

## Done
- **S02 review (frontend): approved.** Optional `expires_at` on Canvas connect, the previously undefined types, and "errors before the stream are JSON" are all in. Follow-ups P6–P9 below are Stage 2/3, not blockers.
- **S30 shell + auth, S32 Today + course page, S33 chat (Stage 1 part)**, all in mock mode: `653d134` on `dev/soumith`. 30 web tests, lint, typecheck, `next build` green.

## In progress
Three agents in parallel, one worktree each. Brief: [handoff/soumith-agents-brief.md](../handoff/soumith-agents-brief.md).
- **Claude Code** (`soumith/claude`): e2e S30-T07/S32-T08 green; next: mock-mode service-worker failure message, 375 px QA, merging the other branches, docs, PR → `main`.
- **Codex** (`soumith/codex`): S33 study sets + approval card.
- **Cursor** (`soumith/cursor`): S31 onboarding → S34 settings.

## Next
- Try the web app against Hari's `make api` stubs (needs a laptop with Python/uv).
- Real Supabase sign-in once the publishable key is in `apps/web/.env.local` (and S20 lands).

## Blocked on / needs from others
- **Hari:** answers on P6–P9; S20 for real JWT auth.
- This laptop has no Python / `uv` / `make` (frontend only).

## Contract change proposals
For S02 (Hari to decide; none blocks Stage 1):
- **P6** S31 onboarding step 6 shows live counts, but no response has counts: add `counts?: {courses, items, materials}` to `SourceStatus`.
- **P7** Reloading a conversation can't show whether proposed blocks were added or skipped (`Message` has only `block_ids`, no "get blocks" endpoint): add `Message.blocks: StudyBlock[]` (resolved, like citations).
- **P8** `ModelOption.unavailable_reason?: string` (S34 shows why a model is disabled).
- **P9** Put the SSE event payload models and the S24 study-set payload union into the OpenAPI schema so `make types` generates them (`StudySet.payload` is currently `{[key]: unknown}`). Also: S24 says saved payloads carry a resolved `citations` map, but the mock payload doesn't.

## Notes for other agents
- Frontend REST types = re-exports of generated `schema.d.ts` (`src/lib/api/types.ts`). **Re-run `make types` after API changes**; the UI then fails typecheck where it drifts.
- Node-20 pins: MSW 2.15, supabase-js 2.109, Vitest 3.2 / jsdom 26. shadcn adds import `cn` from the Node-22 `cn` package: rewrite to `@/lib/utils`.
- Mock mode: `NEXT_PUBLIC_API_MOCKS=1` with empty Supabase vars → MSW API + "Continue with demo data" sign-in. `pnpm test:e2e` runs its own mock server on :3100.
- `tests/setup.ts` bridges jsdom `AbortSignal` → Node fetch; don't remove it.
