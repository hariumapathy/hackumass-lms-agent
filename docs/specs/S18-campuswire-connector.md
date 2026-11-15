# S18 — Campuswire connection feasibility and read-only posts

**Status:** Draft / feasibility only (requested for the feature list, 2026-11-14). **Depends on:** S10, S13. No implementation or live support claimed.

## Design plan
Determine whether a student can complete Campuswire login normally and whether the worker can reuse the resulting session for read-only access to their enrolled course feeds. Use the same encrypted-session and normalized course/post architecture as Gradescope/Piazza. Never accept passwords in chat, bypass MFA, or allow the AI to operate Campuswire directly.

## Implementation plan
1. Inspect primary documentation and the student's login flow. Establish whether a supported API exists; otherwise run a bounded session-reuse spike.
2. Record exact read operations, pagination, rate limits, enrollment/current-term fields, private-message boundaries and stable post URLs. Verify normal reads do not mark/edit/post content.
3. If feasible, expand this spec with real input/output shapes and scrubbed fixtures before implementation. If not, record the blocker and keep the feature unavailable in the UI.
4. Tests first, then connector + saved login + worker + UI wiring. Follow credits/vendoring rules for reused code.

## Proposed test plan (finalize after spike)
- S18-T01: only enrolled student courses are returned.
- S18-T02: normalized posts preserve question/instructor-answer content and canonical URLs.
- S18-T03: author names/private messages excluded according to the final scope.
- S18-T04: pagination, incremental refresh and rate limiting.
- S18-T05: expired session becomes Reconnect; no password/write methods.
- S18-T06: fixture-backed worker → stored chunks → citation integration and per-student isolation.

## Needed for a live check
A teammate with a Campuswire course must complete their own login/MFA. No implementation should be called complete until one enrolled course and its source links are verified.
