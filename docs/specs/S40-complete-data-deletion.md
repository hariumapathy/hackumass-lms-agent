# S40 — Clear saved data completely and fence old work

**Status:** Implemented on review branch; user-authorized sequential implementation (2026-11-24), unmerged. **Package:** P01c. Supersedes S20's deferred file/job cleanup. Contract proposal: additive internal deletion-state table; existing DELETE /me/data still returns204 only after successful cleanup. Auth account stays; reconnecting later is allowed. Gemini unchanged.

## Spec

A successful clear removes all owned application rows, connection secrets, calendar access, original files and queued/retained job payloads. Another student's data is untouched. Existing requests/imports finish before cleanup; new work is blocked while cleanup is pending. Previously queued work and browser login completions cannot restore deleted data after a reconnect. A partial failure must never report success: retain a durable pending checkpoint, refuse normal work, permit the same authenticated DELETE to retry, and retry from the worker schedule. Keep only user ID, generation, state and timestamps as operational deletion metadata. Auth deletion/backup expiration are outside this clear-saved-data action.

## Test cases (written before implementation)

| ID | Expected behavior |
|---|---|
| S40-T01 | HTTP deletion clears every user table and exact Storage prefix, preserves Auth and another user's rows/files; repeat succeeds |
| S40-T02 | Storage failure returns retryable503, persists pending and blocks normal HTTP requests; retry completes and unblocks |
| S40-T03 | Active shared work delays cleanup; new work is refused after pending commits; timeout leaves pending for maintenance retry |
| S40-T04 | Queue cleanup removes owned pending/terminal payloads, redacts and aborts doing jobs without deleting their acknowledgment row, preserves foreign/scheduler jobs |
| S40-T05 | Original deleted sync-run cannot execute even after reconnect; old material/post jobs find no parent |
| S40-T06 | Login completion from a previous deletion generation cannot save credentials; current-generation completion still works |
| S40-T07 | Pending cleanup survives service restart, maintenance retries it, and terminal redacted jobs are purged |
| S40-T08 | New state has RLS/no client write access; locks release on cancellation/error; existing auth/public routes and SSE behavior remain compatible |

## Design plan

Add an internal `account_data_state` row keyed to Auth, with monotonically increasing generation and pending/complete state. Commit pending before waiting for an exclusive user advisory session lock. Normal authenticated DB API requests hold a shared lock for the response lifetime (including SSE), then check pending. Use an auth-only dependency for DELETE, avoiding lock upgrade deadlock. Review amendment: requests and login completion reuse their guarded data connection through a request-local context; serialize parallel tool connection leases and allow nested leases by the same task. Admit at most8 guarded API/login sessions against the max10 data pool, reserving capacity for deletion/maintenance. Losing the lock session therefore also loses the request's write connection; escaped tasks cannot borrow a fresh connection after the request ends. Worker/scheduler guards use their direct connections. Session locks require direct/session-pool PostgreSQL connections, **not transaction pooling**.

Once existing shared work drains, acquire exclusive ownership with a bounded wait, purge owned queued/terminal Procrastinate jobs and redact+request abort for doing jobs (retain rows until framework acknowledgment), delete application rows, remove Storage objects, then mark complete. Failure leaves pending; periodic maintenance retries without resetting existing imports. Successful completion can later permit new connections, but deleted sync jobs must still prove their original run exists. Browser login captures generation at start and validates it under a shared guard before saving. No passwords or new platform calls. File cleanup failures never silently skip storage when a key is absent.

## Implementation plan

1. Write HTTP/storage-failure/two-user, actual DB lock/queue and login-generation regressions and demonstrate red.
2. Add additive migration with RLS/revoked client privileges; apply only this migration locally, never reset retained data.
3. Implement shared/exclusive guards, durable deletion service, request dependency and worker/queue/login fences.
4. Integrate DELETE and periodic recovery; replace the obsolete S20 Storage xfail with real assertions. Use synthetic objects/providers only.
5. Run focused tests, complete backend/frontend checks, current-feature security review; document migration/connection/backup limits, update pitch/progress/devlog and commit/push this feature separately. Keep PR34 unmerged for contract review.

## Acceptance / evidence

Initial six DB tests red; login-generation, duplicate-login-window, stale merge, killed-lock, child-lease and Settings regressions also demonstrated red before their corrections. Final33 focused tests pass; full backend588 pass/1 optional Storage skip, then that local Storage round-trip passed separately with a local-only key supplied in memory. Frontend102 pass,6 browser E2E, production build and all lint/format/types green. Independent current-feature security re-review found no further blocking defect. See [operator and recovery guide](../deployment/data-deletion.md). Partial failures do not imply immediate completion; a retryable message says to retry clearing saved data. No new status endpoint or public SSE event is introduced. A network/process failure during an external Storage upload remains a distributed side-effect boundary: orphan-object reconciliation after failure/restore is still a deployment gate; no claim of atomic DB+Storage transactions. Backup lifecycle and institutional deployment approval remain separate launch gates.
