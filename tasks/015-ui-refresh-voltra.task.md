# Task 015 - UI Refresh (Voltra Template)

## Scope
- Refresh the demo UI to match the visual style and layout of https://voltra.framer.website.
- Preserve existing functionality (upload, ask, citations, refusals, evidence panel).
- Ensure the UI feels premium, confident, and intentional for client demos.

## Requirements
### Visual Direction
- Use Voltra as the design reference for typography, spacing, and layout rhythm.
- Introduce a bold, high-contrast hero area with branded headline and short tagline.
- Use a structured grid for the chat area and evidence side-panel.
- Add subtle background texture or gradient to avoid a flat feel.
- Replace default UI fonts with a strong display + readable body pairing.

### UX & Content
- Keep all current flows: upload, ask, refusal messaging, evidence support panel, citations.
- Add a “Confidence & Evidence” section that explains:
  - Verified vs Unverified
  - Evidence Strength (A/B/C)
  - Snapshot + index version provenance
- Add a small “System Rigor” strip (invariants + eval gate mention).

### Responsiveness
- Ensure mobile layouts remain clean and readable.
- Evidence panel collapses below chat on small screens.

## Acceptance tests
- UI visually aligns with Voltra’s style direction (typography, spacing, contrast).
- Chat flow remains fully functional.
- Evidence panel and citation cards remain present and readable.
- Refusal styling is preserved or improved for clarity.
- Mobile layout displays hero + chat + evidence without overflow.

## Files likely touched
- `apps/web/app/page.tsx`
- `apps/web/components/*`
- `apps/web/app/globals.css`
- `apps/web/tailwind.config.js`
