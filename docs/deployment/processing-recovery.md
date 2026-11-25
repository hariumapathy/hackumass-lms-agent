# Processing recovery: durable intent delivery (S44)

Review-branch implementation; no production rollout. Read [S44](../specs/S44-durable-processing-intents.md) and the latest [checkpoint](../handoff/overnight-2026-11-24.md).

Apply additive migration0004 before enabling the updated sync worker. Do not reset or seed retained data. The API/worker database role needs access to internal `processing_intents`; client roles have no grants/policies. Keep the existing Fernet key available through restarts/restore: material source text/transcripts/download references are encrypted in this table. Its rows cascade with source/Auth deletion and are explicitly purged by clear-saved-data. The agent reads ordinary scoped course data, never this outbox.

A new/changed source and its indexing intent commit in one record transaction. Persistence failure rolls back that record and aborts absence inference. Later platform failure does not discard previously committed intents. Best-effort callbacks enqueue promptly after a successful import; callback/queue connection failure cannot leave metadata marked running merely because its notification failed. Periodic worker maintenance attempts up to100 eligible intents per pass, independently of a successful full import.

Dispatch reserves a five-minute lease. If the process dies before enqueue, maintenance can reclaim it after expiry. If enqueue succeeds but acknowledgment is lost, delivery can repeat. **Delivery is at least once**. New tasks intentionally have no shared queueing lock: Procrastinate's unique todo key can collide when an original running job retries while a replay is queued. Stable task execution lock and worker DB advisory lock serialize one intent; owner/revision/completion guards make duplicate deliveries safe. Provider downloads/embeddings are not promised exactly once across a crash before completion.

Lease acknowledgments compare owner, revision and lease token. Reset/completion compare owner/revision. A worker that finishes or resets before the enqueue acknowledgment clears its lease; the late acknowledgment cannot strand it. A source replacement rotates revision, leaving old queued jobs harmless. Successful/unchanged/skipped/empty outcomes set completion and discard encrypted payload; failed processing never masquerades as completed.

Deploy by draining old workers, applying additive migration, then starting the updated workers/producers. Old workers do not know the new task name. Existing legacy material/post task names remain registered for already queued work. Stop the development worker during DB fixtures; their queues and model keys must never be confused with a live-data smoke check.

## Remaining gates

- RS05 is implemented in S45 on the review branch: see [retry/repair policy](processing-retries.md). S44 alone fixes delivery; S45 adds bounded failed/orphan repair.
- RS06: source/index publication generations and disconnect-vs-running-work policy. Existing disconnect retains imported data; pending processing can still use retained source references. Do not advertise disconnect as complete data deletion.
- Legacy pending materials/unchunked posts without intents are recovered when next observed with usable payload; payloads never stored before S44 cannot be reconstructed from ciphertext that does not exist. Previously failed/processing legacy materials need the next recovery policy.
- Signed external URLs can expire. Fresh source discovery/refresh, extraction limits and truthful imported/organized/searchable readiness remain separate work.
- External Storage upload orphan reconciliation and backup/key/deletion restore policy remain launch gates; no atomic Postgres+Storage promise.
