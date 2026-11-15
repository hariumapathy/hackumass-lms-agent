# apps/web: the student-facing app (role C)

Next.js 16 (App Router, TypeScript), Tailwind 4, shadcn/ui (Radix), TanStack Query, Supabase Auth, MSW 2 for mock mode.
**Read [`AGENTS.md`](AGENTS.md) first: Next.js 16 differs from older versions.** Specs: S30–S34 in [`docs/specs/`](../../docs/specs/README.md).

_Last verified: 2026-11-14 ~20:20 ET on `main` @ `a081914` (+ the Canvas-guide fix on `dev/soumith`): 70 unit/component tests, 6 Playwright e2e tests, lint, typecheck and `next build` all green; screenshots checked at 1280 px and 375 px._

## Screens (all built; all work in mock mode)
| Route | Screen | Spec | Real backend today? |
|---|---|---|---|
| `/` | Landing + sign-in (Google, email link; "Continue with demo data" in mock mode) | S30 | Supabase sign-in needs env vars (below) |
| `/auth/callback` | Finishes sign-in, sends you to onboarding or Today | S30 | yes |
| `/onboarding` | 5 steps: welcome → paste Canvas code (guided) → Gradescope/Echo360 login → calendar → "getting your classes". `?reconnect=<platform>` jumps to one step | S31 | **UMass login (Gradescope/Echo360) is live** (S13: opens a browser window on the machine running the API); Canvas connect + `/sync/status` still stubs |
| `/today` | Overdue / due today / this week / exams / changes banner / announcements / per-source freshness; Canvas-expiry banner on every signed-in screen | S32, S34 | stub data (`mock_data.py`) |
| `/courses/[id]` | Course: upcoming + past items, posts, materials | S32 | stub data |
| `/chat`, `/chat/[id]` | Streaming answers, tool progress, citation chips + cards, study-set cards, Add/Skip study sessions, Stop, Try again, suggested questions | S33 | **real agent** (Gemini) when the API has a key; scripted stream otherwise |
| `/study`, `/study/[id]` | Study sets: plan (checkboxes), quiz (one question at a time, score), flashcards (flip, keyboard) | S33 | real (in-memory store from the agent run) |
| `/settings` | Accounts (Refresh / Reconnect / Disconnect), profile, calendar buttons + new link, privacy + Delete my data, Advanced → AI choice | S34 | stubs (`/me` doesn't persist yet) |

## Run it

### A. Mock mode (no backend, no keys): the default for UI work and the backup demo
```bash
cd apps/web
pnpm install
echo NEXT_PUBLIC_API_MOCKS=1 > .env.local     # leave the Supabase vars unset
pnpm dev                                     # http://localhost:3000 → "Continue with demo data"
```
MSW (`src/mocks/`) answers every endpoint with a realistic semester (COMPSCI 311/320, MATH 235, STATS 315). Use a normal Chrome/Edge window: embedded browsers that block service workers show "We couldn't start the demo in this browser".

### B. Real backend (what the demo should use once the endpoints are wired)
**Next.js only reads env files from `apps/web/`**: the web values in the repo-root `.env` don't reach the UI. Create `apps/web/.env.local`:
```bash
NEXT_PUBLIC_API_MOCKS=0
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=<project URL>           # hosted: https://eahciwnufpjuzqlxqdni.supabase.co ; local: http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable key>  # Supabase dashboard → Project settings → API (public, but keep it out of git anyway)
```
Then `make api` (repo root; needs Python + `uv`) and `cd apps/web && pnpm dev`.
Checklist (all needed or sign-in/API calls fail):
1. API `.env`: `WEB_ORIGIN=http://localhost:3000` (CORS) and the Supabase JWKS/JWT settings (S20).
2. Supabase dashboard → Authentication → URL configuration: add `http://localhost:3000/auth/callback` (and the deployed URL) to **Redirect URLs**.
3. Supabase → Authentication → Providers: enable **Google** (needs a Google OAuth client) and/or **Email** (magic link). Locally, magic-link emails land in Inbucket (`http://127.0.0.1:54324`).
4. The UI has no password field. The seeded local user (`demo@example.com`) signs in with a magic link via Inbucket.

## Checks (run all before pushing)
```bash
cd apps/web
pnpm test          # Vitest + RTL, uses MSW in Node
pnpm lint
pnpm typecheck     # runs `next typegen` first
pnpm build
pnpm test:e2e      # Playwright; starts its own mock-mode server on :3100. First time: pnpm exec playwright install chromium
```
Test IDs match the specs (`S31-T05` etc.), so `pnpm test -t S33` runs one feature.

## Where things live
| Path | What |
|---|---|
| `src/lib/api/types.ts` | REST types = re-exports of the generated `schema.d.ts` (`make types` after API changes) + hand-written SSE `ChatEvent` union (from `backend/app/api/CONTRACT.md`) |
| `src/lib/api/client.ts`, `sse.ts` | `api()` client (bearer token, S02 error envelope → `ApiError`), SSE parser + `streamChat` |
| `src/lib/auth/` | Supabase backend, demo backend (mock mode only), `AuthProvider`/`useAuth` |
| `src/mocks/` | MSW handlers + fixtures (`handlers.ts`, `handlers-study.ts`, `handlers-account.ts`); `browser.ts` starts once per page |
| `src/components/{layout,today,course,chat,study,connect,settings,states,ui}` | Screens and shared pieces |
| `tests/` | Unit/component tests; `tests/e2e/` Playwright |

## Gotchas (each cost time)
- **Node-20 pins** (team rule): Vitest 3.2, Vite 7, jsdom 26, **MSW 2.15** (3.x needs Node 22), **supabase-js 2.109** (2.110+ needs Node 22).
- **shadcn 4** writes `import { cn } from "cn"` (a Node-22 package). Use `@/lib/utils` (`clsx` + `tailwind-merge`); don't add `cn` to `package.json`.
- **MSW 2** option is `onUnhandledRequest`. `tests/setup.ts` bridges jsdom `AbortSignal`s to Node fetch: keep it.
- **Mock worker starts once per page** (React Strict Mode runs effects twice; two workers = two mock states).
- **react-markdown** config is module-level on purpose (per-render objects remount the DOM on every streamed delta).
- **TanStack v5:** a disabled query reports `isPending`; don't use it alone as "loading".
- **Next 16:** pages using `useSearchParams` need `<Suspense>`; instant-navigation dev checks only run on segments that opt in (`next.config.ts`).
- **Copy rules:** plain language, no "token/sync/API/model" in the main UI (AGENTS.md). Canvas's own button names ("New Access Token") are quoted in the guide on purpose.
