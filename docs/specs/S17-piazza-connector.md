# S17 — Piazza connector

| | |
|---|---|
| **Status** | Built (fixtures); live spike pending a real login |
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
- [x] Spike result recorded (offline part; live check pending a real login)
- [x] Fixture tests on normalized posts pass
- [ ] Real sync of one class shows posts with working links (needs a real Piazza login)
- [x] Credits and notices updated

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

## Spike results (2026-11-14, Neal)
- **Offline (done):** piazza-api 0.16.0 needs no login call to work: `PiazzaRPC.request` POSTs JSON to `https://piazza.com/logic/api?method=...` with the `requests.Session` cookies and sends the `session_id` cookie as the `CSRF-Token` header itself. So a session holding the piazza.com cookies of the S13 storage state is all it needs (`PiazzaClient.from_storage_state`). Verified against a fake transport: only piazza.com cookies are sent, the CSRF header equals `session_id`, only `user.status` / `network.get_my_feed` / `content.get` are called.
- **Live (pending a real login):** not run here (no real Piazza account on this machine). To run: `make api`, `POST /connections/piazza/login`, sign in in the window, then a full sync. Things to check: (1) the login lands on `/class...` (our logged-in signal), (2) `session_id` is in the saved cookies, (3) Piazza's logged-out error text matches our auth regex (`login|session|auth|expired|csrf`), (4) feed `updated` is ISO with `Z`. If the requests session is rejected, Piazza stays out of the MVP (rule 1).

## Implementation notes (2026-11-14, Neal)
- Code: `backend/app/connectors/piazza/` — `_vendored/` (piazza-mcp @ `782f62c`, MIT: `client.py` with `user_login` removed, `from_storage_state()` + throttle added, search/filtered feeds removed; `normalizer.py` and `models.py` unchanged apart from import path + ruff formatting; `LICENSE-piazza-mcp`), `mapping.py` (pure: NCourse/NPost, author role, current-term filter), `connector.py` (`PiazzaConnector`, registered in `connectors/registry.py`), `login.py` (`PIAZZA_LOGIN`, added to `browser/manager._LOGIN_SPECS`, so `POST /connections/piazza/login` works through S13).
- **piazza-api 0.16.0** pinned.
- Mapping: `NCourse.platform_id` = network id, `name` = class name, `code` = `course_number` (e.g. "COMPSCI 311"), `term` (e.g. "Fall 2026") so S16 can merge with Canvas. `NPost.platform_id` = `"<nid>:<post number>"` (posts are looked up by user + platform + platform_id, no course, so the number alone would collide). Body = `"Q: …\n\nA (instructor): …\n\nA (student): …"` (notes: `"Note: …"`; followups left out), plain text from the vendored normalizer. `author` = "Anonymous" if the original revision's `anon` is not `"no"`, else "Instructor" for `instructor-*` tags, else "Student"; no names, emails or user ids are stored. `posted_at` = created (fallback updated, then now), `source_updated_at` = updated.
- Current term (rule 2): `get_user_classes()` drops Piazza's `status`, so classes are filtered by term text against the clock (Spring Jan–May, Summer mid-May–Aug, Fall mid-Aug–Dec, Winter mid-Dec–Jan); unreadable terms are kept.
- Feed (rule 3): one `get_my_feed(limit=300)` per class (newest updated first); `get_post` only when the feed item's `updated` is after `ctx.last_success_at` (or no previous success). Whenever an unchanged post is skipped, the feed hits the cap, or a post is unusable, the class is added to `ctx.incomplete` as `(nid, "posts")`, so full-scope removal never marks un-yielded posts `removed` (a post deleted on Piazza therefore stays until a full re-sync with no earlier success).
- Errors: 401/403, piazza-api auth errors, missing `session_id` cookie, or an API error mentioning login/session/auth → `AuthExpired`; timeouts, network, 429/5xx, other API errors → `PlatformError`; one unusable post is skipped. Throttle: ≥ 1 s between HTTP requests (in the session, so every piazza-api call counts).
- Scopes: `full`, `course`, `item` (`platform_id` = `"<nid>:<n>"`, fetched directly), `material` (nothing).
- Login detection: a piazza.com `/class` or `/class/...` page without a password field (logged-out visits redirect to `/account/login`). `check_url` = `https://piazza.com/class`.
- Tests: `tests/connector/test_s17_piazza.py` (T01–T06 + courses, cap, scopes, throttle, cookies, login detection) with `tests/piazza_fake.py` (fake piazza-api transport over hand-written `tests/fixtures/piazza/*.json`, fake names/ids); `tests/integration/test_s17_piazza_db.py` (`run_sync` into the local DB).
