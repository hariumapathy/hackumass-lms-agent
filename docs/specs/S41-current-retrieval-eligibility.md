# S41 — Current retrieval excludes removed sources

**Status:** Implemented on review branch, user-authorized sequential implementation, unmerged. Narrow RS01/P04 correction, independent of future indexing-generation work; source-listing/restoration corrections follow separately. No database/API/SSE/seed contract changes. Gemini retained.

## Spec

New material searches (lexical, vector and hybrid), direct material reads and course-overview syllabus retrieval return only current chunks whose owned material/post parent exists and is not removed. Apply eligibility before candidate limits/ranking, preserving user/course/kind/platform filters. Historical citation resolution remains owner-scoped and may resolve removed/non-current chunks with its existing removed/changed badge. Never delete those chunks to hide them from search.

Tool results expose the already computed `current`/`changed` status so the agent can distinguish changed source evidence; the nested course-overview syllabus result retains that field too. A changed source remains available with its status; this fix does not claim indexing is complete or that a changed excerpt matches the latest platform version. Removal during an existing run can still be reflected by final historical citation status; this is not a snapshot-transaction redesign.

## Test cases

| ID | Expected behavior |
|---|---|
| S41-T01 | Lexical, vector-only and hybrid searches exclude removed material and post parents, non-current chunks and foreign-user content |
| S41-T02 | Direct material read returns no removed/foreign chunks; active/changed parent remains readable |
| S41-T03 | Historical citation IDs still resolve for owner with removed/changed status; foreign resolution denied |
| S41-T04 | Search, material read and overview expose changed source status without changing source links or excerpt text |
| S41-T05 | Eligibility applies before candidate limits; removed hits cannot crowd all active matches out; course/kind/platform filters still apply |
| S41-T06 | Existing DB tools/runtime/citation and full backend/static checks stay green; no live models/platform calls |

## Design plan

Use one fixed SQL predicate for current chunk/parent eligibility in both search branches and the direct material query. Keep historical `chunks_by_id` unchanged. Existing scoped joins already enforce parent ownership. Preserve ranking, candidate counts and vector floor. Add `status` to internal chunk serialization and overview syllabus fields; public citation schema already supports status and needs no change. Keep this small correction separate from embedding provenance, listing completeness, restoration and publication/outbox changes.

## Implementation plan

1. Build synthetic DB fixture with owned/foreign active and removed material/post chunks and an old chunk; write failing eligibility/metadata tests and a passing historical-resolution guard.
2. Add shared SQL eligibility before candidate limits; retain owner/course/kind/source parameters.
3. Expose existing status in read tools/overview; amend S21 output documentation.
4. Run focused/full backend and static checks, current-feature review; update findings/progress/checkpoint and commit/push separately. Do not merge main.

## Acceptance / evidence

Initial6 eligibility/metadata regressions failed and historical-resolution guard passed; final11 source-presence tests pass, including lexical/vector/hybrid crowding, changed posts and foreign-parent mismatch.40 existing focused tool/runtime/citation checks passed before the added review cases; final full/static results recorded in the devlog. Independent current-feature RAG review found no blocking defect. This fixes source-presence retrieval only; semantic evidence quality and stale-generation publication remain later gates.
