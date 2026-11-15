# Feature specs

Every feature is specified here **before** it is built. Workflow: [08-development-workflow.md](../08-development-workflow.md). New spec: copy [_TEMPLATE.md](_TEMPLATE.md).

**Status:** `Draft` (being written) → `Ready` (reviewed by a teammate; agents may implement) → `In progress` → `Done` (merged to `main`).
All specs below start as `Draft`. Review and mark `Ready` during hours 0–2 (Stage 0) or before their stage begins.

## Stage 0: Foundations (hours 0–2, whole team)
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S00 | [Repo scaffolding and tooling](S00-repo-scaffolding.md) | All | — | In progress (Hari) |
| S01 | [Database schema](S01-database-schema.md) **(contract)** | A | S00 | Draft |
| S02 | [API and streaming contract](S02-api-contract.md) **(contract)** | B | S00, S01 | In progress (Hari): on `dev/hari`, awaiting C review |
| S03 | [Seed data](S03-seed-data.md) **(contract)** | A | S01 | Draft |

## Stage 1: Vertical slice (hours 2–10) → checkpoint H10
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S10 | [Sync framework](S10-sync-framework.md) | A | S01 | Draft |
| S11 | [Canvas connector](S11-canvas-connector.md) | A | S10 | Draft |
| S12 | [File processing and embeddings](S12-file-processing.md) | A | S10 | Draft |
| S20 | [Backend API skeleton and auth](S20-api-skeleton-and-auth.md) | B | S01, S02 | In progress (Hari): auth done; DB parts wait for S01 |
| S21 | [Agent tools](S21-agent-tools.md) | B | S01, S03, S20 | Draft |
| S22 | [Agent runtime and chat streaming](S22-agent-runtime-and-chat.md) | B | S02, S21 | Draft |
| S23 | [Citations](S23-citations.md) | B | S21, S22 | Draft |
| S30 | [Frontend shell and auth](S30-frontend-shell-and-auth.md) | C | S00, S02 | Draft |
| S32 | [Today view and course pages](S32-today-view.md) | C (UI) + B (endpoints) | S30 | Draft |
| S33 | [Chat and study UI](S33-chat-and-study-ui.md) (chat part) | C | S30 | Draft |

## Stage 2: Depth (hours 10–18) → checkpoint H18
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S13 | [Browser sessions and live login](S13-browser-sessions.md) | A | S10 | Draft |
| S14 | [Gradescope connector](S14-gradescope-connector.md) | A | S13 | Draft |
| S15 | [Echo360 connector](S15-echo360-connector.md) | A | S11, S13 | **Stretch** (moved out of MVP 2026-11-14) |
| S24 | [Study sets](S24-study-sets.md) | B | S22, S23 | Draft |
| S25 | [Study blocks, approvals and calendar feed](S25-approvals-and-calendar.md) | B | S22 | Draft |
| S31 | [Onboarding and connect flow](S31-onboarding-and-connect.md) | C | S30, S13 | Draft |
| S33 | [Chat and study UI](S33-chat-and-study-ui.md) (study cards, approvals) | C | S24, S25 | Draft |

## Stage 3: Completeness (hours 18–24) → checkpoint H24 (feature freeze)
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S16 | [Merge and change detection](S16-merge-and-changes.md) | A | S11, S14 | Draft |
| S26 | [Model picker and model evals](S26-model-picker-and-evals.md) | B | S22 | Draft |
| S34 | [Settings](S34-settings.md) | C | S30, S26 | Draft |

## Stage 4: Stretch (only after H24, in order)
[S17 Piazza connector](S17-piazza-connector.md) (A, Draft) · MCP server (B) · in-Canvas side panel / extension (C) · Campuswire · email · grades. Write a spec before starting any of them.

## Cross-cutting rules (apply to every spec)
- [AGENTS.md non-negotiable rules](../../AGENTS.md#non-negotiable-rules)
- Every table has `user_id` + Row Level Security; every query and tool is scoped to the authenticated user.
- All times stored as UTC `timestamptz`; converted to the student's timezone (`profiles.timezone`) only for display and in the agent's context block.
- IDs: `uuid` everywhere except `chunks.id` (`bigint`, short so the LLM can cite `[cite:chunk_123]` reliably).
