# Calendar verification and deployment

S25 implements private ICS feeds, not direct Google account access. Deadlines and approved study sessions are included; pending/declined sessions are excluded.

## Local laptop
1. Run the existing demo stack; do not reset the database after live imports.
2. Open Settings → Calendar → Download calendar.
3. In Google Calendar on desktop, use Settings → Import & export → Import and select the downloaded ICS file and a test calendar. Check one real due time against its source in the same timezone.
4. In Apple Calendar, import the ICS file into a test calendar and compare the same event. These manual app checks are still pending.
5. A downloaded file is a snapshot: download/import again after changes. Repeated manual imports may duplicate entries depending on the destination app. Prefer a disposable test calendar.

## Automatic subscriptions
Set `PUBLIC_API_URL` to the externally reachable HTTPS API address and restart the API. In Settings, use the appropriate calendar button. Google must be able to fetch that address without a browser session. Calendar providers choose refresh timing, which can take hours. No public hosting is configured by this feature.

The URL grants access to the feed. Keep it private. Rotate it in Settings if shared accidentally; the old link then returns 404 and existing subscribers must use the new one. The application redacts feed secrets from Uvicorn access logs; configure equivalent redaction at any hosting proxy.

## Study-session approval
Ask the assistant to propose a future study session. It should display Add/Skip after the answer. Before Add, the session must be absent from the feed; after Add, download/refresh the feed and verify its time. Skip excludes it. Past times, overlapping sessions, proposals more than 30 days ahead and ambiguous/nonexistent daylight-saving times are rejected. Undecided proposals expire after 24 hours.

## Automated evidence
`backend/tests/integration/test_s25_calendar.py`, `backend/tests/unit/test_s25_blocks.py`, `backend/tests/unit/test_s25_logs.py`, the actual-tool S25 runtime case in `test_s22_runtime.py`, and `apps/web/tests/s25-calendar.test.tsx`. Tests create and clean their own local users and never call Google, Apple or a real model.
