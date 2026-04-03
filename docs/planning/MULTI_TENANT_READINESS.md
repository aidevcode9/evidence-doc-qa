# Multi-Tenant SaaS Readiness Assessment

**Date:** 2026-03-31
**Target:** Sell Evidence-Bound to law firms as a multi-tenant SaaS product
**Current State:** Single-tenant demo with multi-tenant data model

---

## Readiness Score: 35/100

The data model is multi-tenant. The runtime is not.

---

## What's Ready

### Data Layer (90% ready)
- `tenant_id` on every table with indexes
- `matter_id` scoping on all document and query tables
- `MatterAssignment` table for per-matter user access
- Azure Search filters enforce `tenant_id eq 'X' and matter_id eq 'Y'` on every query
- No cross-tenant join paths in the schema
- Retention policies configurable per tenant

### Auth Layer (80% ready)
- JWT with tenant claims
- Google SSO with tenant routing
- RBAC with 4 roles (admin, attorney, paralegal, viewer)
- Account lockout, password hashing (Argon2id)
- Refresh token rotation with tenant isolation

### API Layer (70% ready)
- `get_request_context()` dependency extracts tenant from JWT/headers on every endpoint
- `user_has_matter_access()` validates matter-level permissions
- Rate limiting per endpoint (but not per tenant)
- Input validation prevents filter injection in Azure Search queries

---

## What's Not Ready

### 1. Tenant Provisioning (0% implemented)

There is no way to create a new tenant. No endpoint, no admin tool, no migration script. The data model supports tenants but there's no onboarding flow.

**What's needed:**
- `POST /admin/tenants` -- Create tenant with initial admin user
- Tenant configuration storage (custom retention policies, feature flags, branding)
- Azure Search index management per tenant (or shared index with tenant filters -- current approach)
- Storage isolation (Azure Blob containers per tenant, or prefix-based isolation)
- DNS/subdomain routing (optional: `firmname.evidence-bound.com`)

**Estimated effort:** 2-3 weeks

### 2. Per-Tenant Resource Limits (0% implemented)

Current rate limiting is per-endpoint, not per-tenant. One tenant doing heavy queries can starve others.

**What's needed:**
- Per-tenant query quotas (e.g., 1000 queries/day for Starter tier)
- Per-tenant storage limits (e.g., 10GB for Starter, 100GB for Professional)
- Per-tenant concurrent request limits
- Per-tenant LLM token budgets (prevent one tenant from exhausting Azure OpenAI TPM)
- Usage tracking and billing integration

**Estimated effort:** 3-4 weeks

### 3. Tenant-Aware Scaling (0% implemented)

The current architecture runs one process, one database, one Azure Search index for everything. For multi-tenant:

| Component | Current | Multi-Tenant Requirement |
|-----------|---------|--------------------------|
| Database | Single Postgres | Shared DB, tenant-filtered queries (already done) |
| Azure Search | Single index | Shared index with tenant filters (already done) |
| Azure OpenAI | Single deployment | Need TPM allocation per tenant |
| Blob Storage | Single container | Per-tenant container or prefixes |
| API Servers | Single process | Horizontal scaling with shared state (Redis) |
| Caches | In-memory | Redis (tenant-scoped keys) |
| Background Jobs | None | Queue per tenant with priority |

**Estimated effort:** 6-8 weeks

### 4. Tenant Data Isolation Testing (0% implemented)

