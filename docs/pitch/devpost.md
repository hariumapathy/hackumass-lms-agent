<!-- Submission notes for the team; do not paste this comment into Devpost.
Draft must exist Sat Nov 14 by 23:59 ET; final deadline Sun Nov 15 09:00 ET.
Add Hari Umapathy, Neal Patel and Soumith Madadi as contributors.
Use the public GitHub URL under Try it out. Category: Best UMass Hack.
This copy distinguishes live-verified Canvas/Gradescope from planned integrations.
Credits below list actual reused code; Piazza helpers remain planned, not copied.
-->

# HackUMass LMS Agent

**Tagline:** Your classes, deadlines, and course materials—together in one study companion for UMass students.

**Project link:** https://github.com/hariumapathy/hackumass-lms-agent

## Inspiration

A normal week at UMass can mean checking Canvas for assignments, Gradescope for submissions, lecture slides for explanations, and announcements for the deadline that just changed. The information exists, but students have to assemble it themselves before they can start studying.

We wanted to build a study companion that starts with a student's actual courses. Instead of asking students to upload files or repeatedly explain their semester to a chatbot, it keeps their course information organized and lets them ask useful questions immediately: “What's due this week?” “What should I study for my next exam?” “Where did my professor explain this?”

## What it does

Our app brings course deadlines and materials into a single student dashboard, with an AI study assistant grounded in those materials.

- **See your day at a glance.** Today shows upcoming deadlines, exams, recent announcements, source links, and when information was last updated.
- **Connect real Canvas data.** A guided connection imports the student's courses, assignments, announcements, and supported course files. Background updates and a manual Refresh keep the stored information current.
- **Ask about your own semester.** Google Gemini uses tools over the student's stored course data to answer deadline questions and help with exam preparation.
- **Check the source.** Answers can cite a specific page of a syllabus or lecture file, or a course announcement. Clicking a citation shows the supporting passage and a link back to Canvas.
- **Study actively.** The app supports generating study plans, quizzes, and flashcards grounded in retrieved course materials.

We verified the live Canvas flow with a real student account: eight courses, 125 organized deadlines, and 143 course materials. We also verified real Gemini answers about upcoming work and exam scope, including citations to a syllabus page and an instructor announcement.

Gradescope is also connected through an interactive UMass login. Our live test imported 20 student courses and 238 assignment records, including 186 with due dates. The student completes the normal login and Duo flow; our worker reuses an encrypted saved session for read-only updates. Echo360, Piazza, and the calendar integration remain future work.

## How we built it

We separated collecting information from answering questions. A Python worker imports course information into Supabase. The assistant reads that stored data through student-scoped tools; it does not browse learning platforms or receive their credentials.

The frontend uses Next.js, React, TypeScript, Tailwind CSS, and shadcn/ui components. FastAPI serves the backend. The OpenAI Agents SDK orchestrates tool use with Google Gemini as our default model. Supabase provides Postgres, authentication, file storage, and pgvector support. Procrastinate runs background jobs, and Playwright supports the Gradescope login flow.

Course files are extracted into searchable chunks with page references. The assistant cites chunk IDs, and our code resolves those IDs to stored source links. We reject citations that were not returned by the tools and check quoted passages against the retrieved text. The dashboard's deadlines come directly from database queries, without asking a language model to invent or interpret their dates.

Our local demo runs against Supabase in Docker. It currently uses keyword retrieval with deterministic development embeddings; the embedding-provider interface also supports Gemini. We keep a separate seeded semester as a backup demo.

## Challenges we ran into

**Connecting the whole system mattered more than making each screen look finished.** Our early dashboard still displayed sample data even after a real Canvas import. We traced the flow from the connection screen through the worker and database to the UI, replaced the remaining mock endpoints, and added regression tests for the complete path.

**A working import is not automatically a responsive app.** Large file imports initially delayed the merge that makes deadlines visible. We prioritized that merge ahead of bulk file processing and made open views refresh when background work completes.

**University login is a real constraint.** Gradescope's UMass sign-in requires an interactive browser and Duo. Our approach lets the student complete that login normally and stores the resulting browser session encrypted; it never asks the assistant to handle a password or bypass two-factor authentication.

**Useful AI answers need evidence.** We built source tracking and citation validation into the system so students can inspect what an answer is based on, including the source passage and file page.

## Accomplishments that we're proud of

- Moving beyond a sample-data interface to a verified live Canvas → database → dashboard → Gemini flow.
- Showing a real exam-preparation answer with clickable syllabus and announcement citations.
- Keeping deterministic deadlines separate from AI-generated explanations and study help.
- Building a phone-friendly interface with guided setup and a reliable seeded backup.
- Passing 440 backend tests, 71 frontend tests, and six browser tests, alongside lint, type checks, and a production build. Platform tests use fixtures; automated agent tests do not call real models.

## What we learned

The hardest part of a student AI assistant is not the chat box. It is collecting information reliably, making freshness visible, handling login expiry, keeping each student's data separate, and carrying source evidence all the way to the screen.

We also learned that a trustworthy demo needs clear boundaries. A feature that works with sample data is different from one verified against a student's live account. Writing specs, using fixtures, testing the integration path, and keeping an honest runbook helped us distinguish the two.

## What's next

Our immediate next step is refining the combined Canvas and Gradescope experience, including checking deadline mappings against the source and making current-semester courses easier to find. We also want to finish persistent study-session approvals and personal calendar feeds, strengthen account-switching and data-deletion behavior, and improve semantic retrieval.

Longer term, we want an official UMass LTI integration that reduces setup friction and supports university-approved hosting and model choices. Additional platform support, including lecture recordings and course discussion tools, would extend the same evidence-backed study experience.

## Built with

Python, FastAPI, Google Gemini API, OpenAI Agents SDK, Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Supabase, PostgreSQL, pgvector, Procrastinate, Playwright, PyMuPDF, python-pptx, tiktoken.

## Open-source credits

We built the app and integration pipeline using open-source frameworks and libraries. These include Next.js/create-next-app, React, Tailwind CSS, shadcn/ui and Radix UI, TanStack Query, Supabase tooling, FastAPI, Pydantic, Uvicorn, the OpenAI Agents SDK and OpenAI Python client, Procrastinate, Playwright, httpx, requests, Beautiful Soup, python-dateutil, PyJWT, cryptography, psycopg, RapidFuzz, PyYAML, PyMuPDF, python-pptx, and tiktoken. Tests use pytest, pytest-asyncio, respx, Vitest, Testing Library, MSW, and Playwright.

For Gradescope, we reused MIT-licensed course-list parsing and session-expiry helpers from Yuanpeng Li's gradescope-mcp at commit f8a46c8, with modifications documented in the vendored files, and the MIT-licensed gradescopeapi 1.8.1 student assignment parser. We did not reuse their password-login flows. canvas-mcp was consulted as a reference; no code was copied from it. PyMuPDF is licensed under AGPL-3.0. Detailed notices and licenses are in THIRD_PARTY_NOTICES.md.
