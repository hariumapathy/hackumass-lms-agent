# S45 — Bounded failed-processing retries and repair

**Status:** Implemented on review branch, user-authorized sequential implementation, unmerged. RS05 / narrow P03; follows S44. Internal additive migration0005 only; public API/SSE/seed unchanged. Gemini stays; model-cost/provider work deferred.

## Spec

Temporary download, provider and Storage failures cannot silently finish indexing successfully. Classify failures without logging source text/credentials/provider bodies. Retain old current chunks on failure. Retry logical processing attempts at most4 times per source revision, with30/120/600second delays. Queue replays must honor the same attempt count and next-attempt time. New intent tasks use this durable retry policy; legacy tasks retain bounded framework retries. Disable nested provider retries in worker embedding calls so the two retry loops do not multiply.

Configuration/auth/permanent errors stop automatic work with an explicit internal reason. Source authentication keeps the existing reconnect state; a changed source reference or newly validated credential may resume it. Changed source content rotates revision/reset attempts. Operator per-user resume after configuration repair can reset configuration/exhausted intents and rotate revision; it must respect pending deletion and cannot resume another user's work or silently reopen permanent/auth failures. Main student-facing errors remain plain language.

A single-file access failure does not prove the whole grant expired; retain that distinction. Reconcile dispatched intents with no matching active queued/running job after a stale threshold; count/limit interrupted attempts. Never blindly re-run work still owned by an active queue job. Legacy unchunked posts can recover from stored owner-scoped body. Legacy Canvas materials without saved payload require bounded targeted metadata refresh using existing connector credentials and course IDs, not guessed/signed links. Do not refresh while a legacy processing job is active. Fully stale active worker ownership/publication remains RS06/operator drain work.

## Test cases

| ID | Expected behavior |
|---|---|
| S45-T01 | HTTP429/5xx/timeouts/source availability/Storage transient failures retry; auth/configuration and corrupt/unsupported content stop appropriately; exception/log text never leaks provider/source secrets |
| S45-T02 | Material failure preserves old current chunks/version; post failure gets the same durable retry policy |
| S45-T03 | Backoff, four-attempt exhaustion and duplicate delivery persist across executor instances; immediate replays cannot bypass delay/limits; successful retry clears ciphertext and completes |
| S45-T04 | Old failed/completed revision cannot mutate replacement source/counters/material state; changed source resets policy |
| S45-T05 | Stale dispatched work with no active matching queue job recovers; an existing todo/doing job is left alone |
| S45-T06 | Operator resume is owner/deletion scoped and rotates revision; source auth resumes only on trusted reobservation |
| S45-T07 | Legacy stored post repair and targeted Canvas material refresh are bounded, scoped, secret-aware and skip active jobs; no live platform/model in tests |
| S45-T08 | Existing sync/processing/deletion/outbox tests and full backend/static checks green |

## Design plan

Add attempt count, next-attempt/start timestamps, blocked reason and sanitized error code to the private intent. Shared failure classifier returns content-free typed failures; retryable failures also inherit PlatformError for legacy compatibility. Material processing records failed state then raises typed failure rather than swallowing; post/factory errors are classified at worker/executor boundaries. Durable executor claims one due attempt under its existing locks, persists retry/blocked state with owner/revision CAS and guarded material updates, and leaves terminal successes unchanged.

Pending/reservation queries honor retry time/blocked state. Lost-dispatch reconciliation checks queue owner/intent/revision and active status before resetting; active stale ownership is an operator alert/drain gate, not proof of safe concurrent publication. Recovery runs separately from ordinary source scheduling. Operator CLI resumes only explicit per-user configuration/exhausted work. Fresh source observation can rotate an auth-blocked intent; source changes reset all policy state. Legacy recovery uses stored posts or normal targeted Canvas sync through existing jobs, with per-user guards and known credentials.

## Implementation plan

1. Write classifier, durable backoff/exhaustion/stale/CAS/resume tests and observe red. Extend the existing old-chunk failure regression to expect a classified failure.
2. Add/apply additive0005 without reset; implement classifier and intent policy/CAS, worker-level provider retry ownership and recovery.
3. Add bounded legacy repair and operator retry command; no platform passwords or fabricated URLs.
4. Run focused/full/static checks and current-feature review; document exact retry/active-worker limits, commit/push separately and restart verified worker checkpoint.

## Limits / acceptance

Initial14 tests failed, with further red regressions for unchanged inaccessible references, stale source failures, retry/recovery races, binary Storage configuration and orphaned replacement budgets. Final32 new tests and full backend676 passed/1 optional Storage skip; Ruff/format/pyright green. RAG and security reviews found no further blocking issue after corrections. See [operator repair guide](../deployment/processing-retries.md). This does not claim source/index atomic publication, a dead-worker takeover protocol, complete platform-disconnect fencing or embedding provenance; those are next gates. Retry durations are scheduling minima: periodic worker cadence/queue backlog can add delay. Extraction resource isolation, orphan Storage reconciliation and backup/key restore remain deployment gates.
