# Post-hackathon planning packet

**2026-11-23 · Draft for review · Branch `post-hackathon-plan/changes` · Baseline `be13793`**

The hackathon is over; the user reports the team presented to judges, received encouraging feedback and wants a deployable student/professor product. This packet records a fresh code audit, current primary-source research, a proposed design and a sequenced implementation plan. **No application/configuration/test code was changed, no deployment was made and no provider was purchased.** All proposed work is Draft until reviewed.

## Read in this order

| Document | Purpose |
|---|---|
| [Design plan](design-plan.md) | Product boundaries, Google identity, source/class selection, architecture, privacy and calendar/mail directions |
| [Implementation plan](implementation-plan.md) | P00–P16 packages, dependencies, tests before code, pilot gates and rollback |
| [Course chats and student UX](course-chats-and-ux.md) | General/course/project chat, controlled memory, modern maroon UI, design skill candidates and usability gates |
| [Models and costs](models-and-costs.md) | One provider versus OpenRouter, current cheap-model candidates, 25/100/1,000-user scenarios and budget controls |
| [Deployment/auth audit](audit-deployment-auth.md) | Source evidence, hosted-login/security/operations gaps and official identity references |
| [Connector/onboarding audit](audit-connectors-onboarding.md) | Current LMS flow, Google consent requirements, Gmail and Calendar design/tests |
| [RAG/sync audit](audit-rag-sync.md) | Fourteen prioritized findings, measured-versus-hypothetical distinction and shared benchmark |
| [Handoff](handoff.md) | Branch state, validation, next-agent instructions and unresolved decisions |

## Recommended direction

Keep the working stack. Correct data isolation/deletion, import recovery/removal and retrieval-generation issues before accepting new students. Configure Google identity separately from optional data permissions. Offer a source checkbox flow, discover courses before importing their content, and allow later additions in Settings. Start with a small invited Canvas/private-calendar pilot if the team accepts staged connector availability. Hosted Gradescope/Piazza need a separate real login architecture; Gmail requires external approval gates. Professors initially have private workspaces, not access to students' private data. General Chat and course workspaces (with optional coursework projects) keep history, retrieval and tools aligned; student-approved memory is inspectable and removable. Student-first responsive maroon UX and novice task success are proposed pilot gates, extending the existing UI.

Choose the cheapest model that passes a controlled course-evidence/tool/streaming evaluation. Prefer one provider initially; consider OpenRouter when one chat invoice plus several approved models is worth its routing/privacy complexity. Do not choose purely by nationality, advertised rate limit or per-token price. No provider has passed the proposed new benchmark yet.

## Highest-priority findings

- Hosted browser login is unimplemented and falls back to opening a browser on the server machine.
- Workspace deletion leaves Storage/jobs; account switching has an unproven cache-disclosure risk needing a two-user regression.
- Production can silently use demo/scripted/fake defaults without stronger startup validation.
- Capped Canvas file listings can mark existing materials removed; identical reappearing records may remain removed.
- Partially committed imports and failed indexing can leave content unsearchable without durable reconciliation.
- Current retrieval can include removed source content, and embedding model identity is not enforced in stored vectors.
- Usage is counted in memory but not persisted for dependable per-student cost caps.

These are source-level findings, not claims that a hosted exploit was reproduced. Evidence and required tests are in the three audits.

## Review decisions

| Decision | Working recommendation | Status |
|---|---|---|
| First cohort and cap | 25 invited students; cost scenarios rather than a committed bill | Await team/user budget decision |
| Hosted platform minimum | Canvas + outbound calendar first, hosted GS/Piazza gated | Await product decision |
| Identity eligibility | Trusted invited subjects; define personal/UMass account policy | Await policy + staging UMass check |
| Professor scope | Same private workspace; institution roles later | Await scope approval |
| Calendar direction | Preserve outbound feed; add Google/inbound features separately | Await desired capability choices |
| Model/data terms | Paid approved service, no silent provider fallback | Await benchmark + vendor review |
| External ownership | Domain/Cloud/Supabase/billing/support/incident and Google review owners | Must be assigned |

## Validation and limits

Existing baseline rerun: **419 backend tests passed, 1 skipped, 96 integration tests deselected; 92 frontend tests passed; backend/frontend lint, formatting and type checks passed.** No new tests were written because this phase forbids application work. No fresh database-integration, production build, browser E2E, live account, load, penetration or model-quality test was performed. Historical demo checks are labelled as historical, not current production evidence.

The repository was clean at start and main matched fetched `origin/main`. `origin/dev/soumith` retains one non-ancestor patch (`c097617`), but its application/component-test paths have no net diff against main; remaining differences are historical launch/docs metadata. It was inspected, not merged. Current main already contains Calendar, Piazza, UMass UI and Sessions. Old README/progress statements saying there was no code or Stage 0 was active were stale; entry-point documentation now points here.
