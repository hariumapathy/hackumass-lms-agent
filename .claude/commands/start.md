---
description: Start a relay session (sync with main, read context, brief, continue)
argument-hint: <name: hari|neal|soumith>
---
Start session. I am $ARGUMENTS; my branch is dev/$ARGUMENTS.

Follow AGENTS.md → "Relay sessions: START" exactly, as written in docs/handoff/start-prompt.md:
sync dev/$ARGUMENTS with origin/main, read AGENTS.md + newest 3 devlog entries + all progress files +
spec index + current-stage specs + latest decisions, run `make setup && make test`, add a devlog entry
header, brief me in 5 lines, then continue the next steps from the newest devlog entry.
