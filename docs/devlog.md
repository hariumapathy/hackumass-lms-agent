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

> **Agents editing this file with scripts:** match the newest dated entry, not the template above (an earlier `sed` inserted into the template by mistake).

---

## 2026-11-14 18:52 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari
**Hour:** ~H22.4 (Devpost draft due 23:59 tonight; final submission Sun 09:00, freeze 08:00)
**Start check:** main = 478380a; no new commits from Neal/Soumith yet; `make test` + `make lint` green; usage window reset.
**Done:**
- Step 0: **Gemini is t**In progress:** nothing half-done.abel, Devpost credits/built-with, pitch, hackathon.md (opt in to MLH Best Use of Gemini API).
- Fixed earlier devlog edits that had landed inside the entry template.
**In progress:** Step 0: apply the **Gemini-default decision** (docs/decisions.md) to S26 `models.yaml` default/tiers, S22 notes, S12 embeddings (Gemini embedding at 1536 dims, else alternative), 03 stack table + diagram label, `.env.example`, settings default, Devpost credits + hackathon.md (MLH Best Use of Gemini API opt-in).
**State of the hosted DB:** Supabase project `hackumass-lms-agent`, ref `eahciwnufpjuzqlxqdni`, us-east-1, free plan, org ParkTheBus (Hari), created 17:30 ET. URL `https://eahciwnufpjuzqlxqdni.supabase.co`; auth uses **JWKS** (`/auth/v1/.well-known/jwks.json`), so S20 needs no JWT secret. Public URL + publishable key are in Hari's `.env`; **service role key, DB connection string, GEMINI_API_KEY are secrets** (Hari fills them in and shares via a password manager, never git/chat). No migrations applied yet (S01).
**Next steps (in order):** 1. Finish step 0. 2. S20 real JWT auth (JWKS). 3. S21 agent tools (needs S01 schema from Neal for DB queries; build against seed fixtures meanwhile).

## 2026-11-14 17:55 ET · Hari's laptop · Claude Code (Opus 5.5) · branch dev/hari · HANDOFF
**Hour:** ~H21.5 (hacking began Fri 20:30 ET). **~6 h to the Devpost draft deadline (Sat 23:59), ~15 h to final submission (Sun 09:00), code freeze 08:00.** (Earlier docs said 18:15/18:40; the real time at this handoff was 17:55.)

**Done (all on `main` after PR #1 merge):**
- Planning docs, specs S00–S34 + new **S17**, AGENTS.md (relay START/HANDOFF protocol, non-technical-student rules, hackathon deliverables, vendoring rule), devlog, `/start` `/handoff` prompts, PR template.
- **S00 scaffolding** (`1695e7b`): backend (FastAPI), apps/web (Next.js 16), supabase/, Makefile, .env.example, CI. CI green.
- **S02 API + SSE contract** (`7c3745d`): typed stubs + mock data for every endpoint, error envelope, SSE framing, scripted `POST /chat` (`?delay_ms=`), `backend/app/api/CONTRACT.md`, `make types` → `apps/web/src/lib/api/`. 27 backend tests.
- Hackathon facts ([hackathon.md](hackathon.md)), pitch kit + Devpost draft ([pitch/](pitch/pitch.md)), category **Best UMass Hack**.
- MCP review → **borrow the pieces** (S14 reworked, S17 added, [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).
- Non-technical-student design: S31 simplified onboarding, S11 token expiry default, S34 model under Advanced, S13 one-UMass-login stretch.

**In progress (not finished):** nothing half-built. S02 awaits Soumith's review (status "In progress"). S00 `make db` untested (Docker Desktop was off).

**Decisions / design changes:** relay protocol with green self-merge; `make` + pinned `npx` tools; Best UMass Hack; non-technical-student rules; Canvas token kept for MVP; MCP pieces borrowed (Option A). All in [decisions.md](decisions.md).

**Roadblocks / waiting on humans:**
- 🚨 **Hari: create the Devpost draft before 23:59 tonight** (text in [pitch/devpost.md](pitch/devpost.md); category Best UMass Hack; add Neal + Soumith; GitHub link).
- **Compressed scope plan still needs Hari's OK** (Echo360 S15 → stretch; minimal S16/S26/S34). Until approved, follow the stage order in specs/README.md but prefer demo-critical work.
- Hosted Supabase + OpenAI key: Hari puts them in `.env` (never in git/chat). Docker Desktop must run for `make db`.
- Specs are still `Draft`: the team should mark Stage 0/1 specs `Ready` quickly (a teammate skim is enough).

**State of main:** PR #1 merged at this handoff (CI green; `make test` + `make lint` green).

**Next steps (in order):**
1. **Neal (A):** S01 schema → S03 seed (mock IDs in `backend/app/api/mock_data.py` match the seed plan) → S10 → S11 → S12.
2. **Hari (B):** S20 real JWT auth → S21 tools → S22 agent runtime → S23 citations (needs S01 for DB-backed tools; use seed).
3. **Soumith (C):** review S02 → S30 shell (MSW handlers + SSE parser moved here) → S32 Today → S33 chat, against `make api` mocks. Follow the non-technical UI rules.
4. Anyone: keep [pitch/pitch.md](pitch/pitch.md) "What actually works" true.

**Gotchas for the next agent:**
- Next.js is **v16**: read `apps/web/AGENTS.md` first. Frontend test tools pinned for **Node 20** (Vitest 3.2, Vite 7, jsdom 26).
- No global pnpm/Supabase CLI: `make` runs pinned versions via `npx`. Re-run `make types` after API changes.
- `current_user` in `backend/app/api/deps.py` is a **stub** until S20 (any `Bearer x` works). Backend needs `tzdata` on Windows. New env var `PUBLIC_API_URL`.
- Two agent sessions shared one checkout earlier; if you run parallel sessions, commit only your own paths.

---

_Earlier entry (superseded by the handoff above):_

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
