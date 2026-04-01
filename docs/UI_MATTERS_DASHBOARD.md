# UI Spec: My Matters Dashboard

**Date:** 2026-03-31
**FR:** FR-UI-001 (new)
**Status:** Implemented on 2026-03-31

This spec shipped on 2026-03-31. The dashboard route, matter detail route,
zero-document matter visibility, inline rename, and per-matter session
storage are now live. The sections below describe the shipped behavior,
with implementation notes added where the final code differed from the
original plan.

---

## Problem

When a user signs in today, they land on the full chat interface (`/`) with a `CasePicker` dropdown in the header. There is no overview of their matters. First-time users see an empty chat with no context. Users with many matters have to click a dropdown to find them.

For a law firm product, the mental model should be: **sign in → see your cases → pick one → work**.

---

## Previous Routing (before 2026-03-31)

```
/login          → Login page
/               → Chat interface (full app, matter selected via header dropdown)
/auth/callback  → OAuth callback
```

Before this change, users landed on `/` immediately after login. The matter
was saved in `localStorage` and auto-restored on next visit. If no matter
was saved, the CasePicker dropdown showed an empty state.

---

## Target Routing

```
/login          → Login page (unchanged)
/               → My Matters dashboard (NEW default landing page)
/matters/[id]   → Chat interface for a specific matter (current "/" behavior moved here)
/auth/callback  → OAuth callback (unchanged)
```

The existing `CasePicker` dropdown in the chat header becomes a "← Back to My Matters" link instead.

---

## Backend API Changes Required

### New field on `GET /v1/matters` response

The existing endpoint returns matter metadata. Add `last_question_at` and `last_question_preview` per matter.

**Current response shape (from `lib/api.ts`):**
```typescript
interface MatterInfo {
  matter_id: string
  display_name: string
  doc_count: number
  last_activity?: string  // exists but may be unused
}
```

**Target response shape:**
```typescript
interface MatterInfo {
  matter_id: string
  display_name: string
  doc_count: number
  last_activity_at: string | null    // ISO timestamp of last doc upload or query
  last_question_at: string | null    // ISO timestamp of most recent user message
  last_question_preview: string | null // First 80 chars of last question, redacted
}
```

**Backend query to add** (`apps/api/app/db.py` or `apps/api/app/routers/matters.py`):

```python
# Per matter: get most recent user qa_message
SELECT
  matter_id,
  MAX(created_at_utc) as last_question_at,
  -- Return content of the most recent user message (truncated, no PII concern since
  -- the user asking is the same user receiving this data)
  (
    SELECT content FROM qa_messages
    WHERE tenant_id = :tenant_id
      AND matter_id = m.matter_id
      AND role = 'user'
    ORDER BY created_at_utc DESC
    LIMIT 1
  ) as last_question_preview
FROM qa_messages m
WHERE tenant_id = :tenant_id
  AND role = 'user'
GROUP BY matter_id
```

This query runs once per `GET /v1/matters` call (not per matter), and only touches `qa_messages` which is already indexed on `tenant_id + matter_id`.

**Truncation:** Return first 80 characters of `last_question_preview` from the backend. Do not expose full question text in the list view.

---

## Frontend Changes

### 1. New page: `apps/web/app/page.tsx` → becomes the dashboard

The current `apps/web/app/page.tsx` (chat interface) moves to `apps/web/app/matters/[id]/page.tsx`.

The new `apps/web/app/page.tsx` is the My Matters dashboard.

### 2. New route: `apps/web/app/matters/[id]/page.tsx`

This is the current chat interface, unchanged except:
- Remove `CasePicker` dropdown from the header
- Replace with `← My Matters` back link + matter display name
- Load `matter_id` from route param instead of localStorage

### 3. New component: `apps/web/components/MattersDashboard.tsx`

The main dashboard component. See layout below.

### 4. Update `apps/web/middleware.ts`

No change needed — middleware protects all non-auth routes, so `/matters/[id]` is automatically protected.

### 5. Update `apps/web/lib/api.ts`

