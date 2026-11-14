# HackUMass LMS Agent

**One login, every class.** An AI study partner that already knows your Canvas, Gradescope, Piazza, Echo360 lectures and more. Built at HackUMass 2026.

> **Status: planning.** Start with the [planning docs](docs/README.md). Nothing is locked yet; add ideas to [open questions](docs/06-open-questions.md).

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

## Architecture (draft)
```
Canvas token / Cloud browser / Extension ──► Sync + Ingest ──► Postgres + pgvector
                                             (normalize, dedupe,      │
                                              diff, chunk, embed)     ▼
Next.js app (Today · Study · Chat · Settings · .ics) ◄── Agent (Vercel AI SDK) ◄── any model
```
Details: [docs/03-architecture.md](docs/03-architecture.md)

## Planned layout
```
apps/web             Next.js + Tailwind + shadcn/ui
apps/extension       Chrome MV3 (stretch)
services/sync        Sync workers + cloud-browser connectors
packages/agent       Agent tools, prompts, citation validation
packages/connectors  Canvas, Gradescope, Echo360, Piazza parsers
db/                  Schema + migrations
docs/                Planning docs
```

## Team
- [@hariumapathy](https://github.com/hariumapathy)
- [@nealp](https://github.com/nealp)
