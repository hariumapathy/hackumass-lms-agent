# Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-11-13 | Repo `hariumapathy/hackumass-lms-agent`, public | Hackathon submissions are often required to be public; easy for judges |
| 2026-11-13 | Never store platform passwords | SSO + Duo makes it impossible headlessly; FERPA/ToS; adoption blocker |
| 2026-11-13 | Sync first, agent second; deterministic dashboard | Reliability, cost, model-agnostic; avoids invented deadlines |
| 2026-11-14 | **Echo360 is in scope** | Lecture transcripts + timestamped citations are a strong, differentiated use case |
| 2026-11-14 | Connector tiers: official API → cloud browser session → extension (stretch) | Agent keeps working with the laptop closed; extension-only needs the browser open |
| 2026-11-14 | Not using Codex as the core agent harness | Open source, but built as a coding agent; poor fit for custom tools + web streaming + model choice; injection risk with shell access |
| 2026-11-14 | LLM cites by chunk ID; links rendered from stored platform-ID URLs and validated | Hallucinated links become structurally impossible; staleness handled by sync status + tombstones |
| 2026-11-14 | Canvas via personal access token (confirmed available, 90-day max); renewal reminder at ~day 80 | Official API, server-side, no browser needed |
| 2026-11-14 | Canvas client is read-only (GET only) | Student tokens can't be scoped and could otherwise submit work |
| 2026-11-14 | No storing NetID passwords, no getting around Duo | Duo still needs a phone approval anyway; bypassing it likely violates UMass policy; huge breach liability; kills adoption |
| 2026-11-14 | Background sync + targeted live refresh, not live pulling | Search, change detection, merging and instant dashboard all need a stored copy |
| 2026-11-14 | Supabase for everything stored (Postgres + pgvector, Storage, encrypted secrets); separate sync worker | One service; Vercel can't run long syncs or Playwright |
| 2026-11-14 | **Stack: Next.js (TS) frontend + Python backend** (FastAPI, OpenAI Agents SDK, Procrastinate worker, Playwright) | Team choice; Python's better PDF/slide parsing; Agents SDK has guardrails built in. DB schema is the contract between halves |
| 2026-11-14 | Curated model picker validated by a golden-question test script; simple tool schemas + Pydantic validation | Adapter-based models lose OpenAI's strict-schema guarantees; prompts behave differently per model |
| 2026-11-14 | Team of 3: roles A data and sync, B agent and API, C frontend and product; contracts (schema, API/SSE format, seed data) agreed in hours 0–2 | Parallel work without blocking; seed data lets B and C build before connectors land |
| 2026-11-14 | **Spec first, tests first, stage by stage** ([08](08-development-workflow.md), [specs](specs/README.md)); agents implement only `Ready` specs | Fewer bugs; three people + three agents stay consistent |
| 2026-11-14 | Personal branches `dev/hari`, `dev/neal`, `dev/soumith`; PRs into `main` at least per checkpoint; per-person progress files | Parallel work; no merge conflicts on status notes |
| 2026-11-14 | Study blocks use a **proposal pattern** (tool proposes, separate endpoint approves) instead of paused agent runs | Works with every model; no run-state resume |
| 2026-11-14 | `supabase/` is the DB folder (Supabase CLI layout); local Supabase for dev and integration tests | Standard tooling; one command to reset |
| 2026-11-14 | Hybrid search (vector + full-text, RRF); `chunks.id` is a short integer | Better recall; short IDs are easier for models to cite exactly |
| 2026-11-14 | Live login MVP = local headed browser on the demo machine; hosted live view is stretch | Zero infrastructure for the demo |
| 2026-11-14 | Roles: Neal A, Hari B, Soumith C; roles flexible within the current stage (claim a spec first); agents report roadblocks and ask before any design change | Finish stage by stage; no silent drift from specs |
| 2026-11-14 | Scaffolding: `make` instead of `just`; pnpm and Supabase CLI run pinned via `npx`; Next 16; Node-20-compatible test tooling | Fewer installs on three laptops; Node 20 is what we have |
| 2026-11-14 | Agents SDK tracing off (or to our own logger) | Default export would send students' course content to OpenAI |
| 2026-11-14 | Devpost category: **[HACKUMASS] Best UMass Hack** (+ automatic grand prizes) | Built for UMass students and platforms; demo and pitch use UMass-real details and the UMass adoption path |
| 2026-11-14 | **Non-technical students first:** plain-language UI, Today first, default model (choice under Settings → Advanced), Add-to-Google-Calendar button. **MVP keeps the guided Canvas token**; one-UMass-login (NetID + Duo for all platforms) is a stretch goal (S13) | Average UMass student won't handle setup; token is proven and low-risk for the demo |
| 2026-11-14 | **MCP servers: borrow the pieces** (Option A). gradescopeapi + vendored gradescope-mcp helpers in S14 with our saved session instead of passwords; piazza-api + vendored piazza-mcp client/normalizer in new S17 (stretch); canvas-mcp as S11 reference. Vendored code in `_vendored/` with headers + THIRD_PARTY_NOTICES.md | Fast connectors, no passwords, invisible to students, no architecture change |
| 2026-11-14 | **Echo360 (S15) is a stretch goal**, not MVP | Time (~15 h left); Canvas + Gradescope + slides carry the demo. Seed data keeps Echo360 transcripts so the demo can still show a lecture citation |
| 2026-11-14 | **Gemini is the default model** (free tier via Google AI Studio, `GEMINI_API_KEY`), via the Agents SDK's OpenAI-compatible endpoint; OpenAI/Claude stay optional in the picker. Embeddings: Gemini embedding model if it can output 1536 dims, else keep a 1536-dim alternative (decide in S12) | $0 for the hackathon; eligible for MLH Best Use of Gemini API. Caveat: free-tier data may be used by Google (fine for demo data; mention in privacy answer) |
| 2026-11-14 | **S20 auth:** verify Supabase tokens by their `alg`: ES256 via the project JWKS (cached 10 min), HS256 via `SUPABASE_JWT_SECRET` if set (PyJWT). `/me` routes keep S02 mock data until S01's `profiles` table exists | Hosted project signs with ES256; frontend never sees 503s before the schema lands |
| 2026-11-14 | **Default model `gemini-3.5-flash`** (2.5 closed to new keys; 3.8 overloaded on free tier). Gemini stream fix wraps the client (tool-call indexes). `CHAT_MODE=auto\|agent\|scripted`; scripted is the demo backup | Verified live; parallel tool calls work |
| 2026-11-14 | Agent tools read through a `ToolData` interface; `MockToolData` (S02 mock semester) until S01/S03, then `DbToolData`. Chat history in an in-memory store until S01 | Real agent works end to end before the DB exists; no route changes later |
| 2026-11-14 | `DATA_SOURCE=mock\|db` switches the agent's tool data + chat history between the S02 mock semester (in-memory) and the S01 DB (`DbToolData`, `DbChatStore`); account routes follow it | One switch for demo backup vs real data; mock stays the default until the hosted DB is migrated + seeded |
| 2026-11-14 | Agent tools read only our database; only the sync worker touches platforms and credentials | Security (prompt injection can't act on the LMS), speed, model-agnostic |
| 2026-11-14 | ~9 tools organized by action, not per platform | Sync already merged platforms; fewer tools = better tool choice, esp. smaller models |
| 2026-11-14 | One MCP server over our combined data (stretch), not one per platform | Lets students use their data in Claude/ChatGPT without reintroducing live pulling |
| 2026-11-14 | Agent "live pulls" = high-priority narrow sync jobs (`fetch_latest`), same worker code as scheduled sync | Keeps credentials out of the agent, results stay citable and reusable, one code path |
| 2026-11-14 | Email is a nice-to-have: try Microsoft sign-in first, fall back to manual forward + seeded demo emails | Tenant may block app consent and external forwarding; Canvas announcements already cover most course email |

| 2026-11-14 | **Merge steward:** one Claude session merges each `dev/*` branch into `main` every 15 min when CI + local checks are green, resolving conflicts on a `merge/<name>` branch (never pushes to `dev/*`); rules in [handoff/merge-steward.md](handoff/merge-steward.md) | Three people + many agents push constantly; one owner for integration avoids drift and stale `main` |
_Still in planning — stack, roles and final MVP scope not yet locked. See [06-open-questions.md](06-open-questions.md)._

| 2026-11-14 | Demo fixes authorized on main: use official UMass Canvas host `umamherst.instructure.com`; DB dashboard and disconnect; priority merge before bulk file processing; production demo UI; email sign-in with Google opt-in only when configured | Live token check exposed wrong host, mock dashboard, stale caches and merge starvation; no schema or API shape changes |

- 2026-11-14 (Neal, user workflow override): new features share `codex/calendar-piazza-ui`, one verified commit each; user reviews before merge. S25 keeps the specified private ICS approach; localhost offers download/manual import, public HTTPS is required for subscription. Ambiguous/nonexistent DST times are rejected.
- 2026-11-14 (Soumith): reviewed and approved merging `codex/calendar-piazza-ui` (S25) and `neal/s17-piazza` into main on Neal's behalf, each only after live end-to-end checks + green tests; one PR per feature.
- 2026-11-14 (Soumith): Echo360 is hidden in the UI (no connector; S15 stays stretch). Piazza gets a Connect option in Settings/onboarding with its own login wording. `CONNECTABLE_PLATFORMS` in `apps/web/src/lib/platforms.ts` is the single list. No API/schema change.
- 2026-11-15 (Soumith, Session B): submission state lives in `item_sources.raw.submitted` (no schema change); `Item.submitted` added to the API; submitted items are excluded from Today's Overdue. Canvas graded-as-missing (no hand-in) does not count; excused does.
- 2026-11-15 (Soumith, Session B): in-app file viewer = `GET /files/{material_id}` streams the student's own stored original (row-scoped, storage path from the DB row, never from the request); citations get `file_id` only for stored PDFs. The web app fetches it with the Bearer token into a blob URL and shows the browser's PDF viewer in a dialog at `#page=N` (no new library).
- 2026-11-15 (Hari, Session A): "Study" tab → **Sessions** (`/sessions`; `/study` redirects, `/study/[id]` kept). Additive API: `ConversationSummary.study_sets`, `StudySetSummary.conversation_id`, `PATCH`/`DELETE /conversations/{id}`; deleting a chat keeps its study sets (S36).
- 2026-11-15 (Soumith): the agent web-search tool (split doc Session B task 3) is **dropped**: answers stay grounded in the student's own course sources only.

- 2026-11-23 (user): begin post-hackathon **planning only**, with delegated code audits on `post-hackathon-plan/changes`; produce design and implementation/test plans before any application code. Provider/hosting/feature sequencing remains proposed pending review.

- 2026-11-23 (user planning amendment): include General and course-specific chats, optional coursework projects, aligned context/memory/tools and student-first responsive modern maroon UX; add research-backed design skill candidates and usability tests. Documentation only; no feature code authorized.

- 2026-11-24 (user): implement one fix at a time through spec/tests/design/implementation/verification and feature commits on `codex/post-hackathon-implementation`; keep Gemini now, prepare handoff before 07:00 ET, and **never merge main until user explicitly says done**. S37 adds an explicit production Settings gate and disabled browser mode, with no existing contract changes.

- 2026-11-24 (S40 review branch): durable clear-data generation/checkpoint, shared/exclusive user barriers with request-bound DB leases, idempotent file/job cleanup and worker recovery; Auth retained. Additive migration0003 requires team review before merge; object-upload orphan reconciliation remains a public-launch gate.
