# S34 — Settings

| | |
|---|---|
| **Status** | Draft |
| **Stage** | 3 |
| **Role** | C |
| **Depends on** | S30, S26 (models), S25 (calendar), S20 (`/me`, `/me/data`) |
| **Folders** | `apps/web/src/app/settings/` |

## Purpose
One place to manage connections, model choice, timezone, the calendar feed, and privacy (delete my data).

## Inputs / outputs
| Section | Shows | Actions → API |
|---|---|---|
| **Connections** | Each platform: status (active / needs reconnect / error / not connected), last sync, Canvas token expiry ("expires in 12 days") | Reconnect → `/onboarding?reconnect=<p>` · Disconnect → `DELETE /connections/{p}` (confirm dialog) · Sync now → `POST /sync {platform}` |
| **Advanced → AI model** (collapsed by default) | Options from `GET /models`, grouped Recommended / Experimental; unavailable ones disabled with reason; the default is pre-selected and labelled "Recommended" | Select → `PATCH /me {model_choice}` |
| **Profile** | Display name, timezone (default from browser) | `PATCH /me` |
| **Calendar** | Feed URL (masked), copy button, "Add to Google Calendar" helper, refresh-delay note | Rotate → `POST /calendar/feed/rotate` (confirm: "old link stops working") |
| **Privacy** | What we store, what we never store (passwords), model provider note | **Delete my data** → `DELETE /me/data` (type "DELETE" to confirm) → signed out, landing page |

## Behavior and rules
1. Canvas token expiry: warning banner across the app when < 10 days (also on Today).
2. Experimental models show a note: "May skip tools or make mistakes."
3. All destructive actions use a confirm dialog naming exactly what happens.
4. Saving shows inline success; errors use S02 messages.

## Acceptance criteria
- [ ] Every action works against the real API
- [ ] Model change affects the next chat (verified with S26)
- [ ] Delete my data leaves the account empty and signs out

## Test plan
| ID | Test | Type |
|---|---|---|
| S34-T01 | Connection statuses render; Reconnect link targets onboarding | component |
| S34-T02 | Disconnect requires confirmation and calls API | component |
| S34-T03 | Model list grouped by tier; unavailable disabled | component |
| S34-T04 | Rotate feed confirms and shows the new URL | component |
| S34-T05 | Delete my data requires typing DELETE, then signs out | component |
| S34-T06 | Token-expiry banner appears under 10 days | component |

## Out of scope
Notification preferences, theme customization beyond light/dark, multiple accounts.
