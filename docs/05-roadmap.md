# 05 — Roadmap

> Draft. Will be revised once open questions are settled and both teammates weigh in.

## Demo script first (write in hour 1, build backward)
1. Sign in → connect Canvas (token) → log in to Gradescope/Echo360 via embedded live browser with a Duo push → "4 courses, 23 items, 12 lectures synced."
2. **Today view:** ranked deadlines, a "changed" badge on a moved exam, a source link on every item.
3. **"Prep me for the CS 311 midterm"** → study plan + quiz + flashcards, each citing the exact slide or lecture timestamp.
4. **"Why trust this":** click citations live (slide, Echo360 timestamp, edited announcement).
5. Switch the model in settings, ask again.
6. Subscribe to the `.ics` feed → deadlines appear in their calendar.

## MVP cut line
**Must have:** Canvas (tier 1) + Gradescope and Echo360 (tier 2) · Today view · chat and study mode with verified citations · `.ics` feed · model picker · seeded backup account.

**Stretch, in order:** Piazza → in-Canvas side panel / extension → Campuswire → email → grade tracking.

**Scope warning:** six integrations in 36 hours with two people won't happen. Do 2–3 well.

## 36-hour plan (2 people)
Person A = data and connectors (Python sync worker) · Person B = frontend + agent API (Next.js + FastAPI). The DB schema in `db/` is the contract between them; agree on it in hour 1.

| Hours | A — data and connectors | B — frontend and agent |
|---|---|---|
| 0–3 | Repo, DB schema + migrations, worker skeleton + job queue, Canvas token sync | Next.js shell, Supabase auth, FastAPI skeleton verifying the JWT, Today view on mock data |
| 3–10 | Canvas courses/assignments/announcements/files; parsing + embeddings | Agents SDK chat with tools (get_items, search_materials, get_changes), SSE streaming into the chat UI |
| 10–18 | Cloud-browser login + Gradescope sync; Echo360 transcripts; `fetch_latest` jobs | Study mode: plan, quiz, flashcards (structured output); citation guardrail + citation chips |
| 18–24 | `.ics` feed, dedupe/merge, change detection | Model picker, onboarding "connect your classes" checklist |
| 24–30 | Seed realistic demo account (backup) | UI polish, loading states, mobile layout |
| 30–36 | Bug fixes, demo script, slides, 2-min video | Same |

Repo layout: see [03](03-architecture.md#where-each-piece-lives-in-the-repo).
