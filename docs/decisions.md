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

_Still in planning — stack, roles and final MVP scope not yet locked. See [06-open-questions.md](06-open-questions.md)._
