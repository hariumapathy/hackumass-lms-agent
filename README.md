# HackUMass LMS Agent

**One login, every class.** An AI study partner that already knows your Canvas, Gradescope, Piazza, and lecture materials — built at HackUMass 2026.

## Problem
Course info is scattered across Canvas, Gradescope, Piazza, Campuswire, Echo360, and email. Tracking deadlines and gathering study material is manual, and general-purpose LLMs need everything uploaded by hand.

## What it does (MVP)
- **Today view** — deadlines and announcements from every source, ranked, deduplicated, each linked to its source.
- **Change detection** — "Midterm moved to Thursday" updates the item and flags it.
- **Study mode** — "Prep me for the CS 311 midterm" → study plan, practice quiz, flashcards, with slide-level citations.
- **Calendar feed** — a private `.ics` URL you subscribe to in Google/Outlook/Apple Calendar.
- **Model choice** — Claude, GPT, Gemini, or a local model via Ollama.

## How login works (no stored passwords)
Students sign in to the app, install the browser extension, and log into Canvas/Gradescope/etc. as usual (NetID + Duo). The extension reads data using the existing session and syncs it to the backend. We never see or store platform passwords.

Production path: an official LTI 1.3 app + Canvas developer key issued by university IT, with data and models on campus infrastructure.

## Architecture
```
Chrome extension (MV3) ──► Ingest API ──► Postgres + pgvector (Supabase)
  Canvas / Gradescope /     (normalize,      Courses, Items, Materials,
  Piazza / Echo360          dedupe, diff)    Posts, Chunks, Changes
                                                   │
Next.js app ◄── Agent (Vercel AI SDK; tools: get_items, search_materials,
  Today · Course · Study · Chat · Settings      get_changes, make_quiz) ◄── any model
  .ics feed
```

## Planned layout
```
apps/web          Next.js + Tailwind + shadcn/ui
apps/extension    Chrome MV3 connector
packages/agent    Agent tools + prompts
packages/connectors  Source parsers (Canvas, Gradescope, ...)
db/               Schema + migrations
```

## Status
Planning — scope being finalized. See Issues for the roadmap.

## Team
- [@hariumapathy](https://github.com/hariumapathy)
- [@nealp](https://github.com/nealp)
