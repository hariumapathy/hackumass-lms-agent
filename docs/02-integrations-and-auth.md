# 02 — Integrations and Auth

## Platform reality check

| Source | Access method | Difficulty | Notes |
|---|---|---|---|
| Canvas | **Personal access token** → official REST API | Easy | ✅ **Confirmed:** UMass students can generate tokens; **max expiry 90 days** |
| Gradescope | No student API → cloud browser session | Medium | Unofficial Python libs break with SSO accounts |
| Piazza | No public API → cloud browser session | Medium | |
| Campuswire | Internal GraphQL → cloud browser session | Medium–Hard | Stretch |
| **Echo360** | Usually launched from inside Canvas (LTI) → maybe via Canvas token, else cloud browser | Medium | **In scope.** Transcripts only exist if instructor enabled captions; fallback = audio → Whisper only if downloads allowed |
| Email | See [Email](#email) below | Risky | UMass is likely Microsoft 365; tenant may block third-party apps |
| Calendar | We publish a private `.ics` feed the student subscribes to | Easy | No OAuth write access or consent issues |
| Spire | Course schedule | Later | Not needed for MVP |

## The credentials problem
"Take the student's credentials and log in for them" hits three walls:

1. **SSO + Duo MFA**: UMass NetID login requires a Duo approval on the student's phone for every new login.
2. **Security / FERPA / ToS**: storing student passwords is the one thing a university will never adopt.
3. **Demo fragility**: live password logins over hackathon wifi fail on stage.

**Rule: we never see or store platform passwords.**

### "What if the student gives credentials and the agent logs in?"
- A password alone isn't enough. **Duo still asks for a phone approval** on every new login, so the agent would still wait on the student's phone. Storing passwords saves the student no effort.
- Fully automating it would mean getting around Duo (storing Duo codes or registering a fake "phone"). We won't do that:
  - It deliberately defeats UMass's two-factor login and likely violates UMass IT's acceptable-use policy (which generally forbids sharing NetID credentials).
  - A NetID password unlocks the whole university account: email, Spire, financial aid, payroll. A breach of our database would expose all of it for every user.
  - It sinks the pitch: "you store students' NetID passwords?" kills adoption.
- Some platforms have their *own* password separate from UMass login (e.g. some students have a Gradescope password). We technically could store that, but we keep the "no passwords stored" rule because it's central to the trust story.

**Pitch line:** *"About a minute of setup, a 30-second reconnect every few weeks, and we never hold your password."*

## Connector strategy

**Rule of thumb:** use the official API when there is one, the cloud browser only when there isn't, and treat the browser extension as a stretch goal.

| Platform | Method | Why |
|---|---|---|
| Canvas | **Token** | Official API exists |
| Gradescope | Cloud browser | No student API |
| Piazza | Cloud browser | No public API |
| Echo360 | Canvas launch link if possible, else cloud browser | Opens from inside Canvas; see test below |
| Email | Separate path | See [Email](#email) |
| (stretch) any | Browser extension | Syncs only while the student browses; later an AI side panel inside Canvas |

### Method 1: Canvas token
**What it is:** a key Canvas issues to the student. Whoever holds it can call Canvas's official API as that student and get structured data (courses, assignments, files, announcements, calendar).

**Student experience (about a minute, once every 90 days):**
1. In onboarding, click **Connect Canvas**. It opens Canvas → Account → Settings in a new tab with a short visual guide.
2. Click **+ New Access Token**, name it after our app, set the expiry as far out as allowed (90 days), copy it.
3. Paste it into our app. We immediately fetch their courses: "Connected: 5 courses found."
4. Around day 80: banner + email "Your Canvas connection expires in 10 days, renew in one click." Same steps, ~30 seconds.

**Implementation:**
- Validate on paste (`GET /api/v1/users/self`), store encrypted, record the expiry date.
- Background job every 15–30 min per student: courses, assignments, announcements, files, calendar/planner items. Handle pagination (`Link` header) and rate limits.
- No browser, no login screens.
- **Read-only enforcement:** a student token can do *anything* the student can, including submitting assignments, and students can't limit its scope. Our Canvas client only allows GET requests, and the onboarding screen says so.

### Method 2: Cloud browser session
**What it is:** a real Chrome browser running on our server with no screen, controlled by code (Playwright). When you log in to a site, it gives your browser a **session cookie**, a pass that says "this browser is logged in as you." The student logs in once inside *our* browser; we keep the cookie so our code can visit pages as them later.

**Student experience (about a minute per platform):**
1. Click **Connect Gradescope**. A window in our app shows a *live view* of the server's browser on Gradescope's login page.
2. Log in as usual: school login → UMass NetID → password → **Duo push on phone**.
3. When login succeeds, the window closes: "Gradescope connected, 4 courses."
4. Syncs in the background from then on, even with the laptop closed.

**Implementation:**
- Live view streams the server browser's screen into our page and passes clicks/typing back. Hosted cloud-browser services offer an embeddable live view; or build with Playwright.
- After login, save the browser's cookies (Playwright storage state), encrypted, per student.
- Each sync: load cookies into a fresh browser, visit known pages (Gradescope course/assignment pages, Echo360 lecture lists), parse with **fixed scripts** (no AI clicking around), save data.
- If a page redirects to a login screen → session expired → mark the source **Needs reconnect** and notify the student.

**Honesty note:** the student types their password into a browser *we* run. We don't record it, but it does pass through our server. This is a hackathon tool; the university-grade version is an official Canvas integration (LTI 1.3 + developer key) approved by UMass IT.

### Session expiry (why it matters)
Sessions **do** time out. Two layers:
- **The site's own session** (Gradescope, Piazza): often days to weeks. Regular syncing counts as activity and may keep it alive longer.
- **The UMass login** (NetID + Duo): usually much shorter, but only matters when the site's session runs out and we need to log in again.

When it runs out, re-login needs a Duo approval from the student, so a source can silently go stale. Durations are unknown → on the test list. Mitigations:
- "Last synced" time per source.
- Clear "Reconnect Gradescope (30 sec)" notification.
- Dashboard flags items from a stale source ("may be out of date").

Other caveats:
- **Session cookies ≈ credentials**: encrypted at rest, per user, one-click delete.
- **Data-center IPs** may be flagged by Duo/SSO. Test early.

### Demo note
The embedded live-view login with a real Duo push is a strong demo moment. Always keep a seeded backup account in case live auth fails.

## Email
UMass student email is most likely Microsoft 365 (Outlook).

| Option | Student experience | Under the hood | Risk |
|---|---|---|---|
| **A. Sign in with Microsoft** | Click **Connect Outlook** → UMass login + Duo → "this app wants to read your mail" → Accept | Free app registered with Microsoft; renewable read-only mail access (Microsoft Graph); fetch only course-related mail (sender + course-code filters) | **UMass may require IT approval** → students see "Need admin approval." Test (~15 min) |
| **B. Auto-forwarding rule** | One-time Outlook rule forwarding course emails to a personal address we give them | Inbound email service receives it and passes it to our server for parsing | Microsoft 365 **blocks automatic forwarding to outside addresses by default**; probably blocked at UMass |
| **C. Manual forward** | Forward an important email to your personal app address | Same as B | Always works, but takes effort |
| **D. Gmail** | For students already forwarding UMass mail to Gmail: Sign in with Google | Gmail API; test mode fine for <100 users | Only covers some students |

**Context:** most course emails are copies of Canvas announcements, which we already get via the token. Email mostly adds professor-sent messages, so it's a nice extra, not core.

**Plan:** test A early → if it works, strong feature. If not, demo with C + seeded emails and pitch A as "one IT approval away."

## App login
Supabase Auth with **Google sign-in + email magic link**. Avoid "Sign in with Microsoft" *for app login* for now due to UMass tenant consent risk (separate from the optional Outlook connector above). Production story: real UMass SSO.
