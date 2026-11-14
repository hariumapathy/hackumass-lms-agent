# Start-of-session prompt

Paste this as the first message on a new laptop/session (works in **Codex** and **Claude Code**; in Claude Code you can also type `/start`). Replace `<name>` with `hari`, `neal` or `soumith`.

```text
Start session. I am <name>; my branch is dev/<name>.
Follow AGENTS.md → "Relay sessions: START" exactly:
1. git fetch origin, check out dev/<name>, merge origin/main (stop and tell me if there are conflicts).
2. Read AGENTS.md, the newest 3 entries of docs/devlog.md, docs/progress/README.md and all three
   person files, docs/specs/README.md, every spec in the current stage, and the latest lines of
   docs/decisions.md.
3. Run make setup && make test. Report failures first.
4. Add a new devlog entry header for this session (time, laptop, tool + model, branch, hour of 36).
5. Give me a 5-line briefing (stage, done, in progress and by whom, your next step, blockers),
   then continue the "Next steps" from the newest devlog entry. Follow the specs, tests first,
   commit + push after each verified piece, and keep the devlog updated as you go.
```
