# Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-11-13 | Repo `hariumapathy/hackumass-lms-agent`, public | Hackathon submissions are often required to be public; easy for judges |
| 2026-11-13 | Never store platform passwords | SSO + Duo makes it impossible headlessly; FERPA/ToS; adoption blocker |
| 2026-11-13 | Sync first, agent second; deterministic dashboard | Reliability, cost, model-agnostic; avoids invented deadlines |
| 2026-11-14 | **Echo360 is in scope** | Lecture transcripts + timestamped citations are a strong, differentiated use case |
| 2026-11-14 | Connector tiers: official API → cloud browser session → extension (stretch) | Agent keeps working with the laptop closed; extension-only needs the browser open |
| 2026-11-14 | Not using Codex as the core agent harness (leaning Vercel AI SDK / Mastra) | Codex is open source but built as a coding agent; poor fit for custom tools + web streaming + model choice |
| 2026-11-14 | LLM cites by chunk ID; links rendered from stored platform-ID URLs and validated | Hallucinated links become structurally impossible; staleness handled by sync status + tombstones |
| 2026-11-14 | Canvas via personal access token (confirmed available, 90-day max); renewal reminder at ~day 80 | Official API, server-side, no browser needed |
| 2026-11-14 | Canvas client is read-only (GET only) | Student tokens can't be scoped and could otherwise submit work |
| 2026-11-14 | No storing NetID passwords, no getting around Duo | Duo still needs a phone approval anyway; bypassing it likely violates UMass policy; huge breach liability; kills adoption |
| 2026-11-14 | Background sync + targeted live refresh, not live pulling | Search, change detection, merging and instant dashboard all need a stored copy |
| 2026-11-14 | Supabase for everything stored (Postgres + pgvector, Storage, encrypted secrets); separate Node sync worker | One service; Vercel can't run long syncs or Playwright |
| 2026-11-14 | Email is a nice-to-have: try Microsoft sign-in first, fall back to manual forward + seeded demo emails | Tenant may block app consent and external forwarding; Canvas announcements already cover most course email |

_Still in planning — stack, roles and final MVP scope not yet locked. See [06-open-questions.md](06-open-questions.md)._
