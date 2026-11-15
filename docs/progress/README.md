# Development progress

Team-wide status. Each person's detailed status lives in their own file (only they edit it), so this folder never causes merge conflicts. Update this page when a PR merges to `main`.

| Person | Branch | Role | Status file |
|---|---|---|---|
| Hari | `dev/hari` | B: agent and API | [hari.md](hari.md) |
| Neal | `dev/neal` | A: data and sync | [neal.md](neal.md) |
| Soumith | `dev/soumith` | C: frontend and product | [soumith.md](soumith.md) |

Roles are defaults; anyone may claim a `Ready` spec in the current stage ([AGENTS.md](../../AGENTS.md#team-branches-ownership)).

## Current stage: **0 → 1.** S00 + S02 done; **S01 schema + S03 seed (Neal) are the critical path.** Stage 1 in progress: S20 (auth) merged, S21 plumbing done; S30/S32/S33 frontend on `dev/soumith` (mock mode).

## Contracts
| Contract | Location | Status |
|---|---|---|
| Database schema ([S01](../specs/S01-database-schema.md)) | `supabase/migrations/` | **Merged** (PR #8, Neal) |
| API + SSE event format ([S02](../specs/S02-api-contract.md)) | `backend/app/api/` + `CONTRACT.md` | Built (mock data); approved by C; follow-ups P6–P9 pending |
| Seed data ([S03](../specs/S03-seed-data.md)) | `supabase/seed/` | **Merged** (PR #8, Neal): `make db-reset` |

Feature-by-feature status lives in the spec index: [specs/README.md](../specs/README.md).

## Checkpoints ([05](../05-roadmap.md#36-hour-plan))
| Checkpoint | Goal | Status |
|---|---|---|
| H2 | Contracts agreed; repo + Supabase set up | Partial: repo, hosted Supabase, S02 done; S01/S03 pending |
| H10 | A question about real Canvas data answered end to end in the UI | Not started |
| H18 | Study mode with verified citations from real data; Gradescope connected | Not started |
| H24 | MVP feature freeze; full demo run-through | Not started |
| H30 | Code freeze; bug fixes only | Not started |

## Merged to main
_Newest first. One line per merged PR: what it adds and who._
- PR #8: S01 schema + RLS, S03 seed semester (`make db-reset`, demo login `demo@example.com` / `demo-password-311` locally), S10 sync framework + Procrastinate queue (`make worker`). (Neal)
- S21 agent-tool plumbing (no DB yet) + handoff docs. (Hari, final dev/hari PR)
- PR #5: S20 real Supabase JWT auth, route/repo scans, chat rate limit, private logs. (Hari)
- PRs #2–#4: Echo360 → stretch, Gemini as default model. (Hari)
- PR #1: S00 scaffolding + S02 API contract (mock data). (Hari)
- Planning docs, development workflow, feature specs S00–S34 (Draft), agent context (`AGENTS.md`), branches. (Hari)