There are no tests that verify cross-tenant isolation under adversarial conditions:
- What happens if a user sends `tenant_id=other-firm` in headers? (Should be blocked by JWT, but header mode doesn't validate)
- What happens if Azure Search filter injection bypasses tenant isolation? (Input validation exists, but no fuzzing tests)
- What happens if a DB query accidentally omits `tenant_id`? (No lint rule, no static analysis)

**What's needed:**
- Integration tests that create 2 tenants and verify zero data leakage
- Fuzzing tests for Azure Search filter injection
- Static analysis rule: any query on a tenant-scoped table MUST include `tenant_id` in the WHERE clause
- Penetration testing by a third party (required for law firm compliance)

**Estimated effort:** 2-3 weeks

### 5. Compliance and Legal Requirements (10% implemented)

Law firms have specific compliance requirements that aren't covered:

| Requirement | Status | Notes |
|-------------|--------|-------|
| SOC 2 Type II | Not started | Required by most firms with >20 attorneys |
| Data residency | Not implemented | Some firms require data in specific Azure regions |
| Encryption at rest | Azure default | Need customer-managed keys (BYOK) for enterprise |
| Encryption in transit | TLS (infrastructure) | Need to verify no plaintext internal traffic |
| Data deletion | Implemented (FR-043) | Need to verify complete deletion including backups |
| Audit log export | Implemented (FR-041) | Need SOC 2 format compatibility |
| Uptime SLA | No monitoring | Need 99.9% SLA with Azure Monitor alerting |
| Incident response | No runbook | Need documented IR process |
| Backup/restore | Not tested | Need documented RTO/RPO with tested restore |

**Estimated effort:** 8-12 weeks (SOC 2 alone is a multi-month project)

### 6. Billing and Metering (0% implemented)

No usage tracking for billing purposes:
- No query count per tenant
- No storage usage per tenant
- No LLM token usage per tenant
- No cost allocation per tenant
- No billing integration (Stripe, etc.)

**Estimated effort:** 4-6 weeks

---

## The "Headers Mode" Problem

The biggest immediate risk for multi-tenant: `AUTH_MODE=headers` (the default) trusts whatever the client sends.

```python
# context.py - headers mode
X-Tenant-Id: whatever-the-client-says    # Trusted!
X-User-Id: whatever-the-client-says      # Trusted!
X-User-Role: admin                       # Trusted!
```

In headers mode, any client can claim to be any tenant, any user, any role. This is fine for demos. It's a critical vulnerability for multi-tenant.

**The fix is already built** -- `AUTH_MODE=jwt` validates tenant claims from the JWT, which is signed by the server. But:
- `AUTH_MODE` defaults to `headers` (`config.py:133`)
- `AUTH_BYPASS_ENABLED` defaults to `"1"` (`config.py:137`)
- `JWT_SECRET_KEY` defaults to `"dev-secret-key-change-in-production"` (`config.py:139`)

**Before any multi-tenant deployment:**
```bash
AUTH_MODE=jwt
AUTH_BYPASS_ENABLED=0
JWT_SECRET_KEY=<cryptographically-random-256-bit-key>
```

These three env vars are the difference between "secure multi-tenant product" and "anyone can read anyone's legal documents."

---

## Tenant Onboarding Checklist (What to Build)

### Minimum Viable Tenant Onboarding

```
1. Admin creates tenant via CLI/admin API
   → INSERT INTO tenants (tenant_id, name, plan, created_at)
   → Create Azure Blob container (or prefix) for document storage
   → No Azure Search index creation needed (shared index with tenant filter)

2. Admin creates first user (tenant admin)
   → INSERT INTO users (user_id, tenant_id, email, role='admin', ...)
   → Send invite email with password reset link

3. Tenant admin signs in
   → Creates first matter
   → Uploads first documents
   → Assigns team members to matters

4. Team members sign in (SSO or email/password)
   → See only matters they're assigned to
   → Query documents within their matters
```

### What's Missing from This Flow

| Step | Current State | Gap |
|------|--------------|-----|
| Create tenant | No API | Need admin endpoint |
| Create Blob container | Manual | Need automation |
| Create first user | SQL insert | Need admin endpoint |
| Send invite email | No email service | Need SendGrid/SES |
| Password reset | Not implemented | Need reset flow |
| First matter | Auto-created on upload | Need explicit creation |
| Upload documents | Works | Need storage scoping |
| Assign team members | Works | Need invitation flow |

---

## Pricing Tier Alignment

The architecture already defines 4 tiers in `ARCHITECTURE.md`:

| Tier | LLM | Search | Target Firm Size | Monthly Price Range |
|------|-----|--------|-----------------|-------------------|
| Starter | Gemini Flash | pgvector | Solo/2-5 attorneys | $99-299 |
| Professional | Azure GPT-5-mini | pgvector | 5-20 attorneys | $499-999 |
| Enterprise | Azure GPT-5-mini | Azure AI Search | 20-100 attorneys | $2,000-5,000 |
| On-Prem | Ollama | pgvector | Any (privacy-first) | License + support |

**What's needed for each tier:**

| Feature | Starter | Professional | Enterprise |
|---------|---------|-------------|------------|
| Multi-tenant isolation | Shared infra | Shared infra | Dedicated DB option |
| SSO | Google only | Google + Microsoft | SAML/OIDC custom |
| Storage | 10GB | 100GB | Unlimited |
| Queries/month | 1,000 | 10,000 | Unlimited |
| SLA | Best effort | 99.5% | 99.9% |
| Support | Email | Email + chat | Dedicated CSM |
| Compliance | Basic audit | SOC 2 | SOC 2 + custom |
| Data residency | US | US/EU | Custom region |

---

## Roadmap to Multi-Tenant Beta

### Sprint 1: Secure the Foundation (1-2 weeks)
- [ ] Fix latency issues (see `LATENCY_FIXES.md`)
- [ ] Set secure defaults: `AUTH_BYPASS_ENABLED=0`, require `JWT_SECRET_KEY`
- [ ] Add startup validation: refuse to start if JWT secret is default value
- [ ] Add load tests: verify NFR-011 (p95 < 8s) and NFR-012 (50 concurrent users)

### Sprint 2: Tenant Onboarding (2-3 weeks)
- [ ] Admin API for tenant creation
- [ ] Admin API for user creation with invite flow
- [ ] Per-tenant Azure Blob Storage isolation (prefix-based)
- [ ] Explicit matter creation endpoint (vs auto-create on upload)

### Sprint 3: Resource Limits (2-3 weeks)
- [ ] Per-tenant query rate limiting
- [ ] Per-tenant storage quotas
- [ ] Per-tenant LLM token budgets
- [ ] Usage tracking (queries, storage, tokens per tenant)

### Sprint 4: Isolation Testing (2 weeks)
- [ ] Cross-tenant isolation integration tests
- [ ] Azure Search filter injection fuzzing
- [ ] Auth mode enforcement tests (JWT mode rejects header spoofing)
- [ ] Matter access control boundary tests

### Sprint 5: Operational Readiness (2-3 weeks)
- [ ] Redis cache layer (shared across containers)
- [ ] Horizontal scaling with 2+ API containers
- [ ] Azure Monitor alerting (latency, error rate, token usage)
- [ ] Structured JSON logging
- [ ] Backup/restore testing with documented RTO/RPO

**Total to multi-tenant beta: 10-14 weeks**

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cross-tenant data leak | Low (data model is solid) | Critical (law firm data) | Isolation tests, pen test |
| Auth bypass in production | Medium (dangerous defaults) | Critical | Startup validation |
| Latency regression under load | High (sync architecture) | High (user churn) | Load tests, async migration |
| Azure Search index size limits | Low (current scale) | Medium | Monitor index stats |
| LLM cost overrun | Medium (no per-tenant limits) | High (financial) | Token budgets, alerts |
| Single point of failure (Azure OpenAI) | Medium | High (total outage) | Circuit breaker, fallback provider |

---

## Bottom Line

The data model is ready for multi-tenant. The application is not. The gap is primarily:
1. **Security defaults** (must fix before any shared deployment)
2. **Tenant lifecycle** (no way to create/manage tenants)
3. **Resource isolation** (no per-tenant limits)
4. **Performance under concurrency** (sync architecture)

Items 1 and 2 are blocking. Items 3 and 4 can be addressed in parallel with early pilot customers, but must be solved before scaling past 3-5 tenants.

The fastest path to a paying customer:
1. Fix latency (1 week)
2. Fix security defaults (1 day)
3. Manually provision one tenant (SQL + Azure CLI)
4. Deploy with `AUTH_MODE=jwt`
5. Onboard one firm with 5-10 attorneys
6. Build tenant management while they use it

This is the "sell the MVP, build the platform" approach. It works if you have a firm ready to pilot. If you're trying to build a self-service product, add 10-14 weeks.
