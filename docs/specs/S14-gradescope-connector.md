# S14 — Gradescope connector

| | |
|---|---|
| **Status** | Draft |
| **Stage** | 2 |
| **Role** | A |
| **Depends on** | S13 |
| **Folders** | `backend/app/connectors/gradescope/` |

## Purpose
Read the student's Gradescope courses and assignments (with release/due dates and submission status) from pages they can see when logged in, using the saved browser session (S13). Fixed parsing scripts; no AI browsing.

## Inputs
- `ConnectorContext` with Playwright storage state.
- `SyncScope`: `full` or `course`.

## Outputs
- `NCourse` per Gradescope course (`source_url` = course page).
- `NItem` per assignment: `type` (mapped like S11 rule 2), `title`, `due_at`, `source_url` = assignment page, `raw` = `{released_at, late_due_at, submission_status, score?}`.

## Interface
```python
GRADESCOPE_LOGIN = LoginSpec(platform="gradescope", start_url="https://www.gradescope.com/login",
                             is_logged_in=<account page reachable / course list present>)

class GradescopeConnector(Connector):
    platform = "gradescope"
    async def validate(self, ctx) -> AccountInfo
    def fetch(self, ctx, scope) -> AsyncIterator[NormalizedRecord]

# Pure parsers: unit-tested against saved HTML fixtures
def parse_course_list(html: str) -> list[NCourse]
def parse_assignments(html: str, course_platform_id: str, tz: str) -> list[NItem]
```

## Behavior and rules
1. **Fetch HTML with the session, parse with pure functions.** Navigation uses Playwright with the saved state (or `httpx` with the extracted cookies if that proves reliable; decide during implementation and note it in the spec).
2. Pages: account/course list page → each course's assignments page. Selectors are confirmed against fixtures captured from our own accounts in Stage 2 and **listed in this spec when known**.
3. Dates: prefer machine-readable attributes (e.g. `datetime` on time elements) when present; otherwise parse displayed text in the course's timezone (default `America/New_York`). Never guess a date that can't be parsed (`due_at=null` + warning).
4. `platform_id`: Gradescope's numeric course/assignment IDs from URLs.
5. Throttle: ≤ 1 page/second per user.
6. Login redirect on any page → `AuthExpired`.
7. Selector failure (page layout changed) → `PlatformError("layout_changed")` with the page saved to a debug fixture path (not committed) so a parser fix can be written (the "self-healing connector" stretch idea starts here).

## Errors and edge cases
| Case | Expected behavior |
|---|---|
| Course with zero assignments | Course synced, no items |
| Assignment without a due date | `due_at=null` |
| Late due date present | Stored in `raw.late_due_at`; `due_at` = regular due date |
| Layout change breaks selectors | Run fails with `layout_changed`; previous data stays; UI shows "sync error" |

## Acceptance criteria
- [ ] Parsers pass on scrubbed fixtures from at least two different courses
- [ ] Real sync with a saved session produces courses + items with correct due dates (spot-check 5)
- [ ] Selectors and page URLs documented in this spec after capture

## Test plan
| ID | Test | Type |
|---|---|---|
| S14-T01 | `parse_course_list` extracts IDs, names, terms from fixture | connector |
| S14-T02 | `parse_assignments` extracts title, IDs, due dates (timezone-correct) | connector |
| S14-T03 | Unparseable date → `due_at=null`, warning recorded | connector |
| S14-T04 | Late due date stored in `raw` | connector |
| S14-T05 | Login-page HTML → `AuthExpired` | connector |
| S14-T06 | Missing expected table → `PlatformError("layout_changed")` | connector |
| S14-T07 | Type mapping reuses S11 rules (exam/quiz/lab/project) | unit |

## Out of scope
Submitting anything, downloading submissions, rubric details, grades UI (stretch).
