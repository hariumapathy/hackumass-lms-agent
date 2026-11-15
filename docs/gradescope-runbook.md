# Gradescope: status and live rehearsal

Verified locally on 2026-11-14. The connector, interactive login, encrypted session storage, queue, import, canonical merge and dashboard are connected. A real student login imported 20 courses and 238 assignments (186 with due dates). Three canonical courses and five deadlines carried both Canvas and Gradescope sources.

## Connect on the demo laptop
1. Keep `make demo-api`, `make demo-worker`, and `make demo-web` running with the local configuration in [demo-runbook.md](demo-runbook.md).
2. Sign in to the student app. Settings → Connect Gradescope opens a separate Chromium window on the machine running the API.
3. In that window, use School Credentials → University of Massachusetts Amherst. The student completes NetID sign-in and Duo themselves. Never paste a password in chat or put one in `.env`.
4. The window closes after login; the app returns to Settings. Connected means the session was saved; wait for the import to finish before judging the data.
5. On Today, verify Gradescope has a fresh timestamp and source chips. Open the relevant course to inspect deadlines. Normal refresh interval is about an hour; Settings → Refresh queues an immediate update.

## Already verified
- Existing Chromium launches from the real app, and the success callback stores an encrypted session and queues the initial import.
- Requests with the saved Gradescope cookies fetched account/course pages successfully; browser-fetch fallback was unnecessary.
- Only student-role courses are imported; no submission/grading/write calls are used.
- UI freshness and Gradescope-only deadlines appeared in the merged Canvas course. Five extracted local due-date values matched their UTC/canonical stored values.
- Focused connector/session suite: 33 passed.

## Remaining checks and limits
- Student should compare five dates with the authenticated Gradescope course pages, including a regular deadline vs any late deadline. This independent source check remains open.
- Historical student courses appear in the sidebar; there is no current-semester filter yet. Same course code in different terms must remain separate.
- Login state is in memory in one API process. Restarting the API during sign-in requires trying again. Saved completed sessions remain encrypted in the database.
- Session expiry prompts Reconnect; it does not prompt the AI for credentials. A long idle-period expiry rehearsal is still useful.
- Local browser login requires the API laptop and Chromium (`cd backend && uv run playwright install chromium` if missing). Hosted interactive login is not implemented.

No additional Gradescope key, password storage, hosted Supabase secret, or schema change is needed for the verified local flow.
