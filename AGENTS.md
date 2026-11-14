# AGENTS.md: context for coding agents

This file is for **any coding agent** working in this repo (Claude Code, Codex, Cursor, Copilot, Gemini, ...). Each of the 3 teammates uses their own agent on their own branch. Read this whole file before making changes.

## Project in one paragraph
HackUMass 2026 (36 hours, team of 3). An AI study agent for UMass students: a **sync worker** copies each student's Canvas, Gradescope and Echo360 data into Supabase; a **Python agent** (OpenAI Agents SDK) answers questions, builds study plans/quizzes/flashcards with verified citations, and shows a Today view of deadlines; a **Next.js** frontend is the UI.

## Current status
**Don't trust this line for details; read the newest entry in [docs/devlog.md](docs/devlog.md).** Summary: Stage 0 in progress (S00 scaffolding built, S02 API contract being built). Do not assume a file, package or endpoint exists; check first.

## ⚡ Relay sessions: START and HANDOFF (mandatory)
We build as a **relay**: one laptop/agent works until its usage limit runs out, then the next laptop continues (Hari → Neal → Soumith → Hari ...), mixing **Claude Code and Codex**. An agent can be cut off at any moment, so **the repo must always be ready for the next agent**.

**START of every session** (human says "start session", or runs [docs/handoff/start-prompt.md](docs/handoff/start-prompt.md), or `/start` in Claude Code):
1. `git fetch origin` → check out **your own branch** (`dev/<name>`) → `git merge origin/main` (resolve conflicts before anything else).
2. Read, in order: this file → the **newest 3 entries** of [docs/devlog.md](docs/devlog.md) → [docs/progress/README.md](docs/progress/README.md) and **all three** person files → [docs/specs/README.md](docs/specs/README.md) → every spec in the current stage → [docs/decisions.md](docs/decisions.md) (latest lines).
3. `make setup && make test`. If tests fail on a fresh `main`, fixing that is the first task.
4. Tell your human, in 5 lines max: current stage, what's done, what's in progress (and by whom), what you'll do next, any blockers. Then continue the **"Next"** list from the newest devlog entry unless your human says otherwise.

**DURING the session: log as you go** (you may be cut off without warning):
- After **each spec or meaningful piece** (or at least every ~45 min): tests + lint pass → commit → `git push` → append/update your devlog entry → update your progress file and the spec's status.
- Never leave important work only on the local disk. Small commits pushed often beat one big commit.

**HANDOFF at the end** (human says "handoff" / "wrap up", or runs [docs/handoff/handoff-prompt.md](docs/handoff/handoff-prompt.md), or `/handoff` in Claude Code; also do it yourself if you sense the session is ending):
1. `make test && make lint`. If something is broken and can't be fixed in a few minutes, commit it on your branch with a clear **"WIP / broken: why"** note instead of merging.
2. Write the devlog entry (template in [docs/devlog.md](docs/devlog.md)): what was done (spec IDs, commits), decisions/design changes, roadblocks, **exact next steps** in order, gotchas.
3. Update your progress file, spec statuses, and the [spec index](docs/specs/README.md).
4. Commit, push, open (or update) a PR into `main`, and **merge it if tests and lint pass**, so the next laptop starts from an up-to-date `main`. (Relay rule: green self-merges are allowed at handoff; red work stays on the branch.)
5. Tell your human: "Handoff complete. Next laptop: run the start prompt." plus the top 3 next steps.

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
| [docs/devlog.md](docs/devlog.md) | **Session-by-session log: newest entry = current state + next steps** |
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
| Hari | @hariumapathy | `dev/hari` | **B**: agent and API | [docs/progress/hari.md](docs/progress/hari.md) |
| Neal | @nealp | `dev/neal` | **A**: data and sync | [docs/progress/neal.md](docs/progress/neal.md) |
| Soumith | @Soumith-Madadi | `dev/soumith` | **C**: frontend and product | [docs/progress/soumith.md](docs/progress/soumith.md) |

Roles ([05](docs/05-roadmap.md#roles)): **A** data and sync (`supabase/`, `backend/app/connectors/`, `backend/app/sync/`) · **B** agent and API (`backend/app/api/`, `backend/app/agent/`) · **C** frontend and product (`apps/web/`). Shared backend code (`backend/app/core/`, `backend/app/db/`) is changed in small PRs with a heads-up.

**Roles are a default, not a wall.** What matters is finishing **stage by stage**, following the specs. If you're unblocked early, pick up another `Ready` spec **in the current stage** (never a later stage while the current one is unfinished):
1. **Claim it first**: tell the team, add it under "In progress" in your progress file, and check nobody else's progress file already claims it.
2. Work on your own branch; touching another role's folders is fine for a claimed spec, but say so in the PR.
3. Prefer helping finish the current checkpoint (tests, fixes, reviews) over starting something new.

## Git workflow
- Work on your personal branch (`dev/<name>`), or short-lived feature branches off it (`<name>/<feature>`).
- **Bring in `main` often** (at least every few hours): `git fetch origin && git merge origin/main`. Prefer merge over rebase on branches others may have pulled.
- **Open a PR into `main`** whenever a piece works end to end, and at minimum before each checkpoint (H10, H18, H24). Small PRs merge easily; big ones conflict.
- Never push directly to `main`. Never force-push a branch someone else uses.
- Agents: committing and pushing **your own branch** after each verified piece is expected (relay mode, see above). Merging into `main` happens at handoff, only when tests and lint pass. Never force-push.
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
- Pinned versions and why: [S00 implementation notes](docs/specs/S00-repo-scaffolding.md#implementation-notes-pinned-versions-2026-11-14). **Next.js 16**: read `apps/web/AGENTS.md` before frontend work. Node 20 is supported; don't upgrade test tooling past the Node-20-compatible versions without the team.
- Commands: `make setup | db | db-reset | api | worker | web | test | lint | types`.
- Keep tool schemas simple (flat params, enums); validate with Pydantic. See [03](docs/03-architecture.md#agent-and-tools).

## Roadblocks and design changes: report them, don't absorb them
Your human and the rest of the team must always know when the plan meets reality.
- **Roadblock** (blocked > 30 min, a platform behaves differently than the spec assumes, a test can't be written, a dependency isn't ready): **stop and tell your human right away**, with what you tried and 1–2 options. Record it under "Blocked on" in your progress file.
- **Design or implementation change** (anything that differs from a spec or planning doc, even if it seems small: a new field, a different library, a changed endpoint, a dropped rule): **ask your human before doing it.** Once agreed, in the same PR: update the spec (and the planning doc if affected), add one line to [docs/decisions.md](docs/decisions.md), and note it under "Notes for other agents" in your progress file.
- **Contract change** (schema, API/SSE, seed): as above **plus** the whole team agrees first (see Contracts).
- **Spike results** (e.g. the Echo360 questions in S15, Gradescope selectors in S14): write them into the spec's results section as soon as you have them.
- Never silently work around a spec. A quick question now is cheaper than a broken merge later.

## End of every session: update your progress file
Edit **only** `docs/progress/<your-name>.md`. Keep it short and current: replace stale lines instead of appending forever.
- **Done** (since last update) · **In progress** · **Next** · **Blocked on / needs from others** · **Contract change proposals** · **Notes for other agents** (gotchas, decisions made locally, things others must know)

When your PR merges to `main`, also update the checkpoint and contract status in [docs/progress/README.md](docs/progress/README.md).

## Docs rule
Planning docs stay lean: one topic per doc, link instead of repeating, edit in place, one line per decision in `docs/decisions.md`.
