# AGENTS.md: context for coding agents

This file is for **any coding agent** working in this repo (Claude Code, Codex, Cursor, Copilot, Gemini, ...). Each of the 3 teammates uses their own agent on their own branch. Read this whole file before making changes.

## Project in one paragraph
HackUMass 2026 (36 hours, team of 3). An AI study agent for UMass students: a **sync worker** copies each student's Canvas, Gradescope and Echo360 data into Supabase; a **Python agent** (OpenAI Agents SDK) answers questions, builds study plans/quizzes/flashcards with verified citations, and shows a Today view of deadlines; a **Next.js** frontend is the UI.

## Current status
**Phase: planning done, feature specs drafted (status `Draft`), scaffolding not started.** No application code exists yet. Do not assume a file, package or endpoint exists; check first.
Live progress is tracked in [`docs/progress/`](docs/progress/README.md). Read it at the start of every session.

## How we build: spec first, tests first
Follow [docs/08-development-workflow.md](docs/08-development-workflow.md) for every feature:
1. **Only implement a spec whose status is `Ready`** ([docs/specs/](docs/specs/README.md)). If your human asks you to build something without a spec, help them write the spec first.
2. **Write the spec's test plan as tests first** (test IDs like `S11-T04` in test names), run them, confirm they fail.
3. **Implement the smallest code that passes**, staying inside the spec's scope and your role's folders.
4. **Verify**: all tests, lint, type checks; check off acceptance criteria.
5. **If the spec is wrong or unclear, stop and ask**; update the spec before the code.
6. Work **stage by stage** (Stage 0 contracts → 1 vertical slice → 2 depth → 3 completeness → 4 stretch).

## Read before working
| Doc | Why |
|---|---|
| [docs/08-development-workflow.md](docs/08-development-workflow.md) | Lifecycle, stages, testing strategy, Definition of Done |
| [docs/specs/](docs/specs/README.md) | Every feature's spec: inputs, outputs, interfaces, diagrams, test plan |
| [docs/03-architecture.md](docs/03-architecture.md) | Diagram, agent + tools, stack, repo layout, security rules |
| [docs/07-sync-and-storage.md](docs/07-sync-and-storage.md) | Sync pipeline, storage, on-demand sync |
| [docs/04-citations-and-freshness.md](docs/04-citations-and-freshness.md) | How citations/links must work |
| [docs/05-roadmap.md](docs/05-roadmap.md) | Roles, hour-by-hour plan, checkpoints |
| [docs/decisions.md](docs/decisions.md) | What's decided; don't re-litigate without the team |
| [docs/progress/](docs/progress/README.md) | Who's doing what right now, blockers, handoffs |

## Team, branches, ownership

| Person | GitHub | Branch | Role | Progress file |
|---|---|---|---|---|
| Hari | @hariumapathy | `dev/hari` | TBD (A, B or C) | [docs/progress/hari.md](docs/progress/hari.md) |
| Neal | @nealp | `dev/neal` | TBD | [docs/progress/neal.md](docs/progress/neal.md) |
| Soumith | @Soumith-Madadi | `dev/soumith` | TBD | [docs/progress/soumith.md](docs/progress/soumith.md) |

