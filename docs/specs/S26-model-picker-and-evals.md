# S26 — Model picker and model evals

| | |
|---|---|
| **Status** | In progress (Hari): evals done (13/14 on the seed); `models.yaml` picker not built (minimal /models) |
| **Stage** | 3 |
| **Role** | B |
| **Depends on** | S22 |
| **Folders** | `backend/app/agent/models.py`, `backend/app/agent/models.yaml`, `backend/evals/` |

## Purpose
Offer a **curated** list of models that we have actually tested with our tools, build the right SDK model object for each, and provide an eval script that measures whether each model calls the right tools, cites correctly and produces valid study sets. Background: [03](../03-architecture.md#agent-and-tools).

## Inputs
- `models.yaml` (checked in):
```yaml
default: gemini/gemini-default    # placeholder: pick the current Gemini Flash model ID at implementation time
models:
  - id: gemini/gemini-default       # DEFAULT (free tier; MLH Best Use of Gemini API)
    label: "Gemini (recommended)"
    adapter: openai_compat          # native | openai_compat | litellm
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
    tier: recommended
    env: GEMINI_API_KEY
  - id: openai/gpt-default
    label: "GPT"
    adapter: native
    tier: recommended
    env: OPENAI_API_KEY
  - id: anthropic/claude-default
    label: "Claude"
    adapter: litellm
    tier: recommended
    env: ANTHROPIC_API_KEY
  - id: ollama/llama-local
    label: "Local (Ollama)"
    adapter: openai_compat
    base_url: http://localhost:11434/v1
    tier: experimental
```
- `backend/evals/golden.yaml`: golden questions against seed data (S03).

## Outputs
- `GET /models` → `ModelOption[]` with `available` = required env key present (and reachable for Ollama).
- `model_for(id)` → SDK model object (S22).
- `uv run app evals [--models all|id,...]` → table + JSON report in `backend/evals/reports/` (git-ignored).

## Golden question format
```yaml
- id: G01
  question: "What's due this week in CS 311?"
  expect_tools_any: [get_items]
  expect_answer_contains: ["HW5"]
  expect_citations: false
- id: G02
  question: "Does the CS 311 midterm cover graphs?"
  expect_tools_any: [search_materials]
  expect_answer_contains_any: ["not", "doesn't", "no"]
  expect_citations: true
- id: G03
  question: "Make me 5 flashcards on dynamic programming for CS 311"
  expect_tools_all: [search_materials, create_study_set]
  expect_study_set: {type: flashcards, min_items: 5}
```
10–15 questions covering: deadlines, changes ("did anything move?"), cross-source search, lecture recall, study set types, a study-block proposal, an unknown-course question, an injection attempt in a seeded Piazza post (must not follow it).

## Behavior and rules
1. Only models listed in `models.yaml` can be selected (`PATCH /me` validates).
2. `model_for`: `native` → model ID string; `openai_compat` → `OpenAIChatCompletionsModel` with a client using `base_url` + key; `litellm` → `LitellmModel`.
3. Evals run against a fresh seed DB with **real** embeddings and real models; never in CI.
4. Scoring per question: pass/fail on each expectation; report per model: pass rate, avg turns, avg latency, invalid-citation count, study-set validation failures.
5. **Picker rule:** a model is `recommended` only if it passes ≥ 85% of goldens; otherwise move it to `experimental` (edit yaml). Record results in this spec.

## Results (fill in before H24)
| Model | Pass rate | Avg turns | Notes |
|---|---|---|---|
| **gemini-3.5-flash (2026-11-14 20:16 ET, seed DB)** | **13/14 (93%)**, 1 skipped (S25) | 3.3 tool calls | 0 errors, avg 9.2 s (max 18.7 s). Passed injection (G11) and flashcards (G14). G04 answered right but uncited. Cost sample (G01/G05/G14): avg **9.6k input + 620 output tokens per question** (2–3 model calls) |
| gemini-3.5-flash (2026-11-14 19:56 ET, mock semester) | 4/13 ran (31%); **4/4 before the API cut off** | ~2 tool calls | G01–G04 passed (deadlines, changes, cross-source exam coverage), 25–40 s each. G05+ failed with **402 "prepayment credits are depleted"**. Re-run after topping up AI Studio credits. |

**How to run:** `cd backend && uv run app evals [--db] [--user-email demo@example.com] [--only G01,G05] [--model gemini-3.5-flash] [--delay 4]` (`--db` runs on `DATABASE_URL`, e.g. the local seed; for local use also set `EMBEDDINGS_PROVIDER=fake` if the seed used fake embeddings). Goldens: `backend/evals/golden.yaml` (deadlines, today, changes, cross-source exam coverage, lecture recall, syllabus, concept from slides, unknown course, announcements, **prompt injection in a Piazza post**, freshness, late policy, flashcards, study blocks). Reports: `backend/evals/reports/` (git-ignored, JSON + Markdown). Metrics: pass rate, avg/max latency, avg tool calls, failed tool calls, errors, citation coverage, dropped citations. Code: `backend/app/evals/`; tests `tests/runtime/test_s26_evals.py` (T04 scorer, T05 runner with ScriptedModel). Until the S03 seed exists, goldens run on `MockToolData`.

## Acceptance criteria
- [ ] `/models` lists available models with tiers
- [ ] Switching model in settings changes the model used by the next chat
- [ ] Eval report produced for every model in the picker; tiers updated

## Test plan
| ID | Test | Type |
|---|---|---|
| S26-T01 | `models.yaml` loads and validates (unique IDs, known adapters, default exists) | unit |
| S26-T02 | `available=false` when env key missing | unit |
| S26-T03 | `model_for` returns the right object type per adapter | unit |
| S26-T04 | Eval scorer: pass/fail logic for each expectation type | unit |
| S26-T05 | Eval runner works end to end with `ScriptedModel` (no network) | runtime |

## Out of scope
Per-request model overrides from the chat box, cost dashboards, fine-tuning.
