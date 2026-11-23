# Planning docs

> **Current phase (2026-11-23): post-hackathon deployment planning.** Read the [current audit, design and implementation plans](post-hackathon/README.md). The numbered docs and hackathon timeline below preserve earlier context; new work remains Draft until reviewed.

| Doc | What's in it |
|---|---|
| [01-vision.md](01-vision.md) | Problem, pitch, use cases, differentiation (vs. NotebookLM / Claude + connectors) |
| [02-integrations-and-auth.md](02-integrations-and-auth.md) | Each platform, how we get data out, the login/credentials problem, connector tiers |
| [03-architecture.md](03-architecture.md) | System + flow diagrams, agent and tools, tech stack, repo layout, security |
| [04-citations-and-freshness.md](04-citations-and-freshness.md) | How source links stay real and up to date (no hallucinated links) |
| [05-roadmap.md](05-roadmap.md) | Demo script, MVP cut line, roles for 3 people, 36-hour plan with checkpoints |
| [06-open-questions.md](06-open-questions.md) | Decisions we still need to make + things to test early |
| [07-sync-and-storage.md](07-sync-and-storage.md) | Why we sync instead of pulling live, the sync pipeline, where data/files/links are stored |
| [08-development-workflow.md](08-development-workflow.md) | **How we build:** spec → tests → code, stages, testing strategy, Definition of Done, agent prompt |
| [specs/](specs/README.md) | **Every feature's spec** (S00–S34): inputs, outputs, interfaces, diagrams, test plans |
| [hackathon.md](hackathon.md) | **Deadlines, rules, judging criteria, prize categories** |
| [pitch/](pitch/pitch.md) | **Pitch kit** (demo script, judge Q&A, what works) + [Devpost draft](pitch/devpost.md) |
| [devlog.md](devlog.md) | **Relay baton**: session-by-session log, newest entry = current state + next steps |
| [handoff/](handoff/start-prompt.md) | Copy-paste START and HANDOFF prompts (Claude Code + Codex) |
| [progress/](progress/README.md) | Live status: checkpoints, contracts, each person's progress file |
| [research/](research/mcp-servers-review.md) | Reviews of third-party code (MCP servers for Gradescope/Piazza/Canvas) |
| [decisions.md](decisions.md) | Running log of what we've decided and why |

**Docs 01–07** explain the *why* and the big picture. **Specs** are the *exact what* for building. If they disagree, fix whichever is wrong in the same PR.

**Keeping these lean:** each topic lives in exactly one doc; other docs link to it instead of repeating it. When an idea changes, edit it in place rather than appending. Decisions get one line in the log.

**How to contribute ideas:** edit the relevant doc and open a PR, or add to [06-open-questions.md](06-open-questions.md) / open a GitHub Issue.
