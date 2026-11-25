# S46 — Serialize imports and fence replaced/disconnected connections

**Status:** In progress, WIP checkpoint pushed at user request for immediate review. Spec and failing integration regressions exist; connector checkpoints are partial and depend on the not-yet-added shared callback interface. Not a green/run-ready feature. First narrow RS06 feature; successful index publication is the next separate feature. Private credential revision/schema + internal job args only; public API/SSE/seed shapes unchanged.

## Spec

Source imports for the same user/platform execute serially across full/course/item/material scopes; other users/platforms remain independent. Execution deduplication cannot rely on exact-scope enqueue locks. Every production queued job binds the connection/credential revision it was created for. Credential replacement invalidates older open source runs/queued work and permits a fresh connect import. An old queued/running job cannot use a replacement credential, resurrect canceled run state or change a newly connected account's status.

Disconnect/replacement wins over old source publication. Each source record and full-scope removal phase checks the current owner/connection/revision under row locks in its own transaction. Disconnect can wait for the current short DB transaction, never an entire network fetch; once it returns, an old connector cannot commit another source record. Requests already in flight may finish; connector boundaries check current access before starting the next operation. Apply these checkpoints to Canvas pagination, Gradescope page calls and Piazza read RPCs. No passwords or platform writes.

Keep already imported data on disconnect; organizing existing cached data is distinct from fetching new platform data. Clear-saved-data still uses S40's stronger user barrier. Pipeline errors/finalization from superseded work cannot mark the replacement account expired/error/fresh. Terminal source runs are not restarted by duplicate deliveries. Logs/errors must not include credentials or source response bodies.

## Test cases

| ID | Expected behavior |
|---|---|
| S46-T01 | Overlapping full/course imports for one user/platform serialize; later import wins without phantom removal |
| S46-T02 | Another platform/user proceeds while the first source is busy |
| S46-T03 | Disconnect during fetch prevents later source commits/removals/freshness updates; already committed rows retained |
| S46-T04 | Disconnect waits only for an entered record transaction; no source write can commit after disconnect returns |
| S46-T05 | Credential rotation/ABA fences old jobs and old AuthExpired/transient failures; replacement connection remains healthy |
| S46-T06 | Queued job binds epoch; rotation invalidates old open run and same-scope connect queues fresh work; duplicate terminal delivery does not restart |
| S46-T07 | Canvas/Gradescope/Piazza checkpoint before each public connector read operation, including Canvas next page; no next request after guard rejection |
| S46-T08 | Direct/legacy secret updates rotate private revision; owner isolation, schema/model parity, cancellation lock cleanup and existing suites remain green |

## Design plan

Add private `connection_secrets.revision` with a DB rotation/invalidation trigger so legacy writers cannot change ciphertext without changing epoch. Update its private Pydantic row model. Internal SyncJob adds optional connection/revision IDs for legacy compatibility. Enqueue reads/locks the current grant within the existing scope-dedup transaction. Credential replacement cancels old source runs/queued jobs; disconnect locks connection first to match pipeline row-lock order.

A source access helper snapshots the grant, serializes execution with a per-user/platform session lock, and revalidates grant ownership/epoch before network operations and source commits. The public pipeline wrapper owns the execution/user barriers; transactional checks lock connection then secret, matching credential mutation order. Status mutation uses the same grant guard. Superseded work finishes its own run safely without touching replacement connection state.

ConnectorContext gains an excluded internal async callback plus `checkpoint()`; optional/default no-op for stand-alone connector fixture/credential-validation contexts. Canvas client checks before each GET; Gradescope checks before thread-backed page reads; Piazza checks before constructing/awaiting each read operation. Only the worker supplies DB grant validation; the model never sees this callback or secret.

## Implementation plan

1. Write failing two-connection concurrency/disconnect/rotation/epoch tests and connector operation-boundary tests.
2. Apply additive0006 only, add grant helper/private epoch model and queue binding/invalidation.
3. Integrate pipeline execution/record/finalization guards and connector checkpoints; preserve legacy task compatibility and safe row-lock order.
4. Run focused/full/static checks and current-feature security/RAG review; document snapshot/rollout limits, commit/push separately and restart checkpoint. Main remains under review.

## Limits / acceptance

Pending implementation. This feature fences source imports. Atomic successful processing/chunk/Storage publication, processing-side disconnect behavior and stale-active-worker takeover remain the next RS06 subfeature; do not claim these are already resolved. No claim that an already sent external request can be recalled.
