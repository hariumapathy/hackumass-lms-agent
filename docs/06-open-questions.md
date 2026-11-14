# 06 — Open Questions

Add your own below. Move answered ones into [decisions.md](decisions.md).

## Decisions needed
- [ ] **Platforms:** which do our actual courses use? Canvas / Gradescope / Piazza / Campuswire / Echo360 / other? Is student email Outlook (Microsoft 365)?
- [ ] **Stack:** all TypeScript (Next.js + AI SDK + Supabase), or a Python backend (FastAPI + LangGraph/Pydantic AI)? What are we each strongest in?
- [ ] **Connector strategy:** agree on Canvas token + cloud browser session, extension as stretch? (Explained in [02](02-integrations-and-auth.md#connector-strategy).)
- [ ] **App login:** Google + email magic link via Supabase?
- [ ] **Roles:** who takes data/connectors vs. app/UI/agent?
- [ ] **Hackathon timing + prize tracks:** any sponsor tracks (model providers, MLH categories) to design toward?
- [ ] **Product name.**

## Test early (≤15 min each, before committing)
- [x] Can a student generate a **Canvas personal access token** in UMass Canvas settings? → **Yes, max expiry 90 days** (2026-11-14)
- [ ] Does a student token let us open **Echo360 via Canvas's launch-link API** (`sessionless_launch`)? If yes, Echo360 needs no separate login or Duo.
- [ ] Does logging into UMass SSO + Duo from a **cloud / data-center browser** get flagged or blocked?
- [ ] How long do **Gradescope / Piazza / Echo360 sessions** last before re-login? Does regular syncing keep them alive?
- [ ] Do **Echo360 transcripts** exist for our courses? Are downloads allowed?
- [ ] Does Canvas file **`updated_at`** change when a professor replaces a slide deck? (Decides timestamp vs. content-hash change detection.)
- [ ] Do UMass students get **"Need admin approval"** when connecting a Microsoft (Graph) mail app? (Decides whether email option A is feasible.)
- [ ] Is **automatic external forwarding** blocked on UMass Outlook? (Decides email option B.)

## Teammate ideas
_Neal — add yours here._
