# 03 — Architecture

> Draft to guide implementation. Dashed lines = stretch. Open questions ([06](06-open-questions.md)) may change details, not the overall shape.

## System diagram

```mermaid
flowchart TB
  subgraph STUDENT["Student"]
    WEB["Web app in browser"]
    CAL["Calendar app<br/>Google / Outlook / Apple"]
    OTHERAI["Claude / ChatGPT"]
  end

  subgraph APP["Next.js app on Vercel"]
    UI["UI: Onboarding, Today, Course,<br/>Study, Chat, Settings"]
    CONNECT["Connect API<br/>save Canvas token, start live login"]
    CHAT["Chat API<br/>agent harness: Vercel AI SDK"]
    TOOLS["Agent tools<br/>read our database only"]
    CITE["Citation validator"]
    ICS["Calendar feed<br/>private .ics URL"]
    MCP["MCP server<br/>same tools, for other AI apps"]
  end

  LLM["Model providers<br/>chat: student's choice (Claude, GPT, Gemini, Ollama)<br/>embeddings: one fixed model"]

  subgraph SUPA["Supabase"]
    AUTH["Auth<br/>Google, magic link"]
    DB[("Postgres + pgvector<br/>courses, items, materials,<br/>posts, changes, chunks")]
    FILES[("Storage<br/>original files, versions")]
    SECRETS[("Encrypted secrets<br/>tokens, session cookies")]
    QUEUE[("Job queue<br/>pg-boss")]
  end

  subgraph WORKER["Sync worker: Node on Railway / Render"]
    SCHED["Scheduler"]
    CANVASC["Canvas connector<br/>token, GET only"]
    BROWSERC["Browser connectors: Playwright<br/>Gradescope, Echo360, Piazza"]
    LIVE["Live-view login<br/>shown inside the web app"]
    PIPE["Pipeline: normalize, diff, merge,<br/>parse, chunk, embed"]
  end

  subgraph LMS["Student platforms"]
    CANVAS["Canvas API"]
    GS["Gradescope"]
    ECHO["Echo360"]
    PIAZZA["Piazza"]
    SSO["UMass SSO + Duo"]
  end

  WEB --> UI
  UI --> AUTH
  UI --> CHAT
  UI --> CONNECT
  CHAT <--> LLM
  CHAT --> TOOLS
  CHAT --> CITE
  TOOLS --> DB
  TOOLS -- "refresh_course" --> QUEUE
  CITE --> DB
  CONNECT --> SECRETS
  CONNECT --> QUEUE
  CAL -- "subscribes" --> ICS
  ICS --> DB
  OTHERAI -.-> MCP
  MCP -.-> TOOLS

  QUEUE --> SCHED
  SECRETS -- "tokens, cookies" --> SCHED
  SCHED --> CANVASC
  SCHED --> BROWSERC
  LIVE --> SSO
  LIVE -- "saves cookies" --> SECRETS
  CANVASC --> CANVAS
  BROWSERC --> GS
  BROWSERC --> ECHO
  BROWSERC -.-> PIAZZA
  CANVASC --> PIPE
  BROWSERC --> PIPE
  PIPE -- "embeddings" --> LLM
  PIPE --> DB
  PIPE --> FILES
```

**The one rule the diagram encodes:** the AI never touches the platforms. The **sync worker** (plain code, no AI) is the only thing that talks to Canvas/Gradescope/Echo360 and the only thing that reads tokens and cookies. The **agent** only reads our database. A malicious Piazza post can't make the AI submit anything, because no tool can. Sync details: [07](07-sync-and-storage.md).

## Key flows

**Connect a platform** (Gradescope shown; Canvas is just "paste token → validate → save → queue first sync")
```mermaid
sequenceDiagram
  actor S as Student
  participant UI as Web app
  participant W as Sync worker
  participant P as Gradescope + UMass SSO
  participant DB as Supabase
  S->>UI: Click "Connect Gradescope"
  UI->>W: Start live-view browser session
  W->>P: Open login page
  S->>P: Log in through live view, approve Duo on phone
  W->>DB: Save session cookies (encrypted)
  W->>DB: Queue first sync
  UI-->>S: "Gradescope connected, 4 courses"
```

**Ask a question**
```mermaid
sequenceDiagram
  actor S as Student
  participant H as Agent harness
  participant M as Chat model
  participant T as Tools
  participant DB as Supabase
  S->>H: "Prep me for the CS 311 midterm"
  H->>M: Conversation + tool list
  M->>H: call get_items(course, type: exam)
  H->>T: run
  T->>DB: query
  DB-->>H: Midterm 1, Nov 20 (moved from Nov 18)
  M->>H: call search_materials(course, "midterm topics")
  H->>T: run
  T->>DB: vector search
  DB-->>H: passages with chunk IDs
  M->>H: answer citing [cite:chunk_8812]
  H->>DB: validate citation IDs, look up links
  H-->>S: Streamed study plan with verified links
```

