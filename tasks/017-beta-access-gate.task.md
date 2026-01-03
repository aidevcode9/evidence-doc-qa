# Task 017 - Beta Access Gate (Evidence Bound)

## Scope
- Add a login gate that requires **name + email + beta code** before accessing the app.
- Validate beta code on the server (never client-side only).
- Persist a short-lived, HTTP-only session cookie on success.
- Block UI routes until authenticated (middleware or server guard).
- Collect minimal telemetry for demo auditability (name/email + timestamp).
- UI must match current Evidence Bound visual style and typography.
- Email is collected but not verified for the demo.

## Requirements
### UX
- App title: **Evidence Bound** (if no alternate branding is chosen).
- Login page uses the same font, color palette, and layout rhythm as the current UI.
- Fields: Name, Email, Beta Code.
- Clear privacy note: “By continuing you consent to demo telemetry.”
- Error states: invalid code, missing fields.
- After login: redirect to main app.

### Backend
- New endpoint: `POST /v1/auth/beta`
- Server checks beta code against `DOCQA_BETA_CODE` (env var).
- Issue HTTP-only cookie (short TTL).
- Optionally attach a `session_id` to subsequent requests.

### Telemetry / Analytics
- Record login event (name, email, timestamp, session_id).
- Store in `trace_metadata` or a new lightweight table.
- Add `session_id` to ask telemetry rows if present.

### Security
- Rate-limit login endpoint (basic in-memory throttle ok for demo).
- Do not log beta code.
- Do not expose beta code to client bundle.

## Acceptance Tests
- Hitting the UI without a valid session redirects to login.
- Valid beta code creates a session cookie and grants access.
- Invalid beta code returns a clear error and no session.
- Login event is recorded with name/email + timestamp.
- Main app shows title “Evidence Bound” and retains current styling.

## Files likely touched
- `apps/web/app/*`
- `apps/web/components/*`
- `apps/web/middleware.ts`
- `apps/api/app/main.py`
- `apps/api/app/telemetry.py`
- `.env.example`
- `docs/ENVIRONMENT_REFERENCE.md`
