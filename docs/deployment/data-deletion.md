# Clearing saved data (S40)

Implementation is on `codex/post-hackathon-implementation` / draft PR34, **not main**. Review the [spec and test cases](../specs/S40-complete-data-deletion.md) before rollout.

## Operator setup

Apply additive migration `0003_account_data_state.sql` before deploying the API/worker changes. For an existing local stack, use the pinned Supabase CLI's `migration up --local`; **never reset or seed an existing student's imports**. This session applied only0003 to the retained local DB and registered it in local migration history. A fresh DB still uses the normal ordered migrations. Review/grant the least-privilege runtime role access to the new internal table; authenticated/anonymous clients have no table privileges or policies. No public API/SSE/seed fields changed.

Use a **direct or session-pooled Postgres connection**: deletion uses session advisory locks. Transaction-mode pooling cannot preserve these locks and is unsupported. API requests and login completions share their guarded data connection with repository/tool calls, including streamed responses. Parallel tool leases serialize; nested leases in the same task reuse the connection. At most8 guarded sessions per API process enter against the current10-connection pool, reserving capacity for cleanup. Tune concurrency/connection budgets together before scaling. Deliberate browser-login background tasks get a separate generation guard, while escaped request tasks cannot obtain a fresh lease after response cleanup. An entered child lease drains before guard release; after5seconds the connection closes rather than being recycled with stale work attached.

The API and worker need the configured Storage service key and access to the private `materials` bucket. A missing key or failed Storage request leaves deletion pending; it never returns204. No credentials or source payloads appear in cleanup logs.

## Lifecycle and recovery

The authenticated `DELETE /me/data` commits an internal pending checkpoint and increments the account's data generation once per new deletion. New ordinary API/worker work is refused. Existing shared work drains; deletion waits at most5seconds for exclusive ownership and otherwise returns a retryable503. A repeated DELETE resumes the same pending generation.

Under the exclusive lock, cleanup removes owned application rows and connection secrets, invalidates calendar links, removes queued/terminal job payloads and deletes `users/{user_id}/` files. Running Procrastinate rows are retained with only a deletion-owner marker and an abort request so framework acknowledgment still succeeds. Source text/download payloads are removed. A stale sync must still prove its original sync-run exists; merges and login completion also validate generation. Only after successful Storage cleanup is the checkpoint complete and normal work permitted again. Auth account remains, so the student can reconnect later. The app signs out after a successful clear.

Settings keeps its privacy action available even when account loading is blocked. The student can reopen Settings, type DELETE and retry. The normal worker schedule also retries up to50 pending accounts every5minutes and reaps redacted terminal job bookkeeping. Recovery requires a running worker; a stopped worker means manual retry remains necessary. Use internal SQL/operator monitoring for pending counts/age; no new public status endpoint was added.

## Practical limits / launch gates

This is a resumable application-data clear, not a distributed transaction across Postgres and Storage. A network/process failure during an external upload can leave an orphan object even if the database session disappears. Before public deployment, add and exercise orphan-object reconciliation, failure/restore testing and operational alerts; do not claim that database locks make object writes atomic. The killed-lock DB regression ensures an old API request cannot switch to a fresh healthy connection to recreate rows. It does not simulate a remote Storage network partition.

Already delivered files/answers, platform originals, external model retention, historical logs and backup copies cannot be recalled by this action. Define backup expiration and reapply deletion state after restore before admitting traffic or replaying jobs. Minimal Auth-linked generation/state/timestamps remain as deletion bookkeeping; deleting the Auth account is a different, currently unimplemented action. No production service, institutional login or real student's data was deleted during these tests.

## Validation

Synthetic two-user local-DB tests cover data/files, retries, lock drain/cancellation/loss, true SSE response lifetime, stale scheduler/merge/sync work, RLS, queue acknowledgment/reaping, child/tool leases and browser-login generation. Storage uses a fake in these regressions; existing optional local-Storage integration remains separate. See the spec/devlog for final suite counts and any skipped checks.