## Agent and tools

**Harness = the loop around the model.** It sends the model the conversation plus a tool list; the model asks to call a tool; the harness runs it and returns the result; repeat until the model answers (step limit ~8). The **Vercel AI SDK** gives us this loop, one interface for every model provider, streaming to React, and structured output (quizzes/flashcards as data, not prose).

**Tools are organized by action, not by platform.** Sync already merged every platform into the same tables, so one `search_materials` covers Canvas files, Echo360 transcripts and Piazza posts; the platform is just a filter.

| Tool | Does |
|---|---|
| `get_items(course?, type?, from?, to?, source?)` | Deadlines, exams, quizzes |
| `get_changes(since?, course?)` | Moved deadlines, edited announcements |
| `search_materials(query, course?, kind?, source?)` | Semantic search over slides, transcripts, posts; returns passages + chunk IDs |
| `get_material(id, pages? or time range?)` | Read a full section (e.g. slides 10–20) after search finds it |
| `get_course_overview(course)` | Syllabus, grading, schedule, staff |
| `get_grades(course?)` | Scores and weights (stretch) |
| `refresh_course(course)` | Ask the sync worker for an update now |
| `create_study_set(type, ...)` | Study plan / quiz / flashcards as structured data for the UI |
| `add_study_block(...)` | Add to the calendar feed; **requires the student's click** |

**Why ~9 tools, not dozens:** more tools makes models *worse* at choosing (overlapping tools get confused, smaller/local models degrade fast) and every tool definition costs tokens on every request. Breadth comes from parameters (filters), not more tools. Add a tool only for a genuinely new *kind of action*. If the list grows past ~15, load tools per mode (study vs. planning) instead of all at once.

**MCP:** our own agent calls tools as plain functions (simpler, faster). As a stretch, we expose the **same tools as one MCP server over our combined data**, so students can use their organized course data inside Claude or ChatGPT. Not one MCP server per platform: that would bring back live pulling and give the AI platform access.

## Tech stack (proposed, not locked)

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js + Tailwind + shadcn/ui | Fast modern UI |
| App auth | Supabase Auth (Google + magic link) | One click for students |
| Agent harness | **Vercel AI SDK** (optionally **Mastra** on top) | Open source, TypeScript, tool loop, streaming, MCP, multi-provider |
| Models | AI SDK providers (or LiteLLM / OpenRouter) | Claude, GPT, Gemini, local Ollama, chosen in settings |
| Data | Supabase: Postgres + pgvector, Storage, encrypted secrets | One service; see [07](07-sync-and-storage.md) |
| Sync | Node worker + pg-boss; Canvas via fetch; others via Playwright | Deterministic, no AI driving browsers |
| Doc parsing | pdf-parse / markitdown / unstructured | Slides → text passages |
| Hosting | Vercel (web) + Supabase + Railway / Render / Fly.io (worker) | Minimal devops |

**Language:** leaning TypeScript everywhere. If one teammate is much stronger in Python, the agent could sit behind FastAPI instead.

### Agent harness options considered

| Option | Verdict |
|---|---|
| **Vercel AI SDK / Mastra** | ✅ Recommended. Built for custom tools + streaming to a web app + many providers |
| LangGraph / Pydantic AI | ✅ Good if we go Python |
| **OpenAI Codex** (CLI + SDK, Apache-2.0, supports custom providers) | ❌ Not as the core. It's a *coding* agent (file edits, shell, repo sandbox). Fine as a dev tool for us |
| Claude-only / OpenAI-only agent SDKs | ❌ Conflicts with model choice |
| LibreChat / Open WebUI | Fallback only: could host our MCP server if custom chat runs late |

## Where each piece lives in the repo

| Component | Folder |
|---|---|
| UI, Connect API, Chat API, calendar feed, MCP endpoint | `apps/web` |
| Agent tools, prompts, citation validator | `packages/agent` |
| Canvas / Gradescope / Echo360 / Piazza fetch + normalize | `packages/connectors` |
| Scheduler, pipeline, live-view login | `services/sync` |
| Schema, migrations, Row Level Security policies | `db/` |
| Browser extension | `apps/extension` (stretch) |

## Security and privacy
- **AI never sees credentials**; tools are read-only except `add_study_block`, which needs a click.
- **Prompt injection:** content from Piazza/email is wrapped and labeled as untrusted data in prompts.
- **One fixed embedding model**, independent of the chat model, so switching models doesn't require re-embedding.
- **Data responsibility:** encryption at rest (incl. tokens and cookies); "Delete my data" removes every row, file and secret; "Disconnect" stops sync and deletes that credential; keep old versions only for the current semester; local/campus-hosted model option for sensitive materials.
- **Copyright:** lecture slides are course property; personal study use only, no sharing features.
