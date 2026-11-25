# S44 — Committed course content keeps durable indexing work

**Status:** Implemented on review branch, user-authorized sequential implementation, unmerged. RS04 / narrow P03. Internal additive schema proposal only; public API/SSE/seed unchanged. Gemini retained. User now permits discretionary merges; keep related foundations under review until integrated gates pass. Stop before model-cost/provider work.

## Spec

Every committed new/changed material or post has a processing intent committed in the **same record transaction**. A later connector failure, unavailable queue or crash before enqueue cannot lose that work. Existing source/chunks remain if intent persistence fails; abort the run's removal inference rather than treating the observed record as absent. Identical source observations preserve matching intent revision; previously stranded legacy pending materials or posts lacking current chunks gain an intent when next observed with usable source data.

Material download/text/transcript payloads are encrypted with the worker's Fernet key. Queue args contain only owner/intent/revision IDs. Posts use their owner-scoped stored body. Internal rows have RLS/no client grants and are purged with saved-data deletion. A changed source replaces the intent revision and resets dispatch/completion markers. Superseded, foreign, missing and removed-parent jobs cannot start processing current content. Marker updates always compare owner+revision; completed matching intents do not execute twice and clear encrypted source payloads.

After a successful import, existing callbacks dispatch promptly; periodic worker recovery also dispatches durable pending intents from interrupted/failed imports. Use a short persisted dispatch lease: crash before defer is recoverable after lease expiry, crash after defer before acknowledgment can replay safely, and a fast worker completion/reset cannot be overwritten by late enqueue acknowledgment. Delivery is **at least once**: replay may create duplicate queue rows. Queueing locks are deliberately omitted for the new task because a running job's framework retry can collide with a replayed queued row. Stable task execution locks plus the worker advisory lock and revision/completion guards make duplicate delivery safe; this is not exactly-once provider I/O.

## Test cases

| ID | Expected behavior |
|---|---|
| S44-T01 | Later fetch fails after material/post commits: intents and encrypted material source survive; fresh recovery dispatches them without waiting for another successful import |
| S44-T02 | Queue failure or crash before enqueue/after enqueue-before-marker leaves recoverable work; expired lease can be reclaimed; duplicate delivery preserves revision IDs and a running job can retry while a replay is queued |
| S44-T03 | Source/intent rollback together on intent persistence failure; old source/chunks are retained and no false removal occurs |
| S44-T04 | Changed source rotates revision; stale job/ACK/reset/completion cannot alter new intent; a newer queued revision is never suppressed by old queued work |
| S44-T05 | Worker uses decrypted owned source with fake processing, completes once, clears ciphertext; duplicate/current/removed/foreign IDs behave safely |
| S44-T06 | Authenticated/anon cannot read/write internal intents; saved-data clear removes intents and owner job args contain no source text/URLs |
| S44-T07 | Legacy pending material/unchunked post gains missing intent on next observation; completed healthy unchanged sources are not needlessly queued |
| S44-T08 | Existing sync/processing/deletion/schema tests and full backend/static checks remain green; no live platforms/models in tests |

## Design plan

Add internal `processing_intents`: owner, XOR material/post foreign keys with cascade, unique parent IDs, source hash, revision UUID, encrypted nullable material payload, dispatch lease token/time, dispatched/completed timestamps and creation/update timestamps. No client policies/grants. Integrate capture inside `run_sync`'s per-record transaction. Wrap capture errors as a content-free platform failure so existing transaction rollback/retry/no-removal behavior applies. Keep application-facing USER_TABLES separate from internal deletion tables.

Dispatch reserves an owner/revision/token lease before external queue enqueue, marks dispatched only after acknowledgment with that exact lease, and releases the same lease on failure. Periodic recovery reclaims expired leases and checks owned live parent/hash. `process_intent` uses the existing user deletion barrier and a per-intent advisory session lock; validates revision/parent before decrypting, calls existing worker functions, then CAS-completes only terminal successful/skip outcomes. Clear/reset markers on removed parents, allowing later restoration to redispatch. Existing legacy process task names remain for queued-job compatibility.

## Implementation plan

1. Write failing local-DB partial-commit, encryption/lease/race/rollback/deletion/legacy-capture tests with fake processors/defer callbacks and a fixed test-only encryption key.
2. Add/apply only migration0004 on retained local data; capture intents atomically and fail safely on persistence errors.
3. Implement revision/token dispatch and worker execution, ID-only job args, successful-import callbacks plus periodic reconciliation; preserve legacy task compatibility.
4. Verify all crash windows and status boundaries; current-feature review, full/static checks, exact docs/checkpoint, separate commit/push. Restart worker only after migration/code checks; pause it during DB fixtures.

## Limits / acceptance

Initial6 regressions failed. Additional notification and real Procrastinate retry/replay collision cases failed before corrections. Final16 new tests and full backend644 pass/1 optional local Storage skip; Ruff/format/pyright green. Independent current-feature review found no further major defect after queueing-lock removal. See [operator recovery guide](../deployment/processing-recovery.md). This fixes committed-source→queue durability, not all processing retry classification (RS05 next), source-vs-index publication races (RS06), embedding generation (RS07), canonical merge recovery or full readiness semantics. Failed processors remain incomplete until the next retry feature; do not mark them completed or claim fully searchable imports. Pre-S44 files require another source observation if their download/text payload was never stored; already failed/processing legacy materials and expired external download links need the separate recovery/refresh policy. An external Storage upload is not transactional with Postgres; orphan reconciliation remains a launch gate.
