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
| [PyJWT](https://github.com/jpadilla/pyjwt) + [cryptography](https://github.com/pyca/cryptography) | MIT / Apache-2.0 or BSD | Verifying Supabase sign-in tokens (S20) |
| [psycopg 3](https://www.psycopg.org/) + psycopg-pool | LGPL-3.0 (used unmodified as a library) | Postgres access (S20) |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 (used unmodified as a library; our repo is public) | PDF text extraction per page (S12) |
| [python-pptx](https://github.com/scanny/python-pptx) | MIT | Slide text + speaker notes extraction (S12) |
| [tiktoken](https://github.com/openai/tiktoken) | MIT | Token counting for chunking (`cl100k_base`, S12) |
| pytest, pytest-asyncio, respx, ruff, pyright | MIT / Apache-2.0 / BSD | Backend tests and linting (dev only) |
| Next.js (create-next-app template), React, Tailwind, Vitest, Testing Library | MIT | Frontend |
| Supabase CLI | MIT | Local database |

## Reference only (no code copied)
| Source | License | Used for |
|---|---|---|
| [vishalsachdev/canvas-mcp](https://github.com/vishalsachdev/canvas-mcp) | MIT | Checking Canvas API endpoints and edge cases for S11 |
