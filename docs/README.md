# Planning docs

> **Status: planning.** Nothing here is locked. These docs capture the discussion so far so the whole team can review, comment, and add ideas before we scope the build.

| Doc | What's in it |
|---|---|
| [01-vision.md](01-vision.md) | Problem, pitch, use cases, differentiation (vs. NotebookLM / Claude + connectors) |
| [02-integrations-and-auth.md](02-integrations-and-auth.md) | Each platform, how we get data out, the login/credentials problem, connector tiers |
| [03-architecture.md](03-architecture.md) | System + flow diagrams, agent and tools, tech stack, repo layout, security |
| [04-citations-and-freshness.md](04-citations-and-freshness.md) | How source links stay real and up to date (no hallucinated links) |
| [05-roadmap.md](05-roadmap.md) | Demo script, MVP cut line, roles for 3 people, 36-hour plan with checkpoints |
| [06-open-questions.md](06-open-questions.md) | Decisions we still need to make + things to test early |
| [07-sync-and-storage.md](07-sync-and-storage.md) | Why we sync instead of pulling live, the sync pipeline, where data/files/links are stored |
| [decisions.md](decisions.md) | Running log of what we've decided and why |

**Keeping these lean:** each topic lives in exactly one doc; other docs link to it instead of repeating it. When an idea changes, edit it in place rather than appending. Decisions get one line in the log.

**How to contribute ideas:** edit the relevant doc and open a PR, or add to [06-open-questions.md](06-open-questions.md) / open a GitHub Issue.
