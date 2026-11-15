# S35 — UMass-inspired student interface and streaming polish

**Status:** Design plan (user requested, 2026-11-14). **Branch:** `codex/calendar-piazza-ui`. **Scope:** existing Next.js app; no API/schema changes.

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
- [ ] Clear UMass-inspired identity; current palette checked
- [ ] Responsive and accessible across the target sizes
- [ ] Existing SSE, citations and approval behavior retained and tested
- [ ] Screens visually reviewed and final feature commit ready for user review
