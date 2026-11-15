# Handoff prompt

> **Current user override (2026-11-14):** all new features stay on `codex/calendar-piazza-ui`, one verified commit per feature. Push checkpoints; do **not** merge until the user reviews the branch. This overrides the default self-merge instruction below. See [current work plan](../feature-work-plan.md).

Paste this when the session is about to end (usage running low, switching laptops). Works in **Codex** and **Claude Code** (or `/handoff` in Claude Code). Do it **early**: an agent cut off mid-handoff loses the log.

```text
Handoff now. Follow AGENTS.md → "Relay sessions: HANDOFF" exactly:
1. Run make test && make lint. If anything is red and not fixable in a few minutes, commit it on my
   branch marked "WIP / broken: <why>" and do NOT merge it.
2. Complete this session's entry in docs/devlog.md: done (spec IDs, commit hashes, PRs), in progress,
   decisions/design changes (also one line each in docs/decisions.md), roadblocks, state of main,
   exact next steps in order, gotchas.
3. Update my docs/progress/<name>.md, spec statuses, and docs/specs/README.md.
4. Commit, push, open or update the PR into main, and merge it if tests and lint are green.
5. Reply with: "Handoff complete", the merge status, and the top 3 next steps for the next laptop.
```
