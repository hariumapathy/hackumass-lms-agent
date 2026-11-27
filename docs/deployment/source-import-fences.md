# Source import fencing — S46

Implemented on `codex/post-hackathon-implementation`; review before merging/deploying. This
protects source imports, independently of the next successful-index-publication feature.

## Behavior

- Actual imports serialize per student/platform across full, course, item and material scopes.
  Other students/platforms use independent locks. Exact-scope enqueue deduplication remains.
- Queued work binds a connection ID and a private, random credential revision. Each credential
  insert/replacement rotates the revision, including identical bytes and direct legacy writes.
  Disconnect/reconnect creates a different connection ID, preventing reuse of an old grant.
- Connector checks run before Canvas GETs (including pagination), Gradescope page operations
  and Piazza read operations. An already-started request can finish; it cannot publish a later
  record after disconnect returns. No platform write methods were added.
- Source record writes, removal and final status publication recheck the grant under short
  database transactions. Disconnect waits only for a transaction already publishing a record,
  not for the remaining platform fetch. Existing imported data stays available.
- Old failures cannot mark a replacement connection expired/error/fresh. Terminal runs are
  immutable to ordinary worker updates, and duplicate terminal deliveries do not fetch again.
- Old queue envelopes without explicit grant IDs stop; they never adopt new credentials.
  An enqueue race returns a plain-language conflict using the existing error envelope.

Production `execute_sync` always supplies `expected_grant` loaded from the queued envelope.
The optional direct `run_sync` snapshot/no-secret path is a trusted internal fixture/helper
interface, not a public endpoint or a way for legacy production jobs to adopt current access.

## Rollout

1. Drain/stop **all** API/worker instances capable of writing connection secrets or running source
   imports. Old worker code does not enforce these fences; mixed-version workers are unsafe.
2. Apply additive `0006_source_grants.sql` after migrations0001–0005, in the migration transaction.
   It adds the private revision/rotation/invalidation triggers and retires pre-epoch queued source
   jobs/open runs. It preserves credentials, imported rows, historical completed runs and files.
3. Deploy the matching API/worker code together. Use a direct or session-pooled PostgreSQL URL;
   transaction pooling cannot preserve the session advisory execution lock.
4. Restart and check API/web/worker health. Manually Refresh connected accounts to create fresh
   bound jobs, or wait for their normal schedule. Do not replay legacy envelopes by supplying
   whatever credential is current now. Reconnect only if the saved credentials are unusable.
5. Run synthetic two-session regressions and staging normal-login/import checks. Automated tests
   use synthetic users/fake platform responses; they do not establish live provider availability.

Lock order is **connection → secret → jobs/runs**. The secret trigger does not lock its parent
connection because a legacy writer already holds the secret lock. Changing that order can
deadlock disconnect against a direct secret update. Network operations hold no grant row locks.
Canceled/failed session-lock acquisition closes its connection to avoid leaking a session lock.

## Limits and rollback

Successful file/chunk/Storage publication fencing, processing-side disconnect behavior and active
stale-worker takeover remain separate work. This change does not recall in-flight external reads,
make imports a push feed, or promise that an earlier committed source record will be removed on
disconnect. Clear saved data uses the separate S40 deletion barrier.

Do not roll back to old workers while retaining new queued work/credentials. Stop workers and
roll forward to corrected fence-aware code; preserve revisions and revocations. A full rollback
requires its own reviewed drain/queue retirement plan. Never reset or reseed student imports.
