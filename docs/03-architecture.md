# 03 — Architecture

## System diagram
```
 Connectors                         Backend                          Store
 ──────────                         ───────                          ─────
 Tier 1: Canvas API token  ─┐
 Tier 2: Cloud browser      ├──►  Sync workers + Ingest API  ──►  Postgres + pgvector (Supabase)
   (Gradescope, Echo360,    │     - normalize                      Courses, Items, Events,
    Piazza)                 │     - dedupe / merge                 Materials, Announcements,
 Tier 3: Browser extension ─┘     - diff + change detection        Posts, Recordings, Chunks,
                                  - parse PDFs/PPTX/transcripts    Changes, Sources
                                  - chunk + embed                        │
                                                                         ▼
 Next.js app  ◄──────────────  Agent (Vercel AI SDK, optional Mastra)
   Today · Course · Study           tools: get_items, search_materials,
   Chat · Settings                  get_changes, get_recording_segment,
   .ics feed URL                    make_quiz, make_flashcards
                                         │
                                         ▼
                                    Any model: Claude / GPT / Gemini / Ollama
```

## Tech stack (proposed, not locked)

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js + Tailwind + shadcn/ui | Fast modern UI |
| App auth | Supabase Auth (Google + magic link) | One click for students |
| Agent framework | **Vercel AI SDK** (optionally **Mastra** on top) | Open source, TypeScript, tool loop, streaming, MCP client, multi-provider |
| Model choice | AI SDK providers (or LiteLLM / OpenRouter) | Claude, GPT, Gemini, local Ollama — chosen in settings |
| DB | Postgres + pgvector (Supabase) | Structured data + embeddings + storage in one place |
| Sync / scraping | Playwright scripts (tier 2), fetch (tier 1) | Deterministic, not LLM-driven |
| Doc parsing | pdf-parse / markitdown / unstructured | Slides → chunks |
| Connectors as tools | Each source exposed as an MCP server | Standard interface; works with any harness; good architecture story |
| Hosting | Vercel (web) + Supabase + one sync worker (Railway / Render / Fly.io) | Minimal devops; see [07](07-sync-and-storage.md#where-it-runs) |

**Language:** leaning TypeScript everywhere. Tier-2 browser scraping removes the need for the unofficial Python libraries. If one teammate is much stronger in Python, the agent could sit behind FastAPI instead.

## Agent harness — options considered

| Option | Verdict |
|---|---|
| **Vercel AI SDK / Mastra** | ✅ Recommended. Built for custom tools + streaming to a web app + many providers |
| LangGraph / Pydantic AI | ✅ Good if we go Python |
| **OpenAI Codex** (CLI + SDK, Apache-2.0, supports custom providers) | ❌ Not as the core. It's a *coding* agent: tools, sandbox and approval model assume editing files/running shell in a repo. We'd spend hours stripping that out. Fine as a dev tool for us, or a stretch "self-healing scraper" idea |
| Claude-only / OpenAI-only agent SDKs | ❌ Conflicts with model choice |
| LibreChat / Open WebUI | Fallback only: already support MCP + model choice, could host our connectors if custom chat runs late |

Sync pipeline, data model and storage layout: see [07-sync-and-storage.md](07-sync-and-storage.md).

## Security and privacy
- **Prompt injection:** Piazza posts and emails are written by other people and fed to an agent with tools. All write actions (calendar, sending anything) require an explicit user click; ingested content is wrapped and labeled as untrusted data in prompts.
- **One fixed embedding model**, independent of the chat model, so switching chat models doesn't require re-embedding.
- **Data responsibility:** encryption at rest (incl. tokens and session cookies); "Delete my data" removes every row, file and secret; "Disconnect" stops sync and deletes that credential; keep old versions only for the current semester; local/campus-hosted model option for sensitive materials.
- **Copyright:** lecture slides are course property — personal study use only, no sharing features.
