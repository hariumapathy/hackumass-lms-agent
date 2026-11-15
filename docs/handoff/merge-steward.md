# Merge steward

One Claude Code session whose only job is to keep `main` integrated: every 15 minutes it merges each person's green work into `main` and resolves merge conflicts. It never writes features.

## Start it (on a laptop that stays on, with Docker + local Supabase running)
```bash
git worktree add ../hackumass-merge-steward origin/main --detach   # once
cd ../hackumass-merge-steward && cp ../hackumass-lms-agent/.env .env && claude
```
Then type: `/loop 15m Follow docs/handoff/merge-steward.md exactly (one tick).`

## One tick
1. `git fetch --all --prune`, then `./scripts/merge-steward-check.sh`. It prints one line per branch (`dev/hari`, `dev/neal`, `dev/soumith`): ahead/behind main, conflicts yes/no, open PR, CI state, head commit. **If no branch is ahead of `main`, stop: nothing to do this tick.**
2. For each branch that is ahead, in this order: `dev/neal` (data contracts first), `dev/hari`, `dev/soumith`.
   - **Skip it** if its head commit message contains `WIP` or `broken`, or if it is the owner's open PR with failing CI that the owner hasn't touched for < 15 min (they're fixing it).
   - **No conflicts:** if there's no open PR from that branch, open one (`gh pr create --base main --head dev/<name> --title "<name>: integrate (merge steward)" --body "<commit list>"`). Wait for CI. When CI passes, run the local checks (step 3) on the PR head, then `gh pr merge <n> --merge`.
   - **Conflicts:** `git checkout -B merge/<name> origin/dev/<name>`, `git merge origin/main`, resolve (rules below), run step 3, `git push -u origin merge/<name>` (normal push; force-push only this steward-owned branch if it already exists), open/update a PR `merge/<name>` → `main`, wait for CI, merge when green. Never push to `dev/<name>`; the owner picks up `main` on their next sync.
3. **Local checks before every merge:** `cd backend && uv sync && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright`; `cd apps/web && npx -y pnpm@10.34.9 install --frozen-lockfile && npx -y pnpm@10.34.9 lint && npx -y pnpm@10.34.9 typecheck && npx -y pnpm@10.34.9 test`. Web tests on Node 26: prefix with `NODE_OPTIONS=--no-experimental-webstorage` (Node 26's built-in localStorage breaks jsdom; CI uses Node 20). If the branch adds a migration, apply it to the local DB with `npx -y supabase@3.1.0 migration up` (never `db reset` while others use the DB). Anything red → don't merge; comment on the PR with the failing output (short) and move on.
4. After merging, append one line to the "Merged to main" list in `docs/progress/README.md` **only via the next merge PR** (don't push to main directly).
5. Finish the tick with a 3-line summary: merged, waiting (why), blocked (why).

## Conflict resolution rules
- `docs/devlog.md`: keep **both** entries, newest first; drop exact duplicates.
- `docs/progress/<name>.md`: take the owner's version (each person edits only their own file).
- `docs/specs/README.md`, `docs/pitch/*.md`, `THIRD_PARTY_NOTICES.md`: keep both sides' rows; for one row edited on both sides, keep the newer status (Done > In progress > Draft).
- `backend/uv.lock`: take `main`'s, then `uv lock` (after resolving `pyproject.toml` as the union of dependencies). `apps/web/pnpm-lock.yaml`: take `main`'s, then `pnpm install`.
- `apps/web/src/lib/api/schema.d.ts` / `openapi.json`: regenerate with `make types`.
- **Code:** keep both intents when they're independent (e.g. two new routes, two new imports). If both sides changed the same logic and the right merge isn't obvious, **don't guess**: abort that branch, comment on the PR (`@owner: conflict in <file>: <one line>`), and move on.
- Contracts (`supabase/migrations/`, `backend/app/api/schemas.py`, `backend/app/api/CONTRACT.md`, `supabase/seed/`): never invent changes; only combine additive edits. Two migrations with the same number → stop and comment.

## Never
Force-push any `dev/*` branch or `main`; push directly to `main`; edit feature code beyond conflict resolution; merge red CI or red local checks; merge a branch whose head says WIP/broken; delete anyone's branch; touch `.env`.
