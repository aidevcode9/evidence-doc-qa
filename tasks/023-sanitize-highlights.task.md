# Task 023 - Sanitize highlighted evidence before rendering HTML (XSS fix)

## Summary
The UI renders `citation.highlighted_text` using `dangerouslySetInnerHTML`. Azure highlights are HTML (typically `<em>` tags). This is an XSS risk if any untrusted markup is passed through. We must sanitize or avoid HTML rendering.

## Goals
- Prevent XSS while preserving highlight UX.
- Allow only `<em>` with no attributes, or render highlights as React nodes with no HTML.
- Cap highlight length to avoid UI abuse.

## Scope (recommended)
1. Sanitizer path (client-side)
   - Add a sanitizer helper using `dompurify` or `isomorphic-dompurify`.
   - Allowlist only `<em>`; no attributes.
   - Apply to `citation.highlighted_text` before `dangerouslySetInnerHTML`.
   - Note: if the dependency is not present, add it to `apps/web` and document it.
2. Alternative (no HTML)
   - Parse `<em>` tags and render as React nodes (no `dangerouslySetInnerHTML`).
   - This avoids DOMPurify and is safest if the markup is trivial.
3. Length caps
   - Truncate highlight strings to a safe maximum (e.g., 2000 chars) before rendering.

## Files to change
- `apps/web/components/EvidencePanel.tsx`
- Optional: `apps/web/lib/sanitize.ts` (shared helper)
- Package deps if needed (web app only)

## Acceptance criteria
- `highlighted_text` is sanitized or rendered without HTML.
- Script tags, event handlers, and unexpected tags are stripped.
- Evidence panel still shows emphasis correctly.
- No highlight contents are logged to telemetry.

## Tests
- Unit (frontend):
  - `"<img src=x onerror=alert(1)>"` renders as harmless text.
  - `"<em>match</em>"` preserves emphasis.
- Manual:
  - No console warnings; UI remains responsive.
