# Neal: progress

**Branch:** `codex/post-hackathon-implementation` · **Role:** post-hackathon planning/audit coordinator · **Updated:** 2026-11-24

## Done
- Fetched main `be13793`, confirmed clean start and created the user-requested planning branch.
- Coordinated three source audits and cross-reviews; wrote [design, implementation/test plans and cost scenarios](../post-hackathon/README.md).
- Existing baseline: backend offline 419 pass / 1 skip / 96 integration deselected; frontend 92 pass; backend/frontend lint/format/types pass. No application changes or fresh live/DB/load checks.
- Added user-requested General/course/project chat, server-enforced context, controlled memory and student-first maroon responsive UX plans (P15/P16); researched UI skills, none installed.
- Corrected documentation entry points that still claimed no code/Stage 0. Historical hackathon changes remain on main.

## In progress
- S37 production startup guards verified; finishing security review/commit before next fix. User now authorizes sequential implementation; Gemini only for now; checkpoint before 07:00 ET.

## Next
1. Commit/push S37, then next individual JWT issuer fix through spec/test/design/implementation/checks.
2. Continue account-isolation/deletion then sync correctness in plan order, one fix at a time.
3. Preserve exact handoff/results and leave all changes unmerged until user says done.

## Blocked on / needs from others
- No blocker for current startup fix. Docker initially unavailable; started through Docker Desktop CLI and local integration tests now pass. Credential/provider-dependent setup remains a later gate; don't interrupt independent work.

## Contract change proposals
- No S37 DB/API/SSE/seed changes. Later contract changes remain separate reviewable proposals.

## Notes for other agents
- [Handoff](../post-hackathon/handoff.md) is current. User authorized implementation, setup and reviewed tooling; NEVER merge main until explicitly told done. No destructive resets or paid provider changes.
- Use code/newest devlog; old progress/spec stages are historical. Protect existing local imports and ignored secrets.
- Node default18 cannot build Next16; audit used installed Node26 and `NODE_OPTIONS=--no-experimental-webstorage`; uv for Python.
- No runtime/UI changes, so no server restart this phase. Future approved changes should be served and browser-verified before handoff.
