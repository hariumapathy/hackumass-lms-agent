# S39 — Browser identity transitions isolate cached and in-flight work

**Status:** Implemented on review branch, not merged (user-authorized sequential implementation, 2026-11-24). **Package:** P01b; after S37/S38. No server schema/API/SSE changes. Existing S35/S36 interaction behavior retained.

## Problem / behavior

A browser-wide QueryClient and unscoped keys can retain account A's views for account B. Requests and chat streams started as A may complete after switching/signing out, including a stale 401 that signs out B. Component-local draft/history state can persist. A late initial getSession response can overwrite a newer auth event.

On identity change or explicit sign-out: invalidate/cancel old API/stream requests, cancel/clear old query and mutation caches, replace the account's QueryClient and remount descendant local UI state before displaying the next identity. Old responses cannot enter the new cache or invoke its sign-out handler. Explicit sign-out hides private state before awaiting the provider. While provider logout is pending, ignore non-null provider events; new sign-in methods wait for the logout operation to settle. A logout action supersedes any initial session snapshot, even if it finishes later. Same-user token refresh retains cache/drafts. Ignore late initial session snapshots after a newer auth event. Keep session tokens out of persistent app caches and diagnostics.

## Test cases

| ID | Case / expected result |
|---|---|
| S39-T01 | A warm query cache and local draft disappear on A→B; B fetches own content |
| S39-T02 | Delayed A response cannot repopulate B's cache; old client cleared |
| S39-T03 | Delayed old 401 cannot sign out B; stale REST request rejects as cancellation |
| S39-T04 | Same-user token refresh retains cache/local state and uses refreshed auth |
| S39-T05 | Auth event wins over a delayed initial getSession snapshot |
| S39-T06 | Sign-out clears UI immediately even while provider signOut is pending |
| S39-T07 | Active chat stream is canceled/fenced on identity change; no old text/citations arrive |
| S39-T08 | Existing auth/shell/chat/settings/stream tests and production build remain green |

## Design plan

Move query ownership to AuthProvider: one client per active identity boundary, including anonymous state; no global browser cache. Every identity transition synchronously rotates a request generation, aborts tracked REST/SSE work, clears the previous cache and remounts children via a boundary key. Use ref-held current session for async token/provider callbacks and a monotonically ordered bootstrap/auth-event guard. A same-user token refresh updates credentials without rotating the boundary.

Centralize request cancellation/generation assertions in a small browser request-scope helper shared by REST and SSE. Capture config at request start; check generation after token acquisition, response/body parsing and before event/401 delivery. Independent manual AbortSignals retain their behavior. Requests already committed on the server remain authorized to their original owner; this fix does not claim it can undo server work. Existing backend authorization stays required.

## Implementation plan

1. Write synthetic two-account provider/cache tests, delayed REST/401 and SSE tests; observe current failure before code.
2. Add per-identity QueryClient ownership and subtree reset; remove browser singleton. Guard bootstrap order and immediate sign-out.
3. Add shared request generation/abort tracking; fence REST parsing/401 and SSE dispatch. Never persist tokens or private context in global storage.
4. Run focused and full frontend tests, lint/type/build, mock browser E2E. Security review current fix only, record results, commit/push before next feature. Read installed Next16 auth/caching docs; preserve existing SSE contract.

## Acceptance

Verified: six of seven initial synthetic cases failed against old code, visibly retaining A content/draft under B; same-user refresh already passed. Current-feature security review then found logout resurrection; two additional red regressions now pass. All nine new S39 tests / 24 focused auth+SSE tests pass; full frontend101 pass, lint/types/production build and six browser E2E pass. Backend unchanged from S38 baseline569 pass/1 skip/1 xfail. Security re-review found no further critical defect. No claim of a previously demonstrated server cross-user leak; original finding was a browser-state risk now covered by regressions.