Add `last_question_at` and `last_question_preview` to the `MatterInfo` type.

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                      │
│ [Evidence Bound logo]              [User menu avatar]       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  My Matters                              [+ New Matter]     │
│  ─────────────────────────────────────                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 🗂  Acme Corp v. Baker Industries                   │    │
│  │    12 documents  ·  Last question 2 hours ago       │    │
│  │    "What is the indemnification cap under..."       │    │
│  │                              [Open →]               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 🗂  Henderson Estate Planning                       │    │
│  │    3 documents  ·  Last question yesterday          │    │
│  │    "Does the will include a no-contest clause?"     │    │
│  │                              [Open →]               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 🗂  Regulatory Review Q1 2026                       │    │
│  │    0 documents  ·  No questions yet                 │    │
│  │    Upload documents to get started                  │    │
│  │                              [Open →]               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Empty state (no matters):**
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│              No matters yet                                 │
│   Create your first matter to start reviewing documents     │
│                                                             │
│                  [Create a Matter]                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Spec: `MattersDashboard.tsx`

```typescript
// apps/web/components/MattersDashboard.tsx

interface MatterCardProps {
  matter: MatterInfo
  onClick: () => void
}

// MatterCard renders one row. Clicking anywhere on the card navigates to /matters/[id]
// "Open →" button is the primary CTA but whole card is clickable

// States per card:
// - has docs + has questions: show last question preview
// - has docs + no questions: "Ready — ask your first question"
// - no docs: "Upload documents to get started"

// Sort order for matters list:
// 1. Matters with recent questions first (by last_question_at DESC)
// 2. Matters with docs but no questions (by last_activity_at DESC)
// 3. Empty matters last (by created_at_utc DESC)
```

---

## New Matter Flow

The `[+ New Matter]` button opens an inline modal (not a new page):

```
┌──────────────────────────────┐
│  New Matter                  │
│                              │
│  Matter name                 │
│  ┌────────────────────────┐  │
│  │ e.g. Smith v. Jones    │  │
│  └────────────────────────┘  │
│                              │
│  [Cancel]    [Create Matter] │
└──────────────────────────────┘
```

On confirm: `POST /v1/matters` → navigate to `/matters/[new_id]`.

This replaces the current CasePicker "Create" flow which creates matters inline in the dropdown.

---

## Chat Page Header Change (`/matters/[id]`)

**Current header:**
```
[Evidence Bound logo] [CasePicker dropdown] [Upload] [User menu]
```

**New header:**
```
[← My Matters] [Matter display name]  [Upload] [User menu]
```

- `← My Matters` is a link to `/`
- Matter display name is editable (click to rename, same behavior as current CasePicker rename)
- `CasePicker` component is removed from this page entirely

---

## localStorage Migration

Before the dashboard change, `localStorage` stored `docqa_matter` (last
selected matter ID) and a global `docqa_session` (session ID).

After this change:
- `docqa_matter` is only used as a one-time legacy redirect key, then cleared
- `docqa_session` is stored per tenant and matter as `docqa_session:<tenantId>:<matterId>`
- The legacy global `docqa_session` value is migrated on first matter load
- Keep reading `docqa_matter` on first load as a redirect: if set, redirect to `/matters/[docqa_matter]` then clear the key

---

## Files Created / Modified

| Action | File | What |
|--------|------|------|
| **Create** | `apps/web/app/matters/[id]/page.tsx` | Move current `app/page.tsx` chat logic here |
| **Create** | `apps/web/components/MattersDashboard.tsx` | New dashboard component |
| **Create** | `apps/web/app/api/backend/[...path]/route.ts` | Server-side proxy for authenticated backend calls |
| **Create** | `apps/web/lib/server-auth.ts` | Server auth helper for cookie-backed JWT forwarding |
| **Modify** | `apps/web/app/page.tsx` | Replace chat UI with `<MattersDashboard />` |
| **Modify** | `apps/web/lib/api.ts` | Add matter detail fetch, proxy requests, and per-matter session storage |
| **Modify** | `apps/web/middleware.ts` | Add `/matters/:id*` to protected paths (already covered by default catch-all, verify) |
| **Modify** | `apps/api/app/routers/matters.py` | Add matter detail response and harden create/rename flows |
| **Modify** | `apps/api/app/db.py` | Add zero-doc matter visibility, detail query, creator assignment, and session isolation |

---

## Backend Implementation Detail

### `apps/api/app/db.py` — new helper

