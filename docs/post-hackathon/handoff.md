# Handoff: post-hackathon planning

Date: **2026-11-23**. Work branch: **`post-hackathon-plan/changes`**, forked from fetched `origin/main` **`be13793`**. Read the [packet index](README.md), [design](design-plan.md) and [implementation sequence](implementation-plan.md). This phase is **planning only**. Do not implement, migrate, deploy, merge or purchase anything until the user reviews the plan. Proposed P packages are not Ready specs.

Planning checkpoint: **`679c1d6`**, pushed. Review: [draft PR #33](https://github.com/hariumapathy/hackumass-lms-agent/pull/33), intentionally unmerged. The follow-up documentation commit records this link; use `git log -2 --oneline` for the final tip.

## What was completed

Three delegated source audits (deployment/auth; connectors/onboarding; RAG/sync), official provider/Google/UMass research, consolidated design, P00–P14 implementation/test plan, model/hosting cost scenarios and review decisions. Cross-review added explicit inline-file security tests and aligned all model comparisons to the same 120-question retrieval corpus. Only Markdown documentation changed. No secrets or real student data were inspected.

Baseline checks: backend offline `uv run pytest -m 'not integration' -q --tb=short` → 419 pass, 1 skip, 96 deselected; frontend Vitest → 92 pass. Ruff lint/format, pyright, ESLint and Next typegen/TypeScript pass. No current DB integration/build/E2E/live/load/provider evaluation was run. Do not promote old hackathon check counts into current launch evidence.

## Exact next steps

1. Review the packet with the user: cohort/budget, minimum hosted LMS set, trusted Google eligibility, private professor scope, calendar directions and ownership for provider/Google review. Record approved decisions; leave unanswered choices labelled proposals.
2. Prepare narrow reviewed specs and contract proposals in implementation-plan order. First address production/isolation/deletion and sync presence/recovery; then embedding/evidence and durable spending gates. New Gmail/calendar grants/preferences/generations require reviewed schema/API proposals; do not edit the old contracts silently.
3. Only after explicit implementation go-ahead, mark each reviewed spec Ready, add numbered failing tests, implement, verify and commit separately. Deploy staging with synthetic users before an invited real cohort. Start Google restricted-scope/assessment and UMass/vendor access discovery early, without assuming approval or bypassing institutional controls.

## Environment and repository cautions

- Node default here is 18; use an installed supported Node version (this audit used `/Users/nealpatel/.nvm/versions/node/v26.12.1/bin`) and `NODE_OPTIONS=--no-experimental-webstorage` for frontend tests. Pinned pnpm is 10.34.9; Python via uv. Keep lockfiles intact.
- No server restart was needed: this phase changes no UI/runtime code. Do not claim the local browser displays newly implemented features. If later code changes are approved, restart the tested stack and verify the served version as the user requested earlier.
- Never run `make demo-db`, `db-reset` or seed/reset against retained real imports/production. Old local servers/credentials can be stale. Do not read or print ignored `.env` files or secrets for planning.
- The production hosted-browser flag currently falls back to local; do not enable it as a supposed deployment fix. Google app identity is independent of LMS, mail and calendar grants.
- `origin/dev/soumith` has non-ancestor `c097617`; application/component-test paths match main. No cherry-pick/merge was performed; inspect remaining historical metadata if branch cleanup is desired.
- Old hackathon progress/spec tables contain stale statements. Use code + newest devlog + this packet. Historical remote branches remain untouched. Update only the appropriate person's progress file.
- Future handoff: commit/push documentation checkpoints early, identify actual feature commits and test results, record any dirty state and precise next failure. Keep unverified features gated. Do not self-merge a review branch merely because an old relay prompt permits it.
