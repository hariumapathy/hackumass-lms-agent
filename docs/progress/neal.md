# Neal: progress

**Branch:** `post-hackathon-plan/changes` · **Role:** post-hackathon planning/audit coordinator · **Updated:** 2026-11-23

## Done
- Fetched main `be13793`, confirmed clean start and created the user-requested planning branch.
- Coordinated three source audits and cross-reviews; wrote [design, implementation/test plans and cost scenarios](../post-hackathon/README.md).
- Existing baseline: backend offline 419 pass / 1 skip / 96 integration deselected; frontend 92 pass; backend/frontend lint/format/types pass. No application changes or fresh live/DB/load checks.
- Corrected documentation entry points that still claimed no code/Stage 0. Historical hackathon changes remain on main.

## In progress
- Planning packet ready for user/team review. All P00–P14 packages remain Draft, not Ready for implementation.

## Next
1. Review scale/budget, minimum hosted platforms, identity eligibility, professor scope and calendar directions.
2. Assign external Google/UMass/provider approval and billing/support/incident owners.
3. After implementation go-ahead, prepare Ready specs/contracts and start isolation/deletion + sync correctness/recovery, with tests before code and separate feature commits.

## Blocked on / needs from others
- Product/policy choices and approval owners in the [review table](../post-hackathon/README.md#review-decisions).
- Hosted Gradescope/Piazza access is not implemented; Google restricted-scope approval/assessment gates Gmail. No assumed institutional agreement.

## Contract change proposals
- Draft only: preferences/capabilities, provider grants/scopes, per-class cursors/watch leases, processing/index generations, embedding identity, usage ledger and deletion fencing. No contracts changed.

## Notes for other agents
- [Handoff](../post-hackathon/handoff.md) is current. This is a planning-only review branch: no code, deploy, reset, purchase or self-merge.
- Use code/newest devlog; old progress/spec stages are historical. Protect existing local imports and ignored secrets.
- Node default18 cannot build Next16; audit used installed Node26 and `NODE_OPTIONS=--no-experimental-webstorage`; uv for Python.
- No runtime/UI changes, so no server restart this phase. Future approved changes should be served and browser-verified before handoff.
