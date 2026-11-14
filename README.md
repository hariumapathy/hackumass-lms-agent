# HackUMass LMS Agent

**One login, every class.** An AI study partner that already knows your Canvas, Gradescope, Piazza, Echo360 lectures and more. Built at HackUMass 2026.

> **Status: planning done, feature specs drafted, no code yet.** Builders (and your coding agents): start with [AGENTS.md](AGENTS.md).

## For builders
| Start here | |
|---|---|
| [AGENTS.md](AGENTS.md) | Rules, branches, ownership, contracts, **relay START/HANDOFF protocol**. Read by Claude Code (via `CLAUDE.md`), Codex, Cursor and others |
| [Dev log](docs/devlog.md) | Newest entry = where things stand right now |
| [Start prompt](docs/handoff/start-prompt.md) / [Handoff prompt](docs/handoff/handoff-prompt.md) | Paste at the start/end of every session on any laptop (`/start`, `/handoff` in Claude Code) |
| [Development workflow](docs/08-development-workflow.md) | Spec → tests → code, stage by stage |
| [Feature specs](docs/specs/README.md) | What to build, exactly, with test plans |
| [Progress](docs/progress/README.md) | Who's doing what, checkpoints, blockers |
| [Planning docs](docs/README.md) | Vision, architecture, decisions |

**Branches:** `dev/hari`, `dev/neal`, `dev/soumith`. Work on yours, merge `main` in often, open PRs into `main`.

## Problem
Course info is scattered across Canvas, Gradescope, Piazza, Campuswire, Echo360, and email. Tracking deadlines and gathering study material is manual, and general-purpose LLMs need everything uploaded by hand.

## What it does (MVP, draft)
- **Today view**: deadlines and announcements from every source, ranked, deduplicated, each linked to its source.
- **Change detection**: "Midterm moved to Thursday" updates the item and flags it.
- **Study mode**: "Prep me for the CS 311 midterm" produces a study plan, practice quiz and flashcards, citing the exact slide or lecture timestamp.
- **Lecture recall (Echo360)**: ask what was said in a lecture and get a timestamped link.
- **Calendar feed**: a private `.ics` URL you subscribe to in Google/Outlook/Apple Calendar.
- **Model choice**: Claude, GPT, Gemini, or a local model via Ollama.
- **Verified citations**: the AI never writes links; every reference comes from synced data.

## How login works (no stored passwords)
1. **Canvas**: official API token (server-side, always on).
2. **Gradescope / Echo360 / Piazza**: log in once through an embedded live browser view (NetID + Duo on your phone). We keep an encrypted session so syncing keeps going with your laptop closed, and ask you to reconnect when it expires.
3. **Browser extension** (stretch): syncs as you browse, and an AI side panel inside Canvas.

We never see or store platform passwords. The production path is an official LTI 1.3 app plus a Canvas developer key issued by university IT, with data and models on campus infrastructure.

## Architecture
A sync worker copies course data into Supabase; the AI agent only reads that database, never the platforms directly. Diagrams, tools and repo layout: [docs/03-architecture.md](docs/03-architecture.md).

## Team
- [@hariumapathy](https://github.com/hariumapathy)
- [@nealp](https://github.com/nealp)
- [@Soumith-Madadi](https://github.com/Soumith-Madadi)
