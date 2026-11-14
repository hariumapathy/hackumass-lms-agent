# 06 — Open Questions

Add your own below. Move answered ones into [decisions.md](decisions.md).

## Decisions needed
- [ ] **Platforms:** which do our actual courses use? Canvas / Gradescope / Piazza / Campuswire / Echo360 / other? Is student email Outlook (Microsoft 365)?
- [ ] **Stack:** all TypeScript (Next.js + AI SDK + Supabase), or a Python backend (FastAPI + LangGraph/Pydantic AI)? What are we each strongest in?
- [ ] **Connector strategy:** agree on tiers 1 (Canvas token) + 2 (cloud browser session), extension as stretch?
- [ ] **App login:** Google + email magic link via Supabase?
- [ ] **Roles:** who takes data/connectors vs. app/UI/agent?
- [ ] **Hackathon timing + prize tracks:** any sponsor tracks (model providers, MLH categories) to design toward?
- [ ] **Product name.**

## Test early (≤15 min each, before committing)
- [ ] Can a student generate a **Canvas personal access token** in UMass Canvas settings?
- [ ] Does logging into UMass SSO + Duo from a **cloud / data-center browser** get flagged or blocked?
- [ ] How long do the **SSO / Gradescope / Echo360 sessions** last before re-login?
- [ ] Do **Echo360 transcripts** exist for our courses? Are downloads allowed?
- [ ] Does Canvas file **`updated_at`** change when a professor replaces a slide deck? (Decides timestamp vs. content-hash change detection.)
- [ ] Can a student account consent to a **Microsoft Graph** app in the UMass tenant? (Decides whether email is feasible.)

## Teammate ideas
_Neal — add yours here._