```python
def get_matter_last_questions(
    tenant_id: str,
    matter_ids: list[str],
) -> dict[str, dict[str, str | None]]:
    """Return last question timestamp and preview per matter.

    Returns dict keyed by matter_id:
      {
        "matter-abc": {
          "last_question_at": "2026-03-31T14:22:00Z",
          "last_question_preview": "What is the indemnification cap..."
        }
      }
    """
    if not matter_ids:
        return {}

    with session_scope() as session:
        # Subquery: most recent user message per matter
        subq = (
            select(
                QAMessage.matter_id,
                func.max(QAMessage.created_at_utc).label("last_question_at"),
            )
            .where(
                QAMessage.tenant_id == tenant_id,
                QAMessage.matter_id.in_(matter_ids),
                QAMessage.role == "user",
            )
            .group_by(QAMessage.matter_id)
            .subquery()
        )

        # For preview: latest user message content per matter
        preview_subq = (
            select(QAMessage.matter_id, QAMessage.content, QAMessage.created_at_utc)
            .where(
                QAMessage.tenant_id == tenant_id,
                QAMessage.matter_id.in_(matter_ids),
                QAMessage.role == "user",
            )
            .order_by(QAMessage.created_at_utc.desc())
            .subquery()
        )

        results: dict[str, dict[str, str | None]] = {}
        for matter_id in matter_ids:
            results[matter_id] = {
                "last_question_at": None,
                "last_question_preview": None,
            }

        rows = session.execute(
            select(subq.c.matter_id, subq.c.last_question_at)
        ).all()

        previews = session.execute(
            select(
                preview_subq.c.matter_id,
                preview_subq.c.content,
            ).distinct(preview_subq.c.matter_id)
        ).all()

        for row in rows:
            results[row.matter_id]["last_question_at"] = row.last_question_at

        for row in previews:
            if row.content:
                # Truncate to 80 chars - no PII risk (user sees their own questions)
                results[row.matter_id]["last_question_preview"] = row.content[:80]

        return results
```

### `apps/api/app/routers/matters.py` — update list endpoint

```python
@router.get("/v1/matters")
async def list_matters(ctx: TenantContext = Depends(get_tenant_context)):
    matters = list_matters_for_tenant(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        user_role=ctx.user_role,
    )
    matter_ids = [m["matter_id"] for m in matters]
    activity = get_matter_last_questions(ctx.tenant_id, matter_ids)

    for m in matters:
        m_activity = activity.get(m["matter_id"], {})
        m["last_question_at"] = m_activity.get("last_question_at")
        m["last_question_preview"] = m_activity.get("last_question_preview")

    return matters
```

---

## Acceptance Criteria

- [x] Signing in lands on `/` showing all matters the user can access
- [x] Each matter card shows: name, document count, last question time (relative), last question preview (truncated to 80 chars)
- [x] Empty state shown when user has no matters
- [x] Matter card with no docs shows "Upload documents to get started" instead of question preview
- [x] `[+ New Matter]` creates a matter and navigates to `/matters/[id]`
- [x] Clicking a matter card navigates to `/matters/[id]`
- [x] Chat interface at `/matters/[id]` shows a `My Matters` back link
- [x] Back link returns to `/` (dashboard)
- [x] Old `localStorage` matter ID redirects to `/matters/[id]` on first load then clears
- [x] Admin users see all matters in their tenant, not just assigned ones
- [x] Non-admin users see only assigned matters
- [x] `GET /v1/matters` returns `last_question_at` and `last_question_preview` (null if no questions)
- [x] Matter detail route loads the saved display name without slug fallback
- [x] Session storage is isolated per tenant and matter
- [x] All existing tests pass (no regressions)
- [x] New backend coverage exists for zero-doc matters, creator access, and session/export isolation

---

## Implementation Order (TDD)

1. **Backend first:**
   - Write test for `get_matter_last_questions()` with fixtures
   - Implement `get_matter_last_questions()` in `db.py`
   - Write test for updated `GET /v1/matters` response shape
   - Update `matters.py` router

2. **Frontend routing:**
   - Create `apps/web/app/matters/[id]/page.tsx` (copy of current `page.tsx`)
   - Update current `page.tsx` to render `<MattersDashboard />`
   - Verify navigation works (middleware, back link)

3. **Dashboard component:**
   - Build `MattersDashboard.tsx` with static props first
   - Wire to `GET /v1/matters`
   - Add sort logic
   - Add New Matter modal

4. **Cleanup:**
   - Remove `CasePicker` from chat header
   - Add back link to chat header
   - Handle localStorage migration
   - Update `MatterInfo` type in `lib/api.ts`

---

## Not in Scope for This Task

- Matter-level statistics (queries this week, documents reviewed)
- Matter search/filter (add when > 20 matters, not needed for beta)
- Pinning/favoriting matters
- Matter archiving
- Shared matter views between attorneys
