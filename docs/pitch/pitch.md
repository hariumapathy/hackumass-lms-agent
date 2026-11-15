# Pitch kit

Living document: **update it whenever a feature lands or changes** (AGENTS.md rule). At the end this is what we present from. Keep it honest: only claim what the demo actually does; mark planned items as "next".

**Competing in: [HACKUMASS] Best UMass Hack** (+ automatic grand prizes). Frame every part of the story around UMass students, UMass platforms and UMass adoption.

## One-liner
**One login, every class.** An AI study partner that already knows your Canvas, Gradescope and lecture recordings, so you stop hunting across five sites.

## 30-second version
UMass students juggle Canvas, Gradescope, Piazza, Echo360 and email every week. Deadlines move, slides are scattered, and ChatGPT knows none of it unless you upload everything by hand. We built an agent that **syncs your courses automatically**, shows **one Today view** of what's due and what changed, and helps you **study with answers that cite the exact slide or lecture timestamp**, and those links are verified so the AI can't make them up.

## 3-minute demo script (live)
| Time | Show | Say |
|---|---|---|
| 0:00 | Title slide | The problem **every UMass student knows**: Canvas, Gradescope, Piazza, Echo360, UMass email; scattered deadlines, manual studying |
| 0:20 | Onboarding: guided "Link your Canvas" (1 minute) → "4 classes found" | Built for any student, not just CS majors: no installs, plain language; we never store passwords |
| 0:45 | **Today view**: due today/this week, a **"CHANGED: Midterm moved"** badge, source chips | Deterministic, from synced data; changes detected automatically |
| 1:20 | Chat: **"Prep me for my CS 311 midterm"** → status steps stream → study plan + quiz + flashcards | Agent uses tools over our synced database |
| 2:00 | Click a **citation chip** → opens the exact slide / lecture moment | Links come from synced data and are validated; the AI never writes URLs |
| 2:20 | "Add these study sessions?" → **Add** → calendar feed | Writes need the student's click |
| 2:40 | Architecture slide | Sync worker → Supabase → agent (any model) → Next.js. **UMass adoption path:** an official LTI 1.3 app with a UMass IT Canvas key, data on UMass infrastructure, a campus-hosted model |
| 2:55 | Close | "One login, every class." |

**Backup:** if live sync or wifi fails, switch to the **seeded demo account** (S03). Rehearse both paths.

## Architecture (for the slide)
See the diagram in [03-architecture.md](../03-architecture.md#system-diagram). Talking points:
- **Sync first, agent second:** a worker copies course data into one database; the AI only reads that database.
- **No passwords:** Canvas token; Gradescope/Echo360 via a one-time browser login with Duo.
- **Verified citations:** the model cites chunk IDs; our code resolves them to real links.
- **Any model:** Google Gemini by default (free tier), OpenAI/Claude optional, all tested with a golden-question script.

## Judging criteria mapping
See [hackathon.md → Judging criteria](../hackathon.md#judging-criteria--how-we-score).

## Likely judge questions
| Question | Answer |
|---|---|
| Isn't this NotebookLM / ChatGPT with connectors? | They don't sync Gradescope/Echo360, don't remember changes, don't merge duplicates, don't verify links. See [01-vision](../01-vision.md#differentiation-vs-notebooklm-or-claudechatgpt-plus-connectors) |
| Do you store my password? | No. Canvas uses a revocable token; other sites use a one-time browser login with Duo; sessions are encrypted |
| What if the AI hallucinates? | Deadlines come from database queries, not the model; citations are validated against what tools returned |
| Could UMass adopt it? | Yes: an LTI 1.3 app + Canvas developer key, data on university infrastructure, campus-hosted model |
| What did you build vs. reuse? | See [devpost.md → Credits](devpost.md#credits-external-code) |

## What actually works (update as features land)
| Feature | Status |
|---|---|
| Repo, scaffolding, CI (S00) | ✅ |
| API + streaming contract with mock data (S02) | ✅ |
| Real sign-in checks on every API call: Supabase tokens, chat rate limit, private logs (S20) | ✅ (profile storage waits for the DB schema) |
| AI agent on Gemini: answers deadline + material questions with tools, streams progress (S21, S22) | ✅ on the mock semester (real data after S01/S03) |
| Verified citations: made-up or unreturned sources are dropped, quotes checked (S23) | ✅ |
| Flashcards / quizzes / study plans where every item cites a real source (S24) | ✅ backend (UI cards: S33) |
| Agent evals: 15 golden student questions incl. a prompt-injection test (S26) | ✅ runner; first run 4/4 before credits ran out |
| _everything else_ | ⬜ in progress, see [specs](../specs/README.md) |
