# Development log

The relay baton. **Newest entry first.** Every session adds one entry at its start (header only) and fills it in as it goes; the last thing before a handoff is making sure it's complete. Protocol: [AGENTS.md → Relay sessions](../AGENTS.md#-relay-sessions-start-and-handoff-mandatory).

Keep entries short and factual. Link specs (`S11`), commits (short hash) and PRs. Don't repeat what specs already say; record what *happened*.

## Entry template
```markdown
## <YYYY-MM-DD HH:MM ET> · <person>'s laptop · <tool + model> · branch <dev/name>
**Hour:** H<n> of 36 (clock started Fri Nov 13 21:30 ET, ends Sun Nov 15 09:30 ET)
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
**Hour:** H20.75 of 36 (clock started Fri Nov 13 21:30 ET, ends Sun Nov 15 09:30 ET)
**Done:**
- Planning docs, specs S00–S34 (Draft), AGENTS.md, workflow, branches `dev/hari|neal|soumith`, roles (Neal A, Hari B, Soumith C).
- **S00 scaffolding** (commit 1695e7b, PR #1): `backend/` (FastAPI `/health`), `apps/web/` (Next.js 16), `supabase/`, `Makefile`, `.env.example`, CI. `make test` + `make lint` green locally.
- Reviewed three third-party MCP servers (Gradescope, Piazza, Canvas). Findings: [docs/research/mcp-servers-review.md](research/mcp-servers-review.md).
- Relay protocol + this devlog + start/handoff prompts.

**In progress (not finished):**
- **S02 API + SSE contract**: being finished by a parallel Claude Code session on `dev/hari` (schemas, SSE framing, error envelope, auth stub, mock data, route stubs; then CONTRACT.md + `make types`). Tests: `backend/tests/unit/test_s02_contract.py`. Check `git log dev/hari` and its devlog/progress notes for where it stopped.

**Decisions / design changes:** relay protocol (green self-merge to `main` at handoff); scaffolding uses `make` + pinned `npx` tools (see S00 notes).

**Roadblocks:**
- **Time:** ~15.5 h left at this entry. Proposed compressed plan (cut Echo360 S15 to stretch, minimal S16/S26/S34) **awaits Hari's approval**; not yet applied to docs.
- **MCP server approach awaits Hari's decision** (recommended: borrow pieces into our connectors; see research doc).
- Docker Desktop wasn't running on Hari's laptop → `make db` (local Supabase) untested.
- Hosted Supabase project + OpenAI key: Hari will create them and put values in `.env` (never in git or chat).

**State of main:** `a768196` (docs only). PR #1 (`dev/hari` → `main`): roles + S00 (+ S02 when done); CI not yet reported at time of writing.

**Next steps (in order):**
1. Finish S02 (if not already), merge PR #1 when green.
2. Neal (A): S01 schema + S03 seed, then S10 → S11 → S12.
3. Hari (B): S20 → S21 → S22 → S23.
4. Soumith (C): S30 → S32 → S33 against the S02 mocks/types.

**Gotchas for the next agent:**
- Next.js is **v16**: read `apps/web/AGENTS.md` before frontend code. Frontend test tooling is pinned for **Node 20**.
- No global pnpm/Supabase CLI needed: `make` runs pinned versions via `npx`.
- `current_user` in `backend/app/api/deps.py` is a **stub** until S20.