Roles ([05](docs/05-roadmap.md#roles)): **A** data and sync (`supabase/`, `backend/app/connectors/`, `backend/app/sync/`) · **B** agent and API (`backend/app/api/`, `backend/app/agent/`) · **C** frontend and product (`apps/web/`). Shared backend code (`backend/app/core/`, `backend/app/db/`) is changed in small PRs with a heads-up. Update this table when roles are assigned.

**Stay in your role's folders.** If you must touch another role's folder, keep the change minimal and say so in your progress file and PR.

## Git workflow
- Work on your personal branch (`dev/<name>`), or short-lived feature branches off it (`<name>/<feature>`).
- **Bring in `main` often** (at least every few hours): `git fetch origin && git merge origin/main`. Prefer merge over rebase on branches others may have pulled.
- **Open a PR into `main`** whenever a piece works end to end, and at minimum before each checkpoint (H10, H18, H24). Small PRs merge easily; big ones conflict.
- Never push directly to `main`. Never force-push a branch someone else uses.
- Agents: only commit, push or open PRs when your human asks.
- Merge conflicts in `docs/progress/` should never happen: each person edits only their own file.

## Contracts (change only with whole-team agreement)
These let three people build in parallel. They are created together in hours 0–2.
1. **Database schema**: `supabase/migrations/`, specified in [S01](docs/specs/S01-database-schema.md) (source of truth; Pydantic models derive from it).
2. **API + SSE event format**: specified in [S02](docs/specs/S02-api-contract.md); implemented as FastAPI models (→ generated TS types) + `backend/app/api/CONTRACT.md` for SSE events (`run_started`, `status`, `text`, `study_set`, `approval_required`, `citations`, `done`, `error`).
3. **Seed data**: `supabase/seed/`, specified in [S03](docs/specs/S03-seed-data.md) (realistic fake semester so B and C can build before connectors land).

To change one: write the proposal under "Contract change proposals" in your progress file, get the team's OK, then make it in a **separate, small PR** that updates every side that depends on it.

## Non-negotiable rules
- **The AI never touches the platforms.** Only the sync worker talks to Canvas/Gradescope/Echo360 and reads tokens/cookies. Agent tools read our database only (`fetch_latest` just queues a sync job).
- **Never store or request NetID/platform passwords; never bypass Duo.**
- **Canvas client is GET-only** (student tokens can submit work).
- **The LLM never writes URLs.** It cites `[cite:chunk_id]`; code resolves links from stored `source_url` and drops IDs not returned by tools in that run.
- **Writes need a user click** (`add_study_block` only creates `proposed` blocks; the student approves them, see [S25](docs/specs/S25-approvals-and-calendar.md)).
- **Untrusted content** (Piazza, email, any synced text) is wrapped and labeled as data in prompts.
- **Agents SDK tracing is disabled** (or sent to our own logger); never export course content to OpenAI tracing.
- **Every tool and query is scoped to the authenticated `user_id`**; Row Level Security on every table.
- **No secrets in git.** `.env` is ignored; list variables in `.env.example`.
- **Tests never call live platforms or real LLMs.** Connector tests use saved, scrubbed fixture HTML/JSON; agent tests use `ScriptedModel`; embeddings use `EMBEDDINGS_PROVIDER=fake`.

## Stack and conventions
- **Backend** (`backend/`): Python 3.12+, `uv`, FastAPI, `openai-agents`, Procrastinate, Playwright, `httpx`, Pydantic, `ruff` (lint + format), `pytest`.
- **Frontend** (`apps/web/`): Next.js (App Router) + TypeScript, `pnpm`, Tailwind, shadcn/ui, ESLint.
- **Data**: Supabase (Postgres + pgvector, Storage, Auth). Migrations as plain SQL in `supabase/migrations/`.
- Full layout and commands: [S00](docs/specs/S00-repo-scaffolding.md).
- Exact versions get pinned during scaffolding; record them here when chosen.
- Keep tool schemas simple (flat params, enums); validate with Pydantic. See [03](docs/03-architecture.md#agent-and-tools).

## End of every session: update your progress file
Edit **only** `docs/progress/<your-name>.md`. Keep it short and current: replace stale lines instead of appending forever.
- **Done** (since last update) · **In progress** · **Next** · **Blocked on / needs from others** · **Contract change proposals** · **Notes for other agents** (gotchas, decisions made locally, things others must know)

When your PR merges to `main`, also update the checkpoint and contract status in [docs/progress/README.md](docs/progress/README.md).

## Docs rule
Planning docs stay lean: one topic per doc, link instead of repeating, edit in place, one line per decision in `docs/decisions.md`.
