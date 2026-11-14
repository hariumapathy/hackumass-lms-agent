# 01 — Vision

## Problem
Students at UMass (and most universities) juggle many platforms per semester:

- **Canvas** — assignments, files/slides, announcements, quizzes, calendar
- **Gradescope** — submissions, grades, some assignment deadlines
- **Piazza / Campuswire** — Q&A, clarifications ("is the final cumulative?")
- **Echo360** — lecture recordings and transcripts
- **Email** — course updates, deadline changes
- **Calendar, personal notes, trackers**

Tracking deadlines, finding slides, and gathering exam prep is manual. General LLM chat tools (ChatGPT, NotebookLM, etc.) only know what you upload by hand.

## Pitch
**"One login, every class. Your AI study partner that already knows your Canvas, Gradescope, Piazza, lectures and inbox."**

## Goals
- Usable by the *average* UMass student, not just CS majors
- Quick setup for a new student (minutes, not an afternoon)
- Simple login, modern UI, AI tools embedded
- Flexible model choice (Claude, GPT, Gemini, local via Ollama)
- Real productivity benefit day-to-day, not just a chatbot
- Plausibly adoptable by UMass / a university (security + FERPA story)

## Two core design principles
1. **Sync first, agent second.** A sync layer pulls everything into one normalized store (Courses, Assignments/Items, Events, Materials, Announcements, Posts, Recordings). The agent queries *our* database, not live platforms. Faster, cheaper, model-agnostic, demo-reliable. Details: [07](07-sync-and-storage.md).
2. **The dashboard is deterministic; the LLM adds on top.** "What's due this week" is a database query, not an LLM guess. The LLM prioritizes, summarizes, extracts deadlines from syllabi/emails, and helps study. This avoids the worst failure: the AI inventing a deadline.

## Use cases (demo priority order)
1. **Today view / morning brief** — due today, due this week, new announcements, upcoming exams, ranked.
2. **"Prep me for the CS 311 midterm"** — finds exam date + scope (syllabus, announcements, Piazza), gathers relevant slides and lecture recordings, produces a study plan, practice questions and flashcards with slide-level and timestamp citations.
3. **Ask across sources** — "Did the professor say the final is cumulative?" searches Piazza, announcements, email, and lecture transcripts.
4. **Lecture recall (Echo360)** — "What did the professor say about dynamic programming on Tuesday?" → answer with a timestamped link into the recording.
5. **Calendar sync** — deadlines and study blocks via a subscribable `.ics` feed; conflict warnings ("3 things due Thursday, start the lab tonight").
6. **Catch-up mode** — "I was sick last week, what did I miss?"
7. **Stretch** — grade tracking / "what do I need on the final", group-project coordination, notifications, in-Canvas side panel.

## Differentiation (vs. NotebookLM, or Claude/ChatGPT plus connectors)

| | General assistant + connectors | Us |
|---|---|---|
| Coverage | Canvas at best; Gradescope, Piazza, Echo360 have no official connectors and UMass Duo blocks most | Connectors for UMass's actual platforms |
| Course materials | Fetched and read per question, limited by context | Whole semester indexed ahead of time |
| Memory | Stateless: can't notice "midterm moved" or merge duplicates | Versions, merged items, change log |
| Proactive | Waits to be asked | Dashboard, morning brief, change alerts |
| Trust | AI reads deadlines and writes links | Deadlines from queries; links built from synced data and verified ([04](04-citations-and-freshness.md)) |
| Interface | Chat box | Today view, quizzes, flashcards, calendar feed |
| Setup | Configure each connector and token | One guided onboarding |
| Model / cost | Tied to one paid plan | Any model, incl. free/local or university-hosted |

**Positioning:** *"A general assistant can reach your data. We already have it organized, verified, and watching for changes."* Not a competitor: our MCP server (stretch) lets students use their organized data inside Claude or ChatGPT too.

**Honest risk:** big AI companies could build pieces of this. Our edge is depth on student-specific problems and the university deployment story.

## University adoption story
In production this becomes an official **LTI 1.3 app + Canvas developer key** issued by UMass IT, data stays on university infrastructure, and the model can be a campus-hosted open model. This addresses FERPA before judges ask.
