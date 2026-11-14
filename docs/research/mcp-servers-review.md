# Review: third-party MCP servers for Gradescope, Piazza, Canvas

Reviewed 2026-11-14 (shallow clones at the commits below). **Decision (2026-11-14): Option A, borrow the pieces.** Applied in [S14](../specs/S14-gradescope-connector.md), [S17](../specs/S17-piazza-connector.md), S11 (reference) and [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).

| Repo | Commit / date | License | Size |
|---|---|---|---|
| [Yuanpeng-Li/gradescope-mcp](https://github.com/Yuanpeng-Li/gradescope-mcp) | f8a46c8 · 2026-11-11 | MIT | 80 files / 44k lines |
| [profess/piazza-mcp](https://github.com/profess/piazza-mcp) | 782f62c · 2026-11-05 | MIT | 58 files / 10.9k lines |
| [vishalsachdev/canvas-mcp](https://github.com/vishalsachdev/canvas-mcp) | 5cf81a2 · 2026-11-14 | MIT | 531 files / 153k lines |

**Coverage:** piazza-mcp source read fully (tests/CI/skills not read). gradescope-mcp: auth, server, course/assignment code and docs read; instructor grading modules (~60% of code) reviewed by structure only. canvas-mcp: README, deps, transports, security model, student tool list.

## Findings

**gradescope-mcp**
- Built for **instructors/TAs**: 76 tools (27 write to Gradescope: grading, rubrics, regrades, extensions). Student-useful: `list_courses`, `get_assignments` (student-view parser from the `gradescopeapi` library).
- Results are **markdown tables**, not structured data.
- **Email/password login only; institutional SSO not supported** (stated in its README). UMass students normally use school login.
- One process-wide connection from `.env` → one account per server process; stdio transport.
- Worth reusing: session-expiry detection, timeouts, untrusted-text fencing, timezone-aware date parsing, `gradescopeapi` student-view parsers.

**piazza-mcp**
- **Read-only**: list courses/posts, get post, post history, search; filtered feeds. Clean and small.
- Structured JSON output validated by JSON Schema; normalizer builds `source_url`; course allowlist; error messages never leak post content.
- Email/password login via `piazza-api`; one account per process; stdio.
- Worth reusing: client wrapper, normalizer, models, source-URL builder.

**canvas-mcp**
- Mature (324★, active), FastMCP 4 / MCP SDK 2, **student tool set** (upcoming assignments via Planner API, TODO, grades, announcements, quizzes, calendar, groups).
- Canvas **personal access token** (same as our S11). HTTP mode is **read-only unless `ALLOWED_WRITE_TOOLS`** is set; documented per-user-token deployment.
- Live pulls on every call; up to 128 tools.
- Worth reusing: as reference for S11 endpoints and edge cases (e.g. external-tool/Gradescope assignments wrongly reported missing).

## Catches of running them as-is inside our agent
1. **Breaks sync-first:** live pulls per question; loses search over materials, change detection, merging, verified citations (they need our stored copy).
2. **Passwords:** Gradescope/Piazza need email + password in `.env`, contradicting "never store passwords"; Gradescope can't do UMass SSO at all.
3. **Single-user processes:** one account per server process; doesn't fit a multi-student app.
4. **Tool overload:** dozens of extra tools (mostly instructor writes) degrade tool choice, especially on smaller models.

## Options
| Option | What | Impact on branches |
|---|---|---|
| **A. Borrow pieces (recommended)** | Vendor (with MIT credit) `gradescopeapi` student parsers + gradescope-mcp session/date helpers into S14, using **our saved browser cookies** instead of password login; piazza-mcp client + normalizer into a new **S17 Piazza connector** syncing into `posts`; canvas-mcp as reference for S11 | Only A's connector internals change; normalized records, schema, API and UI unchanged |
| B. A + live extras (post-MVP) | Also connect canvas-mcp read-only with ~5 allowlisted tools (quiz attempts, grades) as live tools for data we don't sync | B adds an MCP connection to the agent; small exception to "agent never touches platforms" (read-only, per-user token) |
| C. Run all three as-is | Agent connects to three MCP servers | New architecture path, password storage, per-user processes; large changes for A and B |

## Tests to run before relying on any of this
- Can a UMass student set a **Gradescope password** ("Forgot password" with the umass.edu email)? Needed only for C.
- Does injecting our saved session cookies into a `gradescopeapi` `GSConnection` let its student parsers fetch courses/assignments? (Option A, S14.)
