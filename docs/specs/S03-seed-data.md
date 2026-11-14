# S03 — Seed data (contract)

| | |
|---|---|
| **Status** | Draft |
| **Stage** | 0 |
| **Role** | A (writes), used by everyone |
| **Depends on** | S01 |
| **Folders** | `supabase/seed/`, `backend/app/cli.py` |

## Purpose
A realistic fake semester loaded into the DB on day one, so B can build tools and the agent and C can build the UI **before any connector works**. It is also the backup demo account and the dataset for model evals (S26).

## Inputs
- `supabase/seed/*.json` fixture files (hand-written + generated text).
- `EMBEDDINGS_PROVIDER` (`fake` for tests, `gemini` for the demo account).

## Outputs
- `uv run app seed [--user-email demo@example.com] [--reset]`: creates (or reuses) a Supabase auth user and loads all fixtures for that user, including chunks with embeddings.
- `make db-reset` runs migrations then `app seed` for the default dev user.

## Fixture contents (one semester, "Fall 2026")
| Entity | Content |
|---|---|
| Profile | Timezone `America/New_York`, model `openai/<default>` |
| Connections | Canvas `active` (expires in 60 days), Gradescope `active`, Echo360 `needs_reconnect` (to exercise the UI) |
| Courses (4) | `COMPSCI 311` Algorithms, `COMPSCI 320` Software Eng., `MATH 235` Linear Algebra, `STATS 315` Statistics. Each linked on Canvas; 311 and 320 also on Gradescope; 311 on Echo360 |
| Items (~40) | Homeworks, labs, quizzes, projects, **CS 311 Midterm 1** (due Nov 20 19:00 ET), finals. Mix of past, today, this week, later. Some with 2 sources (Canvas + Gradescope) |
| Changes (3) | Midterm 1 moved Nov 18 → Nov 20; HW5 points 50 → 60; one edited announcement |
| Posts (~25) | Canvas announcements per course; a few Piazza-style posts in 311 incl. "Midterm covers through DP, not graphs" |
| Materials (~30) | Lecture slide decks (as extracted text per slide), 1 syllabus per course, 6 Echo360 transcripts for 311 with timestamps |
| Chunks (~400) | Generated from materials/posts by the real chunker (S12), with embeddings |
| Study sets (2) | One quiz, one flashcard set for 311 |
| Conversation (1) | A short past chat with resolved citations |

Content must be **plausible academic text** (write it or generate it once and commit it), never copied from real course materials.

## Behavior and rules
1. Dates are **relative to "now"** at load time (e.g. `due: "+3d 23:59"`), so the seed is always current. The fixture format supports relative offsets; the loader resolves them in the profile's timezone.
2. Loader uses the real repositories and the real chunker (S12) so seed data has the same shape as synced data. Until S12 exists, the loader inserts pre-chunked text from the fixtures.
3. Idempotent: running twice with `--reset` gives the same result; without `--reset` it refuses if data exists.
4. `fake` embeddings: deterministic vectors from a hash of the text (same text → same vector), 1536 dims, normalized.
5. All `source_url`s point to plausible but fake URLs on `example.instructure.com` / `example.gradescope.com`, never real course IDs.

## Errors and edge cases
| Case | Expected behavior |
|---|---|
| `EMBEDDINGS_PROVIDER=gemini` without `GEMINI_API_KEY` | Fail with a clear message before inserting anything |
| Fixture references unknown course | Loader fails listing the bad reference |

## Acceptance criteria
- [ ] `make db-reset` loads everything in under 60 s with fake embeddings
- [ ] Today view (S32) and agent tools (S21) return non-empty, sensible data from seed
- [ ] Seed covers every enum value used by the UI (statuses, item types, post kinds, connection statuses)

## Test plan
| ID | Test | Type |
|---|---|---|
| S03-T01 | Loader creates expected counts per table | integration |
| S03-T02 | Relative dates resolve correctly in the profile timezone (incl. DST boundary) | unit |
| S03-T03 | Fake embeddings are deterministic and normalized | unit |
| S03-T04 | Re-running without `--reset` refuses; with `--reset` produces identical counts | integration |
| S03-T05 | Every chunk has exactly one parent and a valid `source_url` path to resolve | integration |

## Out of scope
Multiple demo users; realistic file binaries in Storage (text-only materials are fine for seed).
