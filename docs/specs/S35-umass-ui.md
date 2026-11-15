# S35 — UMass-inspired student interface and streaming polish

**Status:** Done (Hari, 2026-11-15) on branch `hari/umass-ui`; was: design plan (user requested, 2026-11-14). **Scope:** existing Next.js app; no API/schema changes.

## Design plan
Use a distinctive UMass-inspired visual identity, strong typography and clear hierarchy. Today stays the first screen. Use maroon deliberately against neutral backgrounds, with restrained course accents; verify the current official palette before selecting a hex value. The university updated digital maroon guidance in July 2026. This is a student hackathon project, not an official university service.

Make chat feel intentional: readable answer width, comfortable spacing, clear student/assistant separation, useful suggestions, a composer above the phone keyboard/navigation, compact tool progress, accessible citation cards, and clear study/approval cards. Keep long streamed answers smooth and readable. Avoid decorative clutter and excessive identical boxes.

Responsive targets: 375 px phone, 768 px tablet, 1280+ px laptop. Keyboard navigation, focus, contrast, reduced-motion preferences, and empty/loading/error states are part of the design.

## Implementation plan
1. Review existing CSS tokens, shell, Today, chat, citation and study components and Next 16 local docs.
2. Set shared color, spacing, typography and surface tokens in the existing Tailwind/shadcn system. Rework shell/Today/chat hierarchy before individual decoration.
3. Preserve fetch/SSE interfaces, streaming cancellation, final citation validation and student approval actions. Avoid remounting message content for each text delta.
4. Improve scrolling: follow the stream only when the student is near the end; offer Jump to latest when they scroll up. Keep the composer stable.
5. Review every existing screen at target sizes. Run component/e2e tests, type/lint/build, and browser QA before the S35 commit.

## Test plan
- S35-T01: phone/tablet/laptop layouts have no horizontal overflow; composer stays visible.
- S35-T02: SSE deltas render progressively, Stop works, partial/error states recover.
- S35-T03: scrolling up during a long answer is respected; Jump to latest works.
- S35-T04: keyboard focus and citation/approval controls remain usable.
- S35-T05: seed backup and real-data Today/course/chat routes retain their behavior.

## References and skill research
- [assistant-ui components](https://www.assistant-ui.com/components): streaming message controls, grouped tool progress, follow-scroll and jump-to-latest patterns.
- [Vercel chatbot](https://github.com/vercel/chatbot): modern Next.js/shadcn chat shell and responsive composition.
- [shadcn chat components](https://ui.shadcn.com/docs/ai-elements/aria/chat): accessible chat primitives; reference only unless a dependency change is justified.
- [Anthropic frontend-design skill](https://github.com/anthropics/skills/tree/main/skills/frontend-design): candidate for visual direction, typography and deliberate identity. Located, not installed or copied yet; review source/license before use.
- OpenAI curated catalog checked using skill-installer: Figma/design-system and Playwright/testing skills are available, but there is no curated general frontend-design entry in that snapshot. No new skill installed.
- [UMass digital maroon update](https://www.umass.edu/brand/news/umass-maroon-digital-color-refinement) and [web guidance](https://www.umass.edu/brand/applying-brand/web-digital).

## Acceptance
- [x] Clear UMass-inspired identity; current palette checked
- [x] Responsive and accessible across the target sizes (375 px / laptop checked in the browser; no horizontal overflow)
- [x] Existing SSE, citations and approval behavior retained and tested (78 web tests; live Gemini chat in the browser)
- [x] Screens visually reviewed (sign-in, Today, Chat, Settings, Study; light + dark; phone + laptop)

## Implementation (2026-11-15, Hari's laptop)
**Palette (checked on the UMass brand portal 2026-11-15, after the July 2026 digital-maroon refinement):** Maroon `#840028` (primary: brand bars, primary buttons, active nav, student chat bubbles, focus ring), Black `#212721` (text), neutrals for surfaces (warm off-white `#F7F6F3` background, white cards, Medium Gray `#505759` secondary text), **Yellow `#FFC72C` only as a highlight** (due within 24 h, "CHANGED", the changes banner). Roughly the brand's 65/25/10 primary/neutral/accent split. Dark mode keeps the structure with a lifted maroon `#B8274F` so white text stays readable. Tokens live in `apps/web/src/app/globals.css` (`--umass-*`, `--highlight`; utilities `bg-maroon`, `bg-highlight`, `text-primary`).

**Type:** Fraunces (display serif, headings: h1 and `.font-display`) + Geist (body). Loaded with `next/font/google` (self-hosted at build).

**What changed, by screen:**
- *Sign-in*: split hero (maroon panel with the pitch + 3 value points) and a sign-in card; on phones the hero is compact and the value points are hidden so the email box is above the fold. Footer note: "A student project… Not an official University of Massachusetts service."
- *App frame*: maroon brand block (`BrandMark`: graduation-cap tile + "LMS Agent / for UMass students", deliberately **no UMass logo**), active-page bar in maroon, course list with color dots + upcoming counts; phones get a maroon top bar + bottom tabs with a maroon active indicator.
- *Today*: date eyebrow + serif title, source "pills" with a status dot, changes banner in yellow tint (first 3 shown, **"Show N more"**), deadline cards with a course-color stripe, type icon tile, yellow "in N hours" tag when due within 24 h, red relative time when late; **Due today is listed before Overdue**; a maroon "Not sure where to start? → Ask about your week" call-to-action; course cards with color stripe.
- *Chat*: maroon student bubbles, assistant avatar + readable width (68ch), welcome card with suggestion chips, floating composer card, **follow-scroll only near the end + "Jump to latest"** (S35-T03).
- *Study / Settings / course*: larger serif titles, study cards with a type icon.

**Tests:** `apps/web/tests/s35-ui.test.tsx` (S35-T06 change list folds after 3; S35-T07 Due today before Overdue; S35-T08 landing heading + sign-in + not-official note). S35-T01/T03 verified in the browser (375 px and laptop: no horizontal overflow; Jump to latest appears when scrolled up during an answer). Existing 75 tests unchanged and passing.

**Pitfalls found:** `@theme inline` variables are not emitted as CSS custom properties, so base CSS must use `var(--font-fraunces)` (not `var(--font-display)`). A long-running `next dev` can stop picking up CSS changes after its worker crashes; restart it. Gemini sometimes answers with LaTeX (`$O(1)$`) which the chat doesn't render: the system prompt now asks for plain-text math.

**Not done (ideas):** product name/logo (kept "HackUMass LMS Agent"/"LMS Agent"), illustrations, a dark-mode toggle in Settings (follows the OS today), restyling onboarding steps beyond the theme tokens.

