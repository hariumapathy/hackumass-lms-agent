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
1. **Sync first, agent second.** A sync layer pulls everything into one normalized store (Courses, Assignments/Items, Events, Materials, Announcements, Posts, Recordings). The agent queries *our* database, not live platforms. Faster, cheaper, model-agnostic, demo-reliable.
2. **The dashboard is deterministic; the LLM adds on top.** "What's due this week" is a database query, not an LLM guess. The LLM prioritizes, summarizes, extracts deadlines from syllabi/emails, and helps study. This avoids the worst failure: the AI inventing a deadline.

## Use cases (demo priority order)
1. **Today view / morning brief** — due today, due this week, new announcements, upcoming exams, ranked.
2. **"Prep me for the CS 311 midterm"** — finds exam date + scope (syllabus, announcements, Piazza), gathers relevant slides and lecture recordings, produces a study plan, practice questions and flashcards with slide-level and timestamp citations.
3. **Ask across sources** — "Did the professor say the final is cumulative?" searches Piazza, announcements, email, and lecture transcripts.
4. **Lecture recall (Echo360)** — "What did the professor say about dynamic programming on Tuesday?" → answer with a timestamped link into the recording.
5. **Calendar sync** — deadlines and study blocks via a subscribable `.ics` feed; conflict warnings ("3 things due Thursday, start the lab tonight").
6. **Catch-up mode** — "I was sick last week, what did I miss?"
7. **Stretch** — grade tracking / "what do I need on the final", group-project coordination, notifications, in-Canvas side panel.

## Differentiation (answer to "isn't this just NotebookLM + Canvas?")
- **Zero manual upload** — materials arrive automatically.
- **Cross-source deadline merge + dedupe** — one item even if it appears in Canvas, the syllabus, Piazza, and email.
- **Change detection** — "Midterm moved to Thursday" updates the item and flags it.
- **Every claim cites its source** — and links are verified, never generated (see [04](04-citations-and-freshness.md)).

## University adoption story
In production this becomes an official **LTI 1.3 app + Canvas developer key** issued by UMass IT, data stays on university infrastructure, and the model can be a campus-hosted open model. This addresses FERPA before judges ask.
