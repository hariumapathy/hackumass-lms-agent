# Feature work plan and review branch

All unfinished/new feature changes live on **`codex/calendar-piazza-ui`**. Each feature gets its own commit after design plan → implementation plan → failing tests → code → verification. Do not merge this branch until Neal reviews it. The earlier Devpost/Gradescope documentation checkpoint is already on main.

| Order | Feature | State | Spec / deliverable |
|---|---|---|---|
| Complete | Canvas base demo | Live verified | S11, S32; real deadlines and Gemini citations |
| Complete | Devpost draft | Polished, ready to paste | [Submission copy](pitch/devpost.md) |
| Complete | Gradescope connection/import | Live verified: 20 courses, 238 assignments; independent source-date comparison remains | [S14](specs/S14-gradescope-connector.md), [runbook](gradescope-runbook.md) |
| 1 | Google Calendar | **Done, live-verified 2026-11-14 (Soumith)**; manual Google/Apple import of the file still to try | [S25](specs/S25-approvals-and-calendar.md); private feed + approved study sessions |
| 2 | Piazza | **Built** on `neal/s17-piazza` (fixture + DB tests, Connect Piazza UI); live login check pending | [S17](specs/S17-piazza-connector.md); saved session, read-only posts, source citations |
| 3 | UMass-inspired modern UI | Research/brief recorded; implementation after connector work | [S35](specs/S35-umass-ui.md) |
| 4 | Campuswire | Feasibility spike; no live implementation claimed | [S18](specs/S18-campuswire-connector.md) |

## Working agreements
- Each feature has separate design and implementation sections, test IDs, pass/fail evidence, and acceptance limits in its owning spec.
- Preserve the existing SSE contract and stream parser; improve rendering, loading states and responsive behavior without replacing the working backend.
- Keep each student's data scoped; worker owns platform credentials; no passwords or bypassing Duo; writes need a student click.
- Google cannot fetch a feed from localhost. The local demo can download ICS; automatic subscription needs a reachable HTTPS API URL.
- Run focused tests while working, then full relevant checks before each feature commit. Keep the seeded backup working.
- No silent substitutions: report unsupported login methods, undocumented APIs, deployment requirements or scope changes.
- Existing privacy/account-cache issues remain in [live-test-bugs.md](live-test-bugs.md); they are not implicitly fixed by visual work.
