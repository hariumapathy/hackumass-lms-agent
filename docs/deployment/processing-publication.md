# Processing publication fences — S48

Review branch only. This is the publication portion of RS06; external-download authorization
after disconnect/replacement remains S49. Keep Gemini; no provider/dependency change is needed.

## What is protected

Every material/post has a private source revision. Source field, course/owner or presence changes
rotate it even when the content hash returns to its original value. Processing outputs and
freshness timestamps do not. Internal row models exclude it from serialization.

Durable intents store the revision observed with their payload. Execution cannot bless an old
payload by reading today's parent revision. Both trusted direct helpers and intent workers take
an explicit owner/parent/source snapshot; production additionally binds the persisted intent
revision. Same-parent processors serialize, while different parents and source imports proceed.

Short transactions lock **parent → intent**, validate source/intent revisions, presence and owner,
and atomically switch current chunks, publish the material pointer/version/extraction metadata,
and complete that exact intent. Stale results, skips, no-ops and failures cannot alter replacement
state. Worker factory failures before core processing use the same source-generation fence.
The account-error path locks **connection → secret → parent → intent** before status mutation.
No row locks span network, embedding or Storage calls.

New binary objects use `.../v{version}-{attempt_uuid}.{ext}` with non-upsert upload. Embeddings
finish before upload; final publication rechecks ownership/generation before selecting the object.
A late timed-out upload cannot overwrite the winner. Existing stored legacy paths stay readable.
A successful replacement with inline text clears an obsolete binary pointer; failed/superseded
work preserves already-published evidence. Unchanged-content reuse retains the existing policy.

## Cutover and recovery

1. Drain/stop all API writers and source/processing workers; mixed old workers can bypass fences.
2. Apply additive `0007_processing_source_revision.sql` after0001–0006 as one migration transaction.
   It adds private parent/intent revisions and triggers. Imported content, existing chunks, files
   and completed history are preserved. Old incomplete material payloads had no recorded origin:
   their delivery is retired and their encrypted payload is discarded until a trusted observation.
   Pending posts can bind to current owned DB text. Existing stop categories/attempt counts remain;
   an interrupted fourth attempt is normalized to `exhausted` so explicit resume is still possible.
3. Deploy matching API/worker code and restart. Session locks require direct/session pooling.
4. Refresh classes to recreate retired source payloads. Canvas file/syllabus placeholders also
   use S45's bounded targeted metadata recovery, including prior `done` status from a crash gap.
   Other source kinds may need their normal/full source observation. Never construct a replacement
   download URL or adopt an arbitrary old queue payload.
5. Config/permanent/processing-exhausted states do not reopen on routine same-hash observation.
   Follow S45 explicit configuration/exhausted resume. Source auth needs a proven fresh reference
   or newly validated credential; a payload-free reconnect moves to source refresh. Metadata-phase
   exhaustion can recover when a later real observation finally supplies the missing source.

Known course-only merges explicitly rebind only pending intents that matched the immediately
previous locked parent revision/hash; their payload content did not change. Attempts/stop policy
are preserved. An already-stale payload is never blessed by a subsequent merge. Arbitrary material
mismatches discard the old payload into source-refresh recovery; posts can rebuild from current
owned DB text. Legacy queue envelopes request current-intent delivery and ignore arbitrary old
payloads; missing intents use the existing metadata recovery path.

## Remaining limits

This does not make Postgres and Storage one atomic system. An uploaded candidate whose publish
fails may remain unreferenced; ambiguous uploads and orphan reconciliation remain launch gates.
Do not delete a winning/referenced object during loser cleanup. The current file viewer uses the
published pointer; this change does not add historical byte snapshots to citations.

S49 must prevent new external reads with absent/replaced credentials. Cached owned content may
still be organized after disconnect per S46 policy. Download SSRF controls, active stale-worker
takeover, embedding provenance and the broader deployment plan remain separate work. No fresh
real-platform or paid-provider verification is implied by synthetic concurrency tests.

For rollback, drain workers and roll forward to corrected fence-aware code. Do not run old workers
against these new queued generations; do not restore retired payloads or undo credential/deletion
revocations. Pause workers before tests sharing the local database.
