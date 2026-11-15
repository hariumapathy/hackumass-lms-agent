# S17 — Piazza connector

| | |
|---|---|
| **Status** | Ready (Neal; user explicitly requested specification and implementation, 2026-11-14) |
| **Stage** | 4 (stretch; first stretch item for role A) |
| **Role** | A |
| **Depends on** | S10, S13 |
| **Folders** | `backend/app/connectors/piazza/` (+ `_vendored/`) |
| **Reuses** | [`piazza-api`](https://github.com/hfaran/piazza-api) 0.16.x (MIT, PyPI dependency) and the client wrapper, normalizer and models from [piazza-mcp](https://github.com/profess/piazza-mcp) @ `782f62c` (MIT, vendored). Review: [research/mcp-servers-review.md](../research/mcp-servers-review.md) |

## Purpose
Sync the student's Piazza posts (questions, instructor answers, notes) into `posts` so the agent can answer "did the professor say the final is cumulative?" with a citation. Reuse piazza-mcp's read-only client and normalizer; replace its **email/password login with the saved browser session** from S13.

## Inputs
- `ConnectorContext` with Piazza storage state (cookies) from a S13 live login (`LoginSpec` for `piazza.com`).
- `SyncScope`: `full` (recent posts per class) or `course`.

## Outputs
- `NCourse` per Piazza class (`platform_id` = Piazza network id, e.g. `abc123`).
- `NPost(kind="piazza")` per post: title, body (question + instructor answer + student answer, plain text), `posted_at`, `source_url` = `https://piazza.com/class/<nid>/post/<number>` (piazza-mcp's builder), `source_updated_at`.

## What we reuse
| Piece | From | How |
|---|---|---|
| `Piazza`, `PiazzaRPC`, network feed/get_post/search | `piazza-api` (PyPI) | Dependency |
| `PiazzaClient` async wrapper (timeouts, error mapping) | piazza-mcp `services/piazza/client.py` | Vendor; **remove** `user_login`, add `from_storage_state()` |
| `PiazzaNormalizer` + models (`PiazzaThread`, `PiazzaMessage`), source URL builder, HTML → text | piazza-mcp `services/piazza/normalizer.py`, `models/piazza.py` | Vendor as-is |
| **Not** used: MCP server, FastMCP tools, `.env` credentials, course allowlist config | | |

Vendoring rules as in [S14](S14-gradescope-connector.md#what-we-reuse-and-where-it-goes) (header, LICENSE copy, THIRD_PARTY_NOTICES, Devpost credits).

## Behavior and rules
1. **Spike first (≤ 1 h):** can `PiazzaRPC` use a `requests` session with injected Piazza cookies (it needs the `session_id` cookie and a CSRF header)? Record the result here. If not, Piazza stays out of the MVP.
2. Classes: `get_user_classes()`; only current-term classes.
3. Posts: feed newest first, cap 300 per class; fetch full post (`get_post`) only for new/changed feed items (compare `updated` time).
4. Body text = normalized question + instructor answer + top student answer, each labelled; stored as-is and wrapped as `<untrusted source="piazza">` by tools (S21).
5. Anonymous posters stay anonymous; store no student names (`author` = "Instructor" / "Student" / "Anonymous").
6. Throttle ≤ 1 request/second; `AuthExpired` on authentication failure.
7. Read-only: never post, edit or mark anything.

## Acceptance criteria
- [ ] Spike result recorded
- [ ] Fixture tests on normalized posts pass; real sync of one class shows posts with working links
- [ ] Credits and notices updated

## Test plan
| ID | Test | Type |
|---|---|---|
| S17-T01 | Normalizer turns a fixture post (question + answers) into one `NPost` with labelled sections | unit |
| S17-T02 | Source URL built as `https://piazza.com/class/<nid>/post/<n>` | unit |
| S17-T03 | Student names never stored (author mapped to role) | unit |
| S17-T04 | Unchanged feed items don't trigger `get_post` | connector |
| S17-T05 | Auth failure → `AuthExpired` | connector |
| S17-T06 | Client has no login/post/edit methods | unit |

## Out of scope
Posting or replying, private messages, running piazza-mcp as a server.
