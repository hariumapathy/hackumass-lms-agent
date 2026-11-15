# Demo runbook: run the whole app on any laptop

Verified on Neal's laptop on 2026-11-14: email-link sign-in → fresh account → real Canvas connection → eight imported courses → Today with actual deadlines → real Gemini answers with syllabus and announcement citations. The production web server avoids compilation on page switches. Everything uses **local** Supabase; the hosted project is not needed.

## Quick start (already set up once? just these)
```bash
make demo-db        # 1. start the local database (+ demo semester). Skip if it's already running and you want to keep data
make demo-api       # 2. terminal 2: API + AI (keep open)
make demo-worker    # 3. terminal 3: imports Canvas/Gradescope/Piazza (keep open)
make demo-web       # 4. terminal 4: website; wait for "Ready", then open http://localhost:3000
```
Sign in with `demo@example.com` → open http://127.0.0.1:54324 → click the link in "Your sign-in link".

## 0. One-time prerequisites (about 10 min, most of it downloads)
| Need | How |
|---|---|
| Git, Git Bash (Windows) or a terminal (Mac/Linux) | already there on dev laptops |
| **Docker Desktop**, running | docker.com → install → start it (whale icon steady) |
| Python tooling `uv` | `pip install uv` or https://docs.astral.sh/uv/ |
| Node 20+ (with `npx`) | nodejs.org |
| `make` | Git Bash on Windows: `winget install GnuWin32.Make` or use the commands inside the Makefile; Mac: Xcode CLT |
| **`.env` in the repo root** | `cp .env.example .env`, then set **`GEMINI_API_KEY=`** (Hari shares it via password manager, never chat/git). Nothing else is required. `ENCRYPTION_KEY` is generated automatically on first run. |

## 1. Get the code
```bash
git clone https://github.com/hariumapathy/hackumass-lms-agent.git && cd hackumass-lms-agent   # or: git pull
git checkout main && git pull
make setup
```

## 2. Database with the demo semester (terminal 1, once)
```bash
make demo-db
```
Starts local Supabase in Docker (first run downloads images), resets it, and seeds the demo student `demo@example.com` (4 courses, 35 deadlines, slides, announcements). Re-run any time to reset the demo.

## 3. Start the three processes (one terminal each, leave them running)
```bash
make demo-api       # terminal 2: API + AI agent on http://localhost:8000
make demo-worker    # terminal 3: sync worker (only needed for "Connect Canvas" with real data)
make demo-web       # terminal 4: website on http://localhost:3000
```
`demo-web` writes `apps/web/.env.local`, builds the app, then serves the production build. Wait for "Ready" before opening it. Use `make web` for development. Node must be 20.9+; on Neal's laptop run `nvm use 26` first (`NODE_OPTIONS=--no-experimental-webstorage` for frontend tests on Node 26).

Google sign-in is hidden locally because its provider is not configured. Email links work. Deployments with Google configured can set `NEXT_PUBLIC_GOOGLE_SIGN_IN_ENABLED=1` in the web environment before building.

## 4. Use it
1. Open **http://localhost:3000**, type `demo@example.com`, click **Email me a link**.
2. Open the local inbox **http://127.0.0.1:54324** (Mailpit), open "Your sign-in link", click it. You land on **Today**.
3. Click **Chat** and ask: "Does my CS 311 midterm cover graphs?", "What's due this week?", "Make me 5 flashcards on dynamic programming for CS 311."

## 5. Real Canvas data (optional)
Keep `make demo-worker` running. Sign in with a **different email from `demo@example.com`** for live data so the seeded backup stays separate. Local email links arrive in Mailpit regardless of the address. In onboarding (or Settings → Connect Canvas), paste a fresh code from [UMass Canvas settings](https://umamherst.instructure.com/profile/settings). The code is checked, stored encrypted, and the worker imports courses. Today and course pages read that student's database rows. Imports refresh open views automatically; normal background Canvas updates run about every 20 minutes, and Refresh queues an immediate update. This is polling, not Canvas Live Events.

The dashboard merge runs ahead of file processing; deadlines can be ready while files continue becoming searchable. Large first imports can take several minutes. Never run `make demo-db` after importing live data unless you intend to reset the entire local database.
For real-quality search on real data, run steps 2–3 with `EMBEDDINGS_PROVIDER=gemini` (e.g. `EMBEDDINGS_PROVIDER=gemini make demo-api`). The demo seed uses fake embeddings, so leave the default for the seed.

## If something goes wrong
| Symptom | Fix |
|---|---|
| "Local Supabase isn't running" | Start Docker Desktop, then `make demo-db` |
| Chat answers with the same canned text every time | `GEMINI_API_KEY` is empty in `.env` (the scripted backup answer is used); add it and restart `make demo-api` |
| Chat error "The AI service had a problem" | Gemini credits/quota (402/429 in the API terminal). Top up in AI Studio, or for a guaranteed demo set `CHAT_MODE=scripted make demo-api` |
| Sign-in link opens but you stay on the sign-in page | Use `http://localhost:3000` (not 127.0.0.1); request a new link |
| Old stack ignores the callback URL | `make db-stop && make db` reloads `supabase/config.toml` without resetting data; restart `make demo-api`, then request a fresh email link |
| Canvas connect returns 404 | Check `.env`: `CANVAS_BASE_URL=https://umamherst.instructure.com`; restart API and worker. `umass.instructure.com` is the wrong host |
| Canvas linked but classes never appear | Keep `make demo-worker` running with the same `.env`/encryption key as the API. An unreadable old credential needs Reconnect |
| Port already in use (8000/3000/54321) | Close the old terminal running it, or `make db-stop` then `make demo-db` |
| Want the frontend with no backend at all | Delete `apps/web/.env.local`, set `NEXT_PUBLIC_API_MOCKS=1`, `make web` |

Stop everything: Ctrl+C in each terminal, then `make db-stop`.

Calendar (S25) works locally: ask the chat to schedule a study session, click **Add**, then Settings → Calendar → **Download calendar** (import into Google Calendar via Settings → Import & export). Google "subscribe" links only appear when `PUBLIC_API_URL` is public HTTPS; see [calendar-runbook.md](calendar-runbook.md). The seeded/MSW backup remains available.

Live rehearsal issues, fixed and outstanding: [live-test-bugs.md](live-test-bugs.md).
