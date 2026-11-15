# Demo runbook: run the whole app on any laptop

Tested end to end on Hari's laptop (Windows, Git Bash) on 2026-11-14 ~20:45 ET: sign in by email link → Today view → chat answer from real Gemini with citation chips. Everything runs locally against the **local** Supabase stack; the hosted project is never touched.

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
`demo-web` writes `apps/web/.env.local` for the local stack (delete that file to go back to the frontend's mock mode).

## 4. Use it
1. Open **http://localhost:3000**, type `demo@example.com`, click **Email me a link**.
2. Open the local inbox **http://127.0.0.1:54324** (Mailpit), open "Your sign-in link", click it. You land on **Today**.
3. Click **Chat** and ask: "Does my CS 311 midterm cover graphs?", "What's due this week?", "Make me 5 flashcards on dynamic programming for CS 311."

## 5. Real Canvas data (optional)
Keep `make demo-worker` running. In the app's Connect Canvas step (Settings / onboarding), paste a **fresh** Canvas token (Canvas → Account → Settings → **+ New Access Token**). The token is checked with Canvas, stored encrypted, and the worker pulls your courses; then ask the chat. Delete the token in Canvas after the event.
For real-quality search on real data, run steps 2–3 with `EMBEDDINGS_PROVIDER=gemini` (e.g. `EMBEDDINGS_PROVIDER=gemini make demo-api`). The demo seed uses fake embeddings, so leave the default for the seed.

## If something goes wrong
| Symptom | Fix |
|---|---|
| "Local Supabase isn't running" | Start Docker Desktop, then `make demo-db` |
| Chat answers with the same canned text every time | `GEMINI_API_KEY` is empty in `.env` (the scripted backup answer is used); add it and restart `make demo-api` |
| Chat error "The AI service had a problem" | Gemini credits/quota (402/429 in the API terminal). Top up in AI Studio, or for a guaranteed demo set `CHAT_MODE=scripted make demo-api` |
| Sign-in link opens but you stay on the sign-in page | Use `http://localhost:3000` (not 127.0.0.1); request a new link |
| Port already in use (8000/3000/54321) | Close the old terminal running it, or `make db-stop` then `make demo-db` |
| Want the frontend with no backend at all | Delete `apps/web/.env.local`, set `NEXT_PUBLIC_API_MOCKS=1`, `make web` |

Stop everything: Ctrl+C in each terminal, then `make db-stop`.
