# Failed processing and repair (S45)

Review branch only. Apply additive migration0005 before updated workers/API; preserve the database and existing Fernet key. See [S44 delivery](processing-recovery.md) and [S45 spec/tests](../specs/S45-processing-retries-and-recovery.md).

Each source revision allows at most four logical attempts, including interrupted deliveries accounted for by recovery. Delays are30/120/600seconds; the five-minute maintenance cadence and queue backlog can add delay. Duplicate deliveries cannot bypass the atomic attempt/deadline checks. Worker embeddings use no nested provider retry loop; chat behavior/provider remains unchanged. A document with multiple batches can still make multiple provider requests within one logical attempt, and a crash may repeat I/O. This is a repair policy, not a billing ledger or exactly-once guarantee.

Temporary HTTP408/409/425/429/5xx, network and Storage failures retry. Configuration failures stop with an internal code; unreadable content stops as permanent. Old chunks remain available and changed-source evidence retains its existing status warning. Material failure state compares the source hash so an old failed processor cannot label replacement content failed. Failed posts use the same durable policy. Binary downloads require working original-file Storage configuration; inline text/transcripts have no binary original to store.

A single file401/403 is file-level access failure, not proof the whole Canvas credential expired. It does not mark the entire account disconnected. A different saved download reference, changed source or newly validated platform credential can resume it. The same inaccessible URL is not treated as a fresh authorization signal on every import. Whole-grant reconnect behavior remains for verified AuthExpired from platform authentication. Credential replacement and owner/platform-scoped auth-intent reset share a transaction.

## Automatic and operator recovery

Maintenance reconciles an old dispatched intent only after a nonblocking intent lock and a fresh eligibility check. A matching queued/running job prevents takeover. A busy intent cannot stall other accounts' recovery. Each new dispatch clears the previous attempt-start marker before enqueue so abandoned replacement deliveries consume their own interruption budget and cannot appear stale using an older timestamp.

Still-active stale workers are **not** blindly replaced. Drain/repair worker ownership and inspect queue state before repair; source/index publication and disconnect fencing remain the next gate. Ten minutes is a stale-dispatch threshold, not a promise to forcibly stop a live job.

After repairing configuration, an operator can run:

```sh
cd backend
uv run app retry-processing --user-id <local-auth-user-uuid>
```

This resumes only that user's configuration/exhausted intents, rotates revision and respects the pending-deletion barrier. It does not reopen permanent or source-auth failures blindly. If an exhausted legacy record has no saved payload, resume returns it to metadata discovery rather than pretending it can be processed. Normal changed-source observations create fresh policy state. Student screens do not expose this operator command or credentials.

Legacy unchunked posts can be repaired from their stored body, unless a legacy processor is already queued/running. Legacy Canvas files/syllabi with no intent need real metadata: recovery uses stored course/file IDs and existing encrypted connection credentials through normal targeted sync jobs. It skips active legacy processing and open targeted runs. Each metadata-discovery phase has four persisted attempts, including successful-but-empty403/404/no-record results; exhaustion stops the loop. No signed download URLs are fabricated. Other legacy platforms need a fresh normal source observation. Keep old producers/workers drained during rollout.

## Verification and remaining gates

Tests use synthetic users, fake processors/providers and local queue/database only. Coverage includes provider classification, current-chunk preservation, durable delay/exhaustion, concurrent duplicates, orphaned replacement budgets, stale snapshot and busy-lock recovery, old-source failure state, auth-reference/credential refresh, legacy active-job guards and bounded metadata discovery. Final counts and independent review are recorded in the devlog/spec.

Atomic successful source/index publication, active-worker takeover, complete disconnect/permission revocation, embedding identity, extraction resource isolation, external Storage orphan reconciliation and backup/key restore remain separate launch gates. No public deployment or fresh Google/real-course verification is claimed.
