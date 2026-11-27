# S43 — Identical returning sources become available again

**Status:** Implemented on review branch, user-authorized sequential implementation, unmerged. RS03 / narrow P02; follows S42. No public schema/API/SSE/seed changes.

## Spec

Observing a previously removed course link, item source, post or material restores presence even when its content hash is unchanged. Restore an observed source only, for its owner; partial/incomplete listings do not prove an absent source returned. Changed returning course links also become active. Stable repeats retain IDs, hashes, processing state, material version and current chunks; unchanged content is not re-embedded or queued merely because presence returned.

Presence restoration and content changes are separate. Existing sync stats continue to count content classifications (`unchanged` for identical content); no new public counter. Post/material restoration writes one status change `removed`→`active` so Today can say “is back”; genuine body/title changes still get their normal separate change rows. Course links have no student-facing change entity. Item-source restoration does not directly alert: canonical merge restores a removed item when any source returns and emits exactly one canonical status-back event. A source returning while another kept the canonical item alive produces no false “is back” alert. Repeated sync/merge emits no duplicate restoration or fake due/title/body changes.

## Test cases

| ID | Expected behavior |
|---|---|
| S43-T01 | Import→complete removal→identical return restores all source tables and canonical item with stable IDs/hash/version/current chunks; unchanged counts preserved |
| S43-T02 | Removed course whose metadata changes returns active with updated name; changed returning posts/materials restore presence and preserve actual content-change handling |
| S43-T03 | Post/material and canonical item get one back-status event, repeated sync/merge is idempotent, unchanged fields never produce fabricated alerts |
| S43-T04 | Submitted raw state can update during identical-content item restoration; no false overdue state |
| S43-T05 | Unchanged restoration does not enqueue processing; existing saved chunks become eligible again without touching version/processing state |
| S43-T06 | Another user's removed records stay removed; unseen sources under incomplete listing stay removed |
| S43-T07 | Existing sync/merge/retrieval tests and full backend/static checks green; no live LLM/platform calls |

## Design plan

Add a scoped transactional presence-restoration helper called after finding each existing source and before its content branch. Only act when its prior status is removed; guard the update with owner/id/status. For posts/materials, insert a status event only if the update actually transitioned. Item/canonical fields remain owned by merge; add canonical status-back event when reconcile sees removed→live, independent of real field diffs. Reuse existing status enum and change-summary behavior. Do not conflate this with failed-indexing retries or publication generations; recovery for missing/failed chunks is the next separate work.

## Implementation plan

1. Write synthetic DB import/remove/restore and canonical-alert tests, confirm meaningful failures.
2. Restore source presence in all content branches, including changed course link; preserve content counters/processing behavior.
3. Add canonical back alert and verify multi-source/idempotency semantics.
4. Run focused/full/static checks and current-feature review; update spec/findings/progress/handoff, commit/push separately. Main stays unmerged and Gemini unchanged.

## Acceptance / evidence

Initial5 DB regressions failed. Final9 new cases pass, including multi-source/incomplete guards, concurrent duplicate restoration and real canonical field changes.38 focused sync/merge/retrieval checks passed before final4 review/guard additions. Full/static results recorded in devlog. Current-feature review found no blocking defect. Restored sources with pre-existing failed/missing chunks still need the separately planned durable indexing/retry work; do not claim this fix repairs failed processing.
