# S00 — Repo scaffolding and tooling

| | |
|---|---|
| **Status** | Draft |
| **Stage** | 0 |
| **Role** | All (one person drives, others review) |
| **Depends on** | — |
| **Folders** | repo root, `apps/web/`, `backend/`, `supabase/`, `.github/` |

## Purpose
Create the empty-but-runnable skeleton so all three roles can start in parallel: every app boots, tests run, lint runs, CI runs on PRs, and the local database starts.

## Inputs
- Decided stack ([03](../03-architecture.md#tech-stack)).
- Developer machines: Python 3.12+, `uv`, Node 20+, `pnpm`, Docker (for local Supabase), Supabase CLI.

## Outputs
A repo where these commands work from a fresh clone:

| Command | Does |
|---|---|
| `just setup` | Installs Python deps (`uv sync`), JS deps (`pnpm install`), Playwright browsers |
| `just db` | Starts local Supabase (`supabase start`) and applies migrations |
| `just db-reset` | Drops and recreates local DB from migrations + loads seed (S03) |
| `just api` | Runs FastAPI with reload on `:8000` |
| `just worker` | Runs the sync worker (Procrastinate) |
| `just web` | Runs Next.js on `:3000` |
| `just test` | Backend + frontend tests |
| `just lint` | `ruff check`, `ruff format --check`, `pyright`, `eslint`, `tsc --noEmit` |
| `just types` | Regenerates frontend API types from FastAPI's OpenAPI schema (S02) |

(`just` is a small command runner; a `Makefile` is an acceptable substitute on machines without it.)

## Interface: repo layout
```
.
├── AGENTS.md / CLAUDE.md        # agent context
├── justfile                     # commands above
├── .env.example                 # every env var, no values
├── .github/
│   ├── workflows/ci.yml         # lint + tests on PRs
│   └── pull_request_template.md
├── apps/web/                    # Next.js (App Router, TS), pnpm
│   ├── src/app/                 # routes (S30)
│   ├── src/components/
│   ├── src/lib/api/             # generated types + API client (S02)
│   └── tests/                   # vitest + playwright
├── backend/                     # uv project, package name `app`
│   ├── pyproject.toml
│   ├── app/
│   │   ├── api/                 # FastAPI routers (S20, S02)
│   │   ├── agent/               # runtime, tools/, prompts/, citations (S21–S26)
│   │   ├── connectors/          # canvas/, gradescope/, echo360/ (S11–S15)
│   │   ├── sync/                # worker, jobs, pipeline, processing (S10, S12, S16)
│   │   ├── db/                  # connection pool, repositories, models
│   │   ├── core/                # settings, clock, crypto, logging, errors
│   │   └── cli.py               # `uv run app seed`, `uv run app evals`
│   ├── evals/                   # model evals (S26), not run in CI
│   └── tests/
│       ├── unit/ connector/ integration/ runtime/
│       └── fixtures/            # scrubbed platform HTML/JSON
└── supabase/                    # Supabase CLI project
    ├── config.toml
    ├── migrations/              # SQL, source of truth (S01)
    └── seed/                    # seed fixtures (S03)
```

## Environment variables (`.env.example`)
| Variable | Used by | Notes |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | web | Public |
| `SUPABASE_SERVICE_ROLE_KEY` | api, worker | Server only, never in web |
| `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL` | api | Verify user JWTs (S20) |
| `DATABASE_URL` | api, worker | Postgres connection (pooler) |
| `ENCRYPTION_KEY` | api, worker | Fernet key for tokens/cookies (S10) |
| `OPENAI_API_KEY` | api, worker | Default chat model + embeddings |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | api | Optional, for model picker (S26) |
| `EMBEDDINGS_PROVIDER` | api, worker | `openai` (default) or `fake` (tests) |
| `NEXT_PUBLIC_API_URL` | web | FastAPI base URL |
| `WEB_ORIGIN` | api | CORS allow-list |
| `BROWSER_PROVIDER` | worker | `local` (headed Playwright) or `hosted` (S13) |

## Behavior and rules
1. Python: `uv`, Python 3.12+, `ruff` (lint + format), `pyright` (basic mode), `pytest` + `pytest-asyncio`, `respx`.
2. Frontend: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, ESLint, `vitest`, React Testing Library, MSW, Playwright.
3. CI (`.github/workflows/ci.yml`) on every PR: lint + type check + unit + connector + runtime + component tests. Integration tests run in CI with `supabase start` if it fits in time; otherwise locally before merge.
4. Pin exact versions in lockfiles (`uv.lock`, `pnpm-lock.yaml`); record major versions in AGENTS.md.
5. `.env` is git-ignored. CI uses fake values.
6. Each app has one trivial passing test so CI is green from the start.

## Errors and edge cases
| Case | Expected behavior |
|---|---|
| Docker not installed | `just db` prints a clear message; teammates can point `DATABASE_URL` at the shared hosted dev project instead |
| Windows dev machine | All commands work in Git Bash / PowerShell; avoid bash-only scripts in `justfile` recipes where possible |

## Acceptance criteria
- [ ] Fresh clone → `just setup && just db && just test` passes on all three laptops
- [ ] `just api`, `just worker`, `just web` each start without errors
- [ ] `GET http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] CI runs on a PR and is green
- [ ] `.env.example` lists every variable above

## Test plan
| ID | Test | Type |
|---|---|---|
| S00-T01 | Backend smoke test: app imports, `/health` returns 200 | unit |
| S00-T02 | Frontend smoke test: home page renders | component |
| S00-T03 | CI workflow runs lint and tests on a test PR | manual |

## Out of scope
Any feature code. Deployment (done at H24–30: Vercel for web, Railway/Render for `api` and `worker`).
