# Third-party code

HackUMass rules require documenting all external code and mentioning it during judging. Every reused or vendored piece is listed here **in the same PR that adds it** (also in [docs/pitch/devpost.md → Credits](docs/pitch/devpost.md#credits-external-code)).

## Vendored (copied) code
Copied files live in `backend/app/connectors/<platform>/_vendored/`, each with a header naming the source, commit and license, plus a copy of the upstream LICENSE.

| Source | License | Commit | What we copied | Spec | Status |
|---|---|---|---|---|---|
| [Yuanpeng-Li/gradescope-mcp](https://github.com/Yuanpeng-Li/gradescope-mcp) | MIT, (c) 2026 Yuanpeng Li | `f8a46c8` | `tools/courses.py` course-list parser by role → `backend/app/connectors/gradescope/_vendored/courses.py`; `auth.py` logged-out/session-expiry checks → `_vendored/auth_checks.py` (license: `_vendored/LICENSE-gradescope-mcp`). Date helpers not needed (Gradescope dates carry offsets; naive ones handled in our code). Password login not copied | S14 | vendored |
| [profess/piazza-mcp](https://github.com/profess/piazza-mcp) | MIT, (c) 2026 mkslge | `782f62c` | `services/piazza/client.py` async client wrapper → `backend/app/connectors/piazza/_vendored/client.py` (password login removed, `from_storage_state()` + 1 req/s throttle added); `services/piazza/normalizer.py` (incl. source URL builder, HTML → text) → `_vendored/normalizer.py`; `models/piazza.py` → `_vendored/models.py` (license: `_vendored/LICENSE-piazza-mcp`). MCP server, tools and `.env` credentials not copied | S17 | vendored |

## Libraries (dependencies)
| Library | License | Used for |
|---|---|---|
| [gradescopeapi](https://github.com/nyuoss/gradescope-api) 1.8.1 (pinned) | MIT | Gradescope session container + student-view assignment parser (S14); its password login is never called |
| [Playwright for Python](https://github.com/microsoft/playwright-python) | Apache-2.0 | Live login window + saved browser session (S13) |
| beautifulsoup4, requests, python-dateutil (via gradescopeapi) | MIT / Apache-2.0 / BSD-or-Apache-2.0 | HTML parsing, HTTP, date parsing (S14) |
| [piazza-api](https://github.com/hfaran/piazza-api) 0.16.0 | MIT | Piazza read access via the student's saved session cookies (S17); its `user_login` (password) is never called |
| FastAPI, Pydantic, httpx, uvicorn, OpenAI Agents SDK, Procrastinate, Playwright | MIT / Apache-2.0 / BSD | Backend |
| [PyJWT](https://github.com/jpadilla/pyjwt) + [cryptography](https://github.com/pyca/cryptography) | MIT / Apache-2.0 or BSD | Verifying Supabase sign-in tokens (S20) |
| [psycopg 3](https://www.psycopg.org/) + psycopg-pool | LGPL-3.0 (used unmodified as a library) | Postgres access (S20) |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (`openai-agents`) + `openai` | MIT / Apache-2.0 | Agent harness + Gemini via its OpenAI-compatible API (S22) |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | MIT | Citation quote check (S23) |
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
