# S48 — Publish only current processing results

**Status:** Implemented and verified on review branch; unmerged. Spec/design review and failing
regressions preceded implementation; current-feature review regressions were incorporated.

## Spec

An older material/post processor must never replace newer source content, current chunks,
file pointers, processing status or matching outbox completion. Source hash equality alone is
insufficient for A→B→A changes. Every processor captures an owner-bound parent source revision
before heavy work. Production intent execution also binds the expected intent/revision/source
snapshot before decoding its payload. Recheck under a short publication transaction; superseded
work stops without completing/failing the replacement intent. Existing published evidence stays
available on failed/superseded attempts; no partial chunk switch or pointer update.

Serialize processors per owner/parent across current and trusted direct entry points. Source
imports do not wait for heavy processing: their own short writes can invalidate its snapshot.
Successful publication atomically writes chunks, switches current flags, updates the material
pointer/version/status, and completes only its matching intent. No database row locks across
download, extraction, embedding or Storage calls. Status/no-op/skip paths use the same guards.

New binary uploads have an immutable per-attempt UUID in their persisted path. Even a timed-out
upload that finishes later cannot overwrite the current attempt's bytes at the same logical
version. Embed first, then upload to the unique path, then publish the pointer after revalidation.
Successful replacement publishes only its own file/extraction metadata; inline content cannot
retain a pointer to an older binary original. Unchanged-content reuse retains its existing policy.
Never delete an object referenced by another attempt. Unreferenced/ambiguous uploaded objects
remain an explicit reconciliation gate, not a claim of Postgres+Storage atomicity.

Legacy queue envelopes with arbitrary source payloads must not execute them against today's
source row. They only request delivery of an existing current durable intent; normal legacy
metadata recovery creates missing intents. Direct processor helpers remain trusted internal
fixture/worker interfaces, but always capture/check a parent source revision themselves.

## Tests

| ID | Case |
|---|---|
| S48-T01 | Material/post changes during embedding cannot publish old chunks/status; ABA with identical final hash/body is fenced |
| S48-T02 | Removed/deleted/foreign-owner parents cannot publish; unrelated parent proceeds |
| S48-T03 | Production intent snapshot fences a change before processor entry and an intent-only rotation during heavy work; replacement intent stays incomplete/unfailed |
| S48-T04 | Same-parent duplicate processors serialize and avoid duplicate current chunks; canceled lock acquisition leaks no session lock |
| S48-T05 | Late upload after a timeout cannot alter the successful pointer/bytes; separate attempts use different object paths even at logical version1 |
| S48-T06 | Chunk/pointer/completion transaction rolls back together; failed embeddings perform no upload; old published evidence remains intact |
| S48-T07 | Stale skipped/unchanged/failure paths cannot change replacement status or complete it; legacy tasks ignore old payloads and request current intent delivery |
| S48-T08 | Source revision changes for actual source/owner/course/presence mutations, not processing/freshness updates; schema/models/public serialization remain compatible |

## Design plan

Add private `source_revision` UUID to materials/posts with a DB trigger that rotates on source
field changes (including direct/legacy writes and ABA), excluding processing outputs/freshness.
Mirror it in internal row models but exclude it from serialization. Public API/SSE/seed shapes
stay unchanged. No new dependency.

Use a typed owner/parent/source snapshot plus optional expected intent binding. Parent revisions
are mandatory even in direct helpers; a scoped internal context carries only the production
intent binding through existing worker/test adapter signatures. Legacy queue tasks no longer
invoke arbitrary-payload processing. A per-parent session lock covers heavy processing; final
row locks are parent→intent, matching source capture. Checkpoint/finalization validates source
revision/hash/presence/course and intent revision; atomic completion uses the same transaction.
Storage paths retain owner/platform/course/file prefixes and add an attempt UUID to the version
filename. Existing persisted paths remain readable; tests stop assuming exact new filenames.

Review refinement: persist the observed parent revision in each durable intent; never adopt the
current joined revision at execution. Trusted capture refreshes same-hash pending work only when
it reobserves the source. A known course-only merge can explicitly rebind pending intents while
preserving attempt/blocked policy. Arbitrary mismatches stop old delivery: posts can be rebuilt
from current owned DB text; material payloads are discarded into bounded source-refresh recovery.
Rollout retires old pending material payloads whose origin revision was never recorded, and
rebuilds pending post work from current stored text. Completed historical work is preserved.

## Implementation plan

1. Add synthetic two-session race tests with fake providers/storage; observe meaningful failures.
2. Apply additive0007 with workers paused; add private revisions/snapshot/publication helpers.
3. Integrate guarded material/post publication/status/no-op/completion and legacy task routing;
   use immutable upload identity and embed-before-upload. Preserve finite retry ownership.
4. Run focused/full/static checks, schema/serialization regression and current-feature review;
   document rollout/limits, commit/push separately, then restart and HTTP-smoke local demo.

## Limits / acceptance

All S48-T01–T08 cases pass: **35 new regressions**, full **748 backend passed/1 optional Storage
skip**,102 frontend tests, Ruff/format/pyright and web lint/types green. Public OpenAPI excludes
private source revisions. Independent current-feature rereview found no remaining concrete
blocker. Additive0007 applied locally with imports retained; API/worker reloaded after fixture checks.
Earlier unchanged frontend6 browser/production-build checkpoint remains applicable. No paid
provider or fresh real-platform checks were run for this feature.

Review regressions included persisted queued-origin binding, preservation of stopped retry
policies after payload retirement, factory failures before core entry, course-merge rebinding of
only previously valid snapshots, material/post fourth-attempt migration boundaries and successful
inline replacement clearing obsolete binary metadata. Tests use synthetic users/fake providers.

This feature is successful processing publication and stale-output suppression. New external-download credential/connection fencing after disconnect/replacement,
download SSRF policy, active stale-worker takeover, object orphan reconciliation and embedding
provenance remain separate gates. Cached content may still be organized after disconnect per
S46 policy; this spec does not authorize fetching with a missing or replacement credential.
