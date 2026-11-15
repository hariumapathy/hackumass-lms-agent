# Soumith: progress

**Branch:** `dev/soumith` · **Role:** C (frontend and product) · **Last updated:** 2026-11-15 00:30 ET (handoff)

_Only Soumith (or Soumith's agent) edits this file. Keep it short; replace stale lines._

## Done
- **Every MVP screen exists and works in mock mode** (on `main` via PR #14): sign-in (S30), onboarding (S31), Today + course pages (S32), chat + study sets + approvals (S33), Settings + Canvas-expiry banner (S34). Phone (375 px) and desktop checked with screenshots. 70 unit/component + 6 e2e tests, lint, typecheck, build green.
- S02 reviewed (approved); P6–P9 below are follow-ups.
- Frontend runbook: [`apps/web/README.md`](../../apps/web/README.md) (screens, mock vs real mode, real-backend checklist, gotchas).
- ~20:20 sync with `main` @ `a081914` (S01–S03, S10–S14, S16, S20–S24, S26 landed): UI unchanged and green; UMass login endpoints are now live (S13). One fix since: the Canvas guide step rendered one word per line on phones.

- 2026-11-14/15 night: this laptop now runs the full stack (uv, Python 3.12, make, Docker, gh). **S25 calendar verified live** and wording fixed (`codex/calendar-piazza-ui`). On `neal/s17-piazza`: **Connect Piazza** UI, **Echo360 hidden**, calendar branch merged in; all tests green. Soumith approved merging both into main (Neal's review gate).

## In progress
- PRs to open/merge on github.com (agent's `gh` not logged in): calendar first, then Piazza. Links in the newest devlog entry.
- Live Piazza login/import: not run yet (stack was ready; session ended).

## Next (in order)
1. Merge the two PRs (calendar → Piazza), then merge main into `dev/soumith`.
2. Live Piazza check (S17 "UI + verification"); if it fails, hide Piazza again via `CONNECTABLE_PLATFORMS`.
3. Real Canvas on a non-demo account + full 3-minute demo rehearsal (375 px and laptop) incl. calendar Add → Download.
4. S35 UI polish only if time remains before the 08:00 freeze.

## Blocked on / needs from others (what the UI is waiting for)
The UI is done; these make it show **live** data instead of the demo semester:
| # | Need | Who | Why it matters for the demo |
|---|---|---|---|
| 1 | Wire the stub endpoints to the DB, demo order first: `GET /today`, `/courses`, `/courses/{id}` (S32 backend part), `GET /citations`, `GET/PATCH /me` (persist profile + AI choice), `GET /sync/status`, `POST /connections/canvas` → `connect_canvas(...)` (S11), `POST /study-blocks/decision` (persist), calendar feed (S25), `DELETE /me/data` | Hari (B), with Neal's helpers | Today/course/settings show `mock_data.py` until then. **Shapes already match the UI: no frontend change needed.** |
| 2 | Supabase dashboard: add `http://localhost:3000/auth/callback` (+ deployed URL) to Redirect URLs; enable Google provider (OAuth client) or decide "email link only" for the demo | Hari (owns the project) | Real sign-in fails without the redirect URL |
| 3 | Publishable (anon) key + project URL in `apps/web/.env.local` on the **demo laptop** | Hari | Without it the app runs in demo mode |
| 4 | Where the demo runs: laptop `localhost` or a deployed URL (Vercel for web + Railway/Render for API)? Nobody has deployed yet | Team decision | Judges may want a link; deploy needs env vars + CORS `WEB_ORIGIN` |
| 5 | Decide S02 follow-ups P6–P9 and add `details.login_id` to the 409 "login in progress" error | Hari | Small UX gaps only (listed below) |
| 6 | Optional: 3 screenshots of UMass Canvas (Settings → New Access Token) for the onboarding guide | Anyone with Canvas open | Guide is text-only now |

## Contract change proposals
For S02 (Hari to decide; none blocks the demo):
- **P6** `SourceStatus.counts?: {courses, items, materials}`: onboarding's last step shows live counts (now: class count from `/courses`).
- **P7** `Message.blocks: StudyBlock[]` (or "get blocks by id"): reopening a chat can't show whether study sessions were added or skipped.
- **P8** `ModelOption.unavailable_reason?: string`: Settings shows "(not available right now)" without a reason.
- **P9** Generate SSE event payloads + the S24 study-set payload union into OpenAPI (`StudySet.payload` is `{[key]: unknown}`). Seed payloads already carry the `citations` map; the UI handles both shapes.
- **409** on `POST /connections/{p}/login`: include `details.login_id` so the UI can resume the open login (falls back to sessionStorage today).

## Notes for other agents
- **Start with [`apps/web/README.md`](../../apps/web/README.md).** Web env vars live in `apps/web/.env.local`, not the repo-root `.env`.
- Frontend REST types are re-exports of generated `schema.d.ts`: re-run `make types` after any API change; typecheck then shows drift.
- Mock mode (`NEXT_PUBLIC_API_MOCKS=1`, no Supabase vars) is the always-works backup demo. `pnpm test:e2e` runs it on :3100.
- Real auth (S20) means `Bearer anything` → 401: the UI must have a real Supabase session in real mode.
- The UI has no password sign-in; local seed user `demo@example.com` signs in with a magic link (Inbucket).
- Node-20 pins and other gotchas: `apps/web/README.md` § Gotchas.
