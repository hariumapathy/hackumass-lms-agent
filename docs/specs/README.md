# Feature specs

> **Post-hackathon planning (2026-11-23):** proposed deployment/auth, onboarding, Google integrations and RAG/sync hardening work is indexed in [the new implementation plan](../post-hackathon/implementation-plan.md). It includes the [General/course/project chat and student UX amendment](../post-hackathon/course-chats-and-ux.md) (P15/P16). It is Draft, not Ready. The original stage tables below are historical and not a launch-readiness certification.

Every feature is specified here **before** it is built. Workflow: [08-development-workflow.md](../08-development-workflow.md). New spec: copy [_TEMPLATE.md](_TEMPLATE.md).

**Status:** `Draft` (being written) → `Ready` (reviewed by a teammate; agents may implement) → `In progress` → `Done` (merged to `main`).
All specs below start as `Draft`. Review and mark `Ready` during hours 0–2 (Stage 0) or before their stage begins.

## Stage 0: Foundations (hours 0–2, whole team)
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S00 | [Repo scaffolding and tooling](S00-repo-scaffolding.md) | All | — | In progress (Hari) |
| S01 | [Database schema](S01-database-schema.md) **(contract)** | A | S00 | In progress (Neal): built + tested; awaiting B/C review |
| S02 | [API and streaming contract](S02-api-contract.md) **(contract)** | B | S00, S01 | In progress (Hari): on `dev/hari`, awaiting C review |
| S03 | [Seed data](S03-seed-data.md) **(contract)** | A | S01 | In progress (Neal): built + tested; awaiting review |

## Stage 1: Vertical slice (hours 2–10) → checkpoint H10
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S10 | [Sync framework](S10-sync-framework.md) | A | S01 | Done (Neal) |
| S11 | [Canvas connector](S11-canvas-connector.md) | A | S10 | Done (Neal); live token → DB → dashboard verified |
| S12 | [File processing and embeddings](S12-file-processing.md) | A | S10 | Done (Neal); real-course file check pending |
| S20 | [Backend API skeleton and auth](S20-api-skeleton-and-auth.md) | B | S01, S02 | In progress (Hari): done except Storage/job cleanup in DELETE /me/data |
| S21 | [Agent tools](S21-agent-tools.md) | B | S01, S03, S20 | In progress (Hari): mock + DB tools done |
| S22 | [Agent runtime and chat streaming](S22-agent-runtime-and-chat.md) | B | S02, S21 | In progress (Hari): mock + DB done; live eval 13/14 |
| S23 | [Citations](S23-citations.md) | B | S21, S22 | In progress: DB citation endpoint wired and live card verified (Neal) |
| S30 | [Frontend shell and auth](S30-frontend-shell-and-auth.md) | C | S00, S02 | In progress (Soumith): mock mode, T01–T09 green |
| S32 | [Today view and course pages](S32-today-view.md) | C (UI) + B (endpoints) | S30 | In progress: UI + DB endpoints integrated; live Canvas verified; T01–T11 green (Neal/Soumith) |
| S33 | [Chat and study UI](S33-chat-and-study-ui.md) (chat part) | C | S30 | In progress (Soumith): mock mode, green |

## Stage 2: Depth (hours 10–18) → checkpoint H18
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S13 | [Browser sessions and live login](S13-browser-sessions.md) | A | S10 | Done (Neal): local headed login; live NetID check + disconnect (T06, B) pending |
| S14 | [Gradescope connector](S14-gradescope-connector.md) | A | S13 | In progress (Neal): live login/import verified; five source-page date checks pending |
| S15 | [Echo360 connector](S15-echo360-connector.md) | A | S11, S13 | **Stretch** (moved out of MVP 2026-11-14) |
| S24 | [Study sets](S24-study-sets.md) | B | S22, S23 | In progress (Hari): mock + DB done |
| S25 | [Study blocks, approvals and calendar feed](S25-approvals-and-calendar.md) | B | S22 | Done (live-verified 2026-11-14); manual Google/Apple import pending |
| S31 | [Onboarding and connect flow](S31-onboarding-and-connect.md) | C | S30, S13 | In progress (Soumith): mock mode, e2e green; 2026-11-14: Echo360 hidden, Piazza login step added |
| S33 | [Chat and study UI](S33-chat-and-study-ui.md) (study cards, approvals) | C | S24, S25 | In progress (Soumith): mock mode, T07–T13 green |

## Stage 3: Completeness (hours 18–24) → checkpoint H24 (feature freeze)
| ID | Spec | Role | Depends on | Status |
|---|---|---|---|---|
| S16 | [Merge and change detection](S16-merge-and-changes.md) | A | S11, S14 | Done (Neal); Echo360 rule 2 waits for S15 |
| S26 | [Model picker and model evals](S26-model-picker-and-evals.md) | B | S22 | In progress (Hari): evals done; picker minimal |
| S34 | [Settings](S34-settings.md) | C | S30, S26 | In progress (Soumith): mock mode, T01–T06 green; accounts list = Canvas, Gradescope, Piazza |

| S35 | [UMass-inspired UI](S35-umass-ui.md) | C | S30–S34 | Done (Hari, 2026-11-15) |
| S36 | [Sessions + chat rename/delete](S36-sessions.md) | B+C | S22, S24, S33 | Done (Hari, 2026-11-15) |

## Stage 4: Stretch (only after H24, in order)
[S17 Piazza connector](S17-piazza-connector.md) (A, built: fixture + DB tests green, Connect Piazza in the UI; **live login check pending**) · MCP server (B) · in-Canvas side panel / extension (C) · Campuswire · email · grades. Write a spec before starting any of them.

## Post-hackathon implementation (2026-11-24)

| ID | Feature | Status |
|---|---|---|
| S37 | [Production startup guards](S37-production-startup-guards.md) | Implemented on review branch; unmerged |
| S38 | [JWT issuer binding](S38-jwt-issuer-binding.md) | Implemented on review branch; unmerged |
| S39 | [Browser account isolation](S39-browser-account-isolation.md) | Implemented on review branch; unmerged |
| S40 | [Complete data deletion](S40-complete-data-deletion.md) | Implemented on review branch; unmerged; Storage fault reconciliation remains a launch gate |
| S41 | [Current retrieval eligibility](S41-current-retrieval-eligibility.md) | Implemented on review branch; unmerged |
| S42 | [Canvas listing completeness](S42-canvas-listing-completeness.md) | Implemented on review branch; unmerged |
| S43 | [Source presence restoration](S43-source-presence-restoration.md) | Implemented on review branch; unmerged |
| S44 | [Durable processing intents](S44-durable-processing-intents.md) | Implemented on review branch; unmerged; failed-processor retry is next |

## Cross-cutting rules (apply to every spec)
- [AGENTS.md non-negotiable rules](../../AGENTS.md#non-negotiable-rules)
- Every table has `user_id` + Row Level Security; every query and tool is scoped to the authenticated user.
- All times stored as UTC `timestamptz`; converted to the student's timezone (`profiles.timezone`) only for display and in the agent's context block.
- IDs: `uuid` everywhere except `chunks.id` (`bigint`, short so the LLM can cite `[cite:chunk_123]` reliably).
