# Development log

The relay baton. **Newest entry first.** Every session adds one entry at its start (header only) and fills it in as it goes; the last thing before a handoff is making sure it's complete. Protocol: [AGENTS.md → Relay sessions](../AGENTS.md#-relay-sessions-start-and-handoff-mandatory).

Keep entries short and factual. Link specs (`S11`), commits (short hash) and PRs. Don't repeat what specs already say; record what *happened*.

## Entry template
```markdown
## <YYYY-MM-DD HH:MM ET> · <person>'s laptop · <tool + model> · branch <dev/name>
**Hour:** H<n> (hacking began Fri Nov 13 20:30 ET; final Devpost submission Sun Nov 15 09:00 ET; code freeze 08:00)
**Done:** S__ (what, commit abc1234, PR #_) ...
**In progress (not finished):** S__: what's left, where the code is
**Decisions / design changes:** one line each (also in docs/decisions.md)
**Roadblocks:** what, what was tried, options
**State of main:** merged up to <hash>? tests green?
**Next steps (in order):** 1. ... 2. ... 3. ...
**Gotchas for the next agent:** ...
```

---

## 2026-11-14 18:15 ET · Hari's laptop · Claude Code (Opus) · branch dev/hari
**Hour:** ~H22 (hacking began Fri Nov 13 20:30 ET; **final Devpost submission Sun 09:00 ET**, code freeze 08:00; judging 12:30)
**Done:**
- Hackathon facts captured in [docs/hackathon.md](hackathon.md); pitch kit + Devpost draft in [docs/pitch/](pitch/pitch.md).
- Planning docs, specs S00–S34 (Draft), AGENTS.md, workflow, branches `dev/hari|neal|soumith`, roles (Neal A, Hari B, Soumith C).
- **S00 scaffolding** (commit 1695e7b, PR #1): `backend/` (FastAPI `/health`), `apps/web/` (Next.js 16), `supabase/`, `Makefile`, `.env.example`, CI. `make test` + `make lint` green locally.
- Reviewed three third-party MCP servers (Gradescope, Piazza, Canvas). Findings: [docs/research/mcp-servers-review.md](research/mcp-servers-review.md).
- Relay protocol + this devlog + start/handoff prompts.
- **S02 API + SSE contract** (commit `7c3745d`, PR #1): typed stubs for every endpoint backed by `backend/app/api/mock_data.py`, error envelope, SSE framing, scripted `POST /chat` stream (`?delay_ms=` for UI work), `backend/app/api/CONTRACT.md`, `make types` → `apps/web/src/lib/api/{openapi.json,schema.d.ts}`. 27 backend tests pass; ruff, pyright, eslint and typecheck clean.

**In progress (not finished):**
- **S02:** needs Soumith's review (spec status still "In progress"). MSW handlers + frontend SSE parser (S02-T05/T06) **moved to S30**. Auth is still the demo stub until S20.

**Decisions / design changes:** relay protocol (green self-merge to `main` at handoff); scaffolding uses `make` + pinned `npx` tools (see S00 notes).

**Roadblocks:**
- 🚨 **Devpost draft must exist by Sat 11:59 PM** (Hari creates it, adds Neal + Soumith; text in docs/pitch/devpost.md). Choose ONE `[HACKUMASS]` category (see hackathon.md).
- **Time:** ~14.5 h to final submission at 18:40. Proposed compressed plan (cut Echo360 S15 to stretch, minimal S16/S26/S34) **awaits Hari's approval**; not yet applied to docs.
- **MCP server approach awaits Hari's decision** (recommended: borrow pieces into our connectors; see research doc).
- Docker Desktop wasn't running on Hari's laptop → `make db` (local Supabase) untested.
- Hosted Supabase project + OpenAI key: Hari will create them and put values in `.env` (never in git or chat).

**State of main:** `a768196` (docs only). PR #1 (`dev/hari` → `main`): roles + S00 (+ S02 when done); CI not yet reported at time of writing.

**Next steps (in order):**
1. Soumith reviews S02; Hari decides on merging PR #1 (roles + S00 + S02) once CI is green.
2. Neal (A): S01 schema + S03 seed, then S10 → S11 → S12.
3. Hari (B): S20 → S21 → S22 → S23.
4. Soumith (C): S30 → S32 → S33 against the S02 mocks/types.

**Gotchas for the next agent:**
- Next.js is **v16**: read `apps/web/AGENTS.md` before frontend code. Frontend test tooling is pinned for **Node 20**.
- No global pnpm/Supabase CLI needed: `make` runs pinned versions via `npx`.
- `current_user` in `backend/app/api/deps.py` is a **stub** until S20: any `Authorization: Bearer x` works.
- Backend depends on `tzdata` (Windows has no IANA timezone database). Re-run `make types` after any API change.
