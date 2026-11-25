# S42 — Incomplete Canvas listings never imply removal

**Status:** Implemented on review branch, user-authorized sequential implementation, unmerged. RS02 / narrow P02. No database/public API/SSE/seed changes.

## Spec

A file listing that stops at the supported-file cap must mark that course's `materials` listing incomplete. Exactly reaching the cap after exhausting the authoritative list is complete; an additional supported file proves truncation. Other courses/resources keep their own completeness decisions. Hidden Files tabs require module fallback, but module discovery is a subset of all course files and is always non-authoritative for absence/removal. Missing/forbidden module file details and capped module enumeration also report incomplete.

Non-list JSON returned by a paginated Canvas endpoint is a platform failure, not an authoritative empty list. Errors after partial pagination may retain already imported records but never run full-scope removals. Genuine empty/complete authoritative listings still remove absent sources through the existing pipeline. Canvas remains GET-only; no live tokens/models in tests. Existing inaccessible/windowed-section protections remain.

## Test cases

| ID | Expected behavior |
|---|---|
| S42-T01 |99/100/101 supported files with cap100 yield99/100/100; only101 marks materials incomplete |
| S42-T02 | Files403 + successful modules still marks incomplete even below cap; inaccessible individual module file and module cap mark incomplete |
| S42-T03 | Non-list pagination JSON raises PlatformError rather than yielding an empty authoritative list |
| S42-T04 | Import full listing, then capped or module-only listing: old unseen files remain active; another fully listed course can still remove absent files |
| S42-T05 | A genuinely complete shorter list removes missing files; partial-page failure/non-list response cannot infer removals |
| S42-T06 | Existing Canvas connector/DB/pipeline tests and full backend/static checks stay green |

## Design plan

Use existing `ConnectorContext.incomplete` course/table pairs; no new schema or result envelope. Set the pair where file caps or non-authoritative fallback are identified, and inside module discovery for skipped/capped details. Continue using existing `_Store.mark_removed` skip logic. Validate list shape in the GET-only client's paginator and raise a content-free PlatformError on invalid shape. Do not redesign course selection, presence restoration, execution generations or index recovery in this fix.

## Implementation plan

1. Add mocked HTTP cap-boundary/fallback/shape tests and real local-DB two-pass removal tests, observe red where existing behavior is unsafe.
2. Add minimal completeness markings and strict pagination list validation.
3. Verify isolation of skipped resources versus complete removal and failure behavior with scrubbed fixtures.
4. Run focused/full backend, lint/types, current-feature review; document module fallback's conservative removal policy and commit/push separately. Main remains unmerged.

## Acceptance / evidence

Initial13 connector/DB regressions failed;4 completeness/failure controls passed. Final20 new cases pass, including both cross-page cap boundaries requested in review;66 focused Canvas/pipeline checks passed before those2 additions. Full backend619 pass/1 optional Storage skip; lint/format/pyright green. Independent current-feature review found no blocking issue. Module-only discovery may retain files no longer visible in modules; this is deliberate until an authoritative Files listing is available. It is not permission revocation or proof every file was discovered. UI discovery/readiness improvements remain later work.
