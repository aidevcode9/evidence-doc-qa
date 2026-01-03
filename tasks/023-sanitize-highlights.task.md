# Task 023 — Sanitize highlighted evidence before rendering HTML (XSS fix)

## Summary
UI renders `citation.highlighted_text` using `dangerouslySetInnerHTML`. Highlight strings come from Azure Search captions/highlights and are treated as HTML (typically <em> tags). This is an XSS risk if any untrusted HTML leaks through.

**Current code**
- `EvidencePanel.tsx`: `dangerouslySetInnerHTML={{ __html: ... }}` (appears multiple times, e.g. ~line 182)

## Goals
- Prevent XSS while preserving highlight UX.
- Only allow a strict subset of markup (ideally `<em>` only, no attributes).

## Scope (recommended)
1. Add a sanitizer helper (client-side):
   - Use `dompurify` with allowlist: `ALLOWED_TAGS: ['em']`, `ALLOWED_ATTR: []`
   - Apply to `citation.highlighted_text` before passing to `dangerouslySetInnerHTML`.
2. Alternatively (even safer), remove HTML rendering entirely:
   - Convert highlight markup to spans (parse `<em>...</em>` segments) and render as React nodes.
3. Add length caps:
   - truncate highlights to a safe max length (e.g., 2k chars) to avoid UI abuse.

## Files to change
- `EvidencePanel.tsx`
- (optional) shared UI util: `lib/sanitize.ts`

## Acceptance criteria
- `highlighted_text` is sanitized before rendering.
- Script tags, event handlers, and unexpected tags are stripped.
- Evidence panel still displays emphasis correctly.

## Tests
- Unit (frontend):
  - Pass `highlighted_text="<img src=x onerror=alert(1)>"` → renders harmless text
  - Pass `<em>match</em>` → emphasis preserved
- Manual:
  - Confirm no console warnings; UI remains responsive.

## Telemetry / analytics
- Track counts:
  - `highlight_used: bool`
  - `highlight_sanitized_len`
  - number of citations with highlights
