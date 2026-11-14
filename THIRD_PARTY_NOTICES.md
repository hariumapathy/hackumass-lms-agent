# Third-party code

HackUMass rules require documenting all external code and mentioning it during judging. Every reused or vendored piece is listed here **in the same PR that adds it** (also in [docs/pitch/devpost.md → Credits](docs/pitch/devpost.md#credits-external-code)).

## Vendored (copied) code
Copied files live in `backend/app/connectors/<platform>/_vendored/`, each with a header naming the source, commit and license, plus a copy of the upstream LICENSE.

| Source | License | Commit | What we copied | Spec | Status |
|---|---|---|---|---|---|
| [Yuanpeng-Li/gradescope-mcp](https://github.com/Yuanpeng-Li/gradescope-mcp) | MIT | `f8a46c8` | Course-list parser (by role), logged-out/session-expiry checks, (maybe) date helpers | S14 | planned |
| [profess/piazza-mcp](https://github.com/profess/piazza-mcp) | MIT | `782f62c` | Async client wrapper (login removed), normalizer, post models, source URL builder | S17 | planned (stretch) |

## Libraries (dependencies)
| Library | License | Used for |
|---|---|---|
| [gradescopeapi](https://github.com/nyuoss/gradescope-api) 1.8.x | MIT | Gradescope student-view parsing (S14) |
| [piazza-api](https://github.com/hfaran/piazza-api) 0.16.x | MIT | Piazza read access (S17, stretch) |
| FastAPI, Pydantic, httpx, uvicorn, OpenAI Agents SDK, Procrastinate, Playwright | MIT / Apache-2.0 / BSD | Backend |
| Next.js (create-next-app template), React, Tailwind, Vitest, Testing Library | MIT | Frontend |
| Supabase CLI | MIT | Local database |

## Reference only (no code copied)
| Source | License | Used for |
|---|---|---|
| [vishalsachdev/canvas-mcp](https://github.com/vishalsachdev/canvas-mcp) | MIT | Checking Canvas API endpoints and edge cases for S11 |
