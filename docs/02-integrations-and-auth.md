# 02 — Integrations and Auth

## Platform reality check

| Source | Access method | Difficulty | Notes |
|---|---|---|---|
| Canvas | Official REST API (personal access token) or calendar iCal feed; session-based API calls also work | Easy | Verify UMass lets students generate tokens |
| Gradescope | No official API. Session-based scraping | Medium | Unofficial Python libs break with SSO accounts |
| Piazza | Unofficial internal JSON API with session | Medium | |
| Campuswire | Internal GraphQL with session | Medium–Hard | Stretch |
| **Echo360** | Usually launched from inside Canvas (LTI). Session-based | Medium | **In scope.** Transcripts only exist if instructor enabled captions; fallback = audio → Whisper only if downloads allowed |
| Email | Microsoft Graph (UMass is likely Microsoft 365) | Risky | University tenants often **block third-party app consent**. Stretch; seed demo emails |
| Calendar | We publish a private `.ics` feed the student subscribes to | Easy | Avoids OAuth write access + consent issues entirely |
| Spire | Course schedule | Later | Not needed for MVP |

> UMass-specific facts above are best guesses — confirm against our own courses (see [06](06-open-questions.md)).

## The credentials problem
"Take the student's credentials and log in for them" hits three walls:

1. **SSO + Duo MFA** — UMass NetID login goes through Duo; a server can't log in headlessly with a password.
2. **Security / FERPA / ToS** — storing student passwords is the one thing a university will never adopt, and it violates most platforms' terms.
3. **Demo fragility** — live password logins over hackathon wifi fail on stage.

**Rule: we never see or store platform passwords.**

## Connector tiers (current recommendation)

| Tier | Mechanism | Always-on? | Use for |
|---|---|---|---|
| **1. Official** | Canvas personal access token / iCal feed, server-side | Yes, long-lived | Canvas (if tokens allowed) |
| **2. Cloud browser session** | Student logs in once via an embedded *live view* of a server-side browser (Playwright, or a hosted cloud-browser service), approves Duo on their phone; we store the encrypted session cookies; server syncs on a schedule | Yes, until session expires | Gradescope, Echo360, Piazza |
| **3. Browser extension** | Syncs opportunistically while the student browses normally | Only when browsing | Stretch / fallback; later the in-Canvas AI side panel |

### Why tiers 1 + 2 instead of extension-only
With an extension alone, sync only happens while the student's browser is open and logged in. Tiers 1 + 2 let the agent work while the laptop is closed.

### Cloud browser session — caveats
- **Sessions expire.** SSO session + Duo "remember me" have finite lifetimes, so it's "re-login every week or two," not "log in once." UI must show per-source "last synced" and a clean "reconnect" prompt.
- **Session cookies ≈ credentials.** Defensible for a hackathon if encrypted at rest, per-user, scoped, and one-click deletable. For real adoption, this is the part IT would push back on → LTI/developer key path.
- **Data-center IPs** may be flagged by Duo/SSO. **Test early.**
- **Don't let the LLM drive the browser for routine sync.** Use deterministic Playwright scripts; AI-driven browsing only as a "go find this" fallback.

### Demo note
The embedded live-view login with a real Duo push on a phone is a strong demo moment. Always have a seeded backup account in case live auth fails.

## App login
Supabase Auth with **Google sign-in + email magic link**. Avoid "Sign in with Microsoft" for now due to UMass tenant consent risk. Production story: real UMass SSO.
