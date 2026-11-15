# Devpost submission draft

Copy-paste into https://hackumass-xiv.devpost.com (My projects → Create project). **A draft must exist by Sat 11:59 PM**; final edits until **Sun 9:00 AM**. Update the "What it does" and "Built with" sections to match what actually works before the final deadline.

**Project name:** HackUMass LMS Agent _(placeholder name)_
**Tagline:** One login, every class: an AI study partner that already knows your Canvas, Gradescope and lectures.
**Try it out:** https://github.com/hariumapathy/hackumass-lms-agent
**Team (all must have Devpost accounts and be added):** Hari Umapathy, Neal Patel, Soumith Madadi

## Inspiration
Every week UMass students check Canvas, Gradescope, Piazza, Echo360 and email to figure out what's due and what changed. Studying means hunting for the right slides and lecture moments, and general AI chatbots know none of it unless you upload everything by hand.

## What it does
- Syncs your courses automatically (Canvas via a personal token; Gradescope/Echo360 via a one-time login with Duo; no stored passwords).
- **Today view:** everything due, merged across platforms, with "changed" alerts (e.g. a moved midterm).
- **Study mode:** ask "prep me for my midterm" and get a study plan, quiz and flashcards, each citing the exact slide or lecture timestamp.
- **Verified citations:** the AI cites passages by ID and our code turns them into real links, so it can't invent sources.
- **Calendar feed** and study sessions you approve with one click. **Powered by Google Gemini** by default, with other models optional.

## How we built it
Next.js (TypeScript) frontend; Python FastAPI backend with the OpenAI Agents SDK; Supabase (Postgres + pgvector + Storage); a Python sync worker (Procrastinate job queue, Playwright for login-only sites). We worked spec-first and test-first: every feature has a written spec and numbered tests written before the code.

## Challenges we ran into
_(fill in honestly before the final deadline: e.g. UMass SSO + Duo, unofficial platform pages, Node/test tooling versions)_

## Accomplishments that we're proud of
_(fill in)_

## What we learned
_(fill in)_

## What's next
Official UMass LTI 1.3 app with a Canvas developer key, campus-hosted model, Piazza and email, grade tracking.

## Built with
python, fastapi, google-gemini-api, openai-agents-sdk, next.js, react, typescript, tailwind, supabase, postgresql, pgvector, playwright, procrastinate

## Credits (external code)
Required by the rules: list everything we didn't write, and mention it during judging.
| What | Used for | License |
|---|---|---|
| Next.js `create-next-app` template | Frontend scaffold | MIT |
| FastAPI, Pydantic, OpenAI Agents SDK, Procrastinate, Playwright, httpx | Backend frameworks/libraries | MIT/Apache-2.0 |
| PyJWT + cryptography, psycopg 3 | Sign-in token checks, database access | MIT, Apache-2.0/BSD, LGPL-3.0 |
| Supabase CLI | Local database | MIT |
| Google Gemini API (chat + embeddings) | Default AI model | Google API terms |
| Code from [gradescope-mcp](https://github.com/Yuanpeng-Li/gradescope-mcp), [`gradescopeapi`](https://pypi.org/project/gradescopeapi/), [piazza-mcp](https://github.com/profess/piazza-mcp); reference: [canvas-mcp](https://github.com/vishalsachdev/canvas-mcp) | Connector parsing helpers (vendored, see THIRD_PARTY_NOTICES.md) | MIT |

Every external library added later must be added here in the same PR.
