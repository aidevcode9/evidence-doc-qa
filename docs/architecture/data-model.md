# Data Model

> Current implementation schema. All tables use String primary keys (UUIDs) and ISO-8601 timestamp strings.

---

## Design Notes

### Tenant & Matter Isolation

The current implementation uses **inline isolation columns** (`tenant_id`, `matter_id`) in all tables rather than separate `tenants` and `matters` lookup tables:

**Benefits:**
- Simpler schema, fewer joins
- Faster isolation checks (no foreign key lookups)
- Suitable for single-instance deployments

**Future consideration:** Separate `tenants` and `matters` tables could be added later for storing additional metadata (tenant settings, matter retention policies, etc.) without changing the core isolation model.

---

## Core Document Tables

### documents

Uploaded document metadata.

```sql
CREATE TABLE documents (
    doc_id          STRING PRIMARY KEY,
    tenant_id       STRING NOT NULL,        -- FR-001: Tenant isolation
    matter_id       STRING NOT NULL,        -- FR-002: Matter isolation
    doc_sha256      STRING NOT NULL,        -- Deduplication via hash
    doc_name        STRING NOT NULL,        -- Original filename
    storage_path    STRING NOT NULL,        -- S3/MinIO/filesystem path
    ingested_at_utc STRING NOT NULL,        -- ISO-8601 timestamp
    docs_snapshot_id STRING NOT NULL        -- Version/snapshot identifier
);

CREATE INDEX ix_documents_tenant_id ON documents(tenant_id);
CREATE INDEX ix_documents_matter_id ON documents(matter_id);
```

### chunks

Document chunks extracted during parsing (without embeddings).

```sql
CREATE TABLE chunks (
    chunk_id         STRING PRIMARY KEY,
    tenant_id        STRING NOT NULL,       -- FR-001: Tenant isolation
    matter_id        STRING NOT NULL,       -- FR-002: Matter isolation
    docs_snapshot_id STRING NOT NULL,       -- Links to document version
    doc_id           STRING NOT NULL,       -- Links to documents.doc_id
    doc_sha256       STRING NOT NULL,       -- Document hash
    page_num         INTEGER NOT NULL,      -- Starting page number
    page_end         INTEGER NOT NULL,      -- Ending page number (for multi-page chunks)
    chunk_index      INTEGER NOT NULL,      -- Chunk sequence number in document
    char_start       INTEGER NOT NULL,      -- Character offset start
    char_end         INTEGER NOT NULL,      -- Character offset end
    chunk_text       TEXT NOT NULL,         -- Extracted text content
    parse_mode       STRING NOT NULL        -- Parser used: pypdf, marker, llamaparse
);

CREATE INDEX ix_chunks_tenant_id ON chunks(tenant_id);
CREATE INDEX ix_chunks_matter_id ON chunks(matter_id);
```

### index_records

Chunks with embeddings, ready for retrieval (denormalized for performance).

```sql
CREATE TABLE index_records (
    chunk_id          STRING PRIMARY KEY,
    tenant_id         STRING NOT NULL,      -- FR-001: Tenant isolation
    matter_id         STRING NOT NULL,      -- FR-002: Matter isolation
    docs_snapshot_id  STRING NOT NULL,      -- Document version
    doc_id            STRING NOT NULL,      -- Document identifier
    doc_name          STRING NOT NULL,      -- Document filename (denormalized)
    page_num          INTEGER NOT NULL,     -- Starting page number
    page_end          INTEGER NOT NULL,     -- Ending page number
    char_start        INTEGER NOT NULL,     -- Character offset start
    char_end          INTEGER NOT NULL,     -- Character offset end
    chunk_index       INTEGER NOT NULL,     -- Chunk sequence number
    chunk_text        TEXT NOT NULL,        -- Text content
    embedding_json    TEXT NOT NULL,        -- JSON array of embedding vector
    indexed_at_utc    STRING NOT NULL,      -- When indexed
    index_version     STRING NOT NULL,      -- Index schema version
    retrieval_version STRING NOT NULL       -- Retrieval algorithm version
);

CREATE INDEX ix_index_records_tenant_id ON index_records(tenant_id);
CREATE INDEX ix_index_records_matter_id ON index_records(matter_id);
```

**Note:** Embeddings stored as JSON arrays. For production with pgvector, add:
```sql
ALTER TABLE index_records ADD COLUMN embedding vector(1536);
CREATE INDEX idx_index_records_embedding ON index_records
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## Q&A Session Tables

### qa_sessions

Conversation sessions for tracking multi-turn Q&A (FR-032).

```sql
CREATE TABLE qa_sessions (
    session_id       STRING PRIMARY KEY,
    tenant_id        STRING NOT NULL,       -- FR-001: Tenant isolation
    matter_id        STRING NOT NULL,       -- FR-002: Matter isolation
    docs_snapshot_id STRING NOT NULL,       -- Document version for this session
    created_at_utc   STRING NOT NULL
);

CREATE INDEX ix_qa_sessions_tenant_id ON qa_sessions(tenant_id);
CREATE INDEX ix_qa_sessions_matter_id ON qa_sessions(matter_id);
```

### qa_messages

Messages within a Q&A session (user questions + assistant answers).

```sql
CREATE TABLE qa_messages (
    message_id             STRING PRIMARY KEY,
    tenant_id              STRING NOT NULL,  -- FR-001: Tenant isolation
    matter_id              STRING NOT NULL,  -- FR-002: Matter isolation
    session_id             STRING NOT NULL,  -- Links to qa_sessions.session_id
    role                   STRING NOT NULL,  -- "user" | "assistant"
    content                TEXT NOT NULL,    -- Message text
    citations_json         TEXT NULL,        -- JSON array of citation objects
    evidence_json          TEXT NULL,        -- JSON array of evidence objects
    refusal_code           STRING NULL,      -- If assistant refused (low confidence, etc.)
    version_snapshot_json  TEXT NULL,        -- Captured versions for debugging
    created_at_utc         STRING NOT NULL
);

CREATE INDEX ix_qa_messages_tenant_id ON qa_messages(tenant_id);
CREATE INDEX ix_qa_messages_matter_id ON qa_messages(matter_id);
```

---

## Telemetry & Cost Tracking

### telemetry

LLM call telemetry for cost tracking and debugging (NFR-030).

```sql
CREATE TABLE telemetry (
    request_id         STRING PRIMARY KEY,
    tenant_id          STRING NOT NULL,     -- FR-001: Tenant isolation
    matter_id          STRING NOT NULL,     -- FR-002: Matter isolation
    docs_snapshot_id   STRING NOT NULL,     -- Document version
    prompt_version     STRING NOT NULL,     -- Prompt template version
    retrieval_version  STRING NOT NULL,     -- Retrieval algorithm version
    model_id           STRING NOT NULL,     -- LLM model identifier
    parser_mode        STRING NOT NULL,     -- Parser used
    timestamp_utc      STRING NOT NULL,     -- Request timestamp
    latency_ms         INTEGER NOT NULL,    -- Total latency
    tokens_in          INTEGER NOT NULL,    -- Prompt tokens
    tokens_out         INTEGER NOT NULL,    -- Completion tokens
    cost_est           FLOAT NOT NULL,      -- Estimated cost in USD
    cache_hit          BOOLEAN NOT NULL,    -- Whether cache was used
    refusal_code       STRING NULL,         -- If request refused
    failure_label      STRING NULL,         -- If request failed
    trace_metadata     TEXT NULL,           -- JSON blob: retrieval scores, cost breakdown, debug info
    langfuse_trace_id  STRING NULL          -- NFR-045: Langfuse trace ID for cross-reference
);

CREATE INDEX ix_telemetry_tenant_id ON telemetry(tenant_id);
CREATE INDEX ix_telemetry_matter_id ON telemetry(matter_id);
CREATE INDEX ix_telemetry_langfuse ON telemetry(langfuse_trace_id);
```

**Usage:** Track LLM costs, debug issues, correlate with Langfuse traces.

---

## Authentication & Authorization (FR-050, FR-051, FR-003, FR-004)

### users

User accounts with authentication data (FR-050).

```sql
CREATE TABLE users (
    user_id             STRING PRIMARY KEY,
    tenant_id           STRING NOT NULL,    -- FR-001: Tenant isolation
    email               STRING NOT NULL,    -- User email (unique per tenant)
    role                STRING NOT NULL,    -- admin | attorney | paralegal | viewer
    display_name        STRING NULL,        -- Optional display name
    created_at_utc      STRING NOT NULL,
    -- Authentication columns (FR-050)
    password_hash       STRING NULL,        -- NULL for SSO-only users
    auth_provider       STRING NOT NULL,    -- "local" | "oidc_azure" | "oidc_google"
    is_active           BOOLEAN NOT NULL,   -- Account active/deactivated
    last_login_utc      STRING NULL,        -- Last successful login
    failed_login_count  INTEGER NOT NULL,   -- Failed login attempts
    locked_until_utc    STRING NULL         -- Account lockout expiration
);

CREATE INDEX ix_users_tenant_id ON users(tenant_id);
CREATE UNIQUE INDEX ix_users_email_tenant ON users(email, tenant_id);
```

### matter_assignments

Matter-level access control (FR-004).

```sql
CREATE TABLE matter_assignments (
    assignment_id   STRING PRIMARY KEY,
    user_id         STRING NOT NULL,        -- User granted access
    tenant_id       STRING NOT NULL,        -- FR-001: Tenant isolation
    matter_id       STRING NOT NULL,        -- Matter user can access
    granted_by      STRING NOT NULL,        -- User who granted access
    granted_at_utc  STRING NOT NULL
);

CREATE INDEX ix_matter_assignments_user_id ON matter_assignments(user_id);
CREATE INDEX ix_matter_assignments_tenant_id ON matter_assignments(tenant_id);
CREATE INDEX ix_matter_assignments_matter_id ON matter_assignments(matter_id);
CREATE UNIQUE INDEX ix_matter_assignments_user_tenant_matter
    ON matter_assignments(user_id, tenant_id, matter_id);
```

**Note:** Admins bypass this check and have access to all matters in their tenant.

### refresh_tokens

JWT refresh token storage for authentication (FR-050).

```sql
CREATE TABLE refresh_tokens (
    token_id        STRING PRIMARY KEY,     -- JTI from JWT
    user_id         STRING NOT NULL,        -- Token owner
    tenant_id       STRING NOT NULL,        -- FR-001: Tenant isolation
    token_hash      STRING NOT NULL,        -- SHA256 hash (not plaintext)
    expires_at_utc  STRING NOT NULL,        -- Token expiration
    created_at_utc  STRING NOT NULL,
    revoked_at_utc  STRING NULL             -- NULL = active, timestamp = revoked
);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX ix_refresh_tokens_tenant_id ON refresh_tokens(tenant_id);
CREATE INDEX ix_refresh_tokens_user_tenant ON refresh_tokens(user_id, tenant_id);
```

**Security:** Only SHA256 hashes stored, never plaintext tokens.

### sso_states

SSO state storage for CSRF protection (FR-051).

```sql
CREATE TABLE sso_states (
    state_token     STRING PRIMARY KEY,     -- Opaque random state token
    provider        STRING NOT NULL,        -- "microsoft" | "google"
    tenant_id       STRING NOT NULL,        -- Application tenant ID
    code_verifier   STRING NOT NULL,        -- PKCE code verifier
    nonce           STRING NOT NULL,        -- ID token nonce for validation
    expires_at_utc  STRING NOT NULL,        -- State expiration (short-lived)
    created_at_utc  STRING NOT NULL
);

CREATE INDEX ix_sso_states_expires_at ON sso_states(expires_at_utc);
```

**Usage:** Stores pending SSO login state, consumed once on callback. Cleanup job deletes expired states.

---

## Audit & Compliance (FR-040, FR-042)

### audit_events

Immutable audit log for compliance (FR-040).

```sql
CREATE TABLE audit_events (
    event_id       STRING PRIMARY KEY,
    tenant_id      STRING NOT NULL,         -- FR-001: Tenant isolation
    matter_id      STRING NULL,             -- Matter context (if applicable)
    user_id        STRING NOT NULL,         -- User who performed action
    event_type     STRING NOT NULL,         -- "query" | "upload" | "export" | "delete" | "login" | ...
    event_json     TEXT NOT NULL,           -- JSON event details (PII-redacted)
    response_id    STRING NULL,             -- Links to Q&A response
    created_at_utc STRING NOT NULL
);

CREATE INDEX ix_audit_events_tenant_id ON audit_events(tenant_id);
CREATE INDEX ix_audit_events_matter_id ON audit_events(matter_id);
CREATE INDEX ix_audit_events_user_id ON audit_events(user_id);
CREATE INDEX ix_audit_events_event_type ON audit_events(event_type);
CREATE INDEX ix_audit_events_created_at ON audit_events(created_at_utc);
```

**Immutability:** No UPDATE or DELETE functions provided. Append-only log.

### retention_policies

Configurable data retention per tenant and resource type (FR-042).

```sql
CREATE TABLE retention_policies (
    policy_id       STRING PRIMARY KEY,
    tenant_id       STRING NOT NULL,        -- FR-001: Tenant isolation
    resource_type   STRING NOT NULL,        -- "qa_messages" | "audit_events" | "telemetry" | ...
    retention_days  INTEGER NOT NULL,       -- How many days to retain
    created_at_utc  STRING NOT NULL,
    updated_at_utc  STRING NOT NULL
);

CREATE INDEX ix_retention_policies_tenant_id ON retention_policies(tenant_id);
CREATE UNIQUE CONSTRAINT uq_retention_policies_tenant_resource
    ON retention_policies(tenant_id, resource_type);
```

**Usage:** Cleanup jobs query this table to determine what data to delete.

---

## Migration Status

All tables tracked via Alembic migrations in `alembic/versions/`:

| Migration | Tables Created |
|-----------|----------------|
| 0001 | documents, chunks, index_records, telemetry |
| 0002 | (Added page_end, char_start, char_end columns) |
| 0003 | qa_sessions, qa_messages |
| 0004 | (Added tenant_id, matter_id to all tables) |
| 0005 | users |
| 0006 | matter_assignments |
| 0007 | refresh_tokens (+ auth columns to users) |
| 0008 | audit_events |
| 0009 | retention_policies |
| 0010 | sso_states |
| 0011 | (Added langfuse_trace_id to telemetry — NFR-045) |

---

## Query Patterns

### Tenant Isolation (FR-001)

**Every query MUST filter by tenant_id:**

```python
# Good: Tenant-isolated query
chunks = session.execute(
    select(Chunk).where(
        Chunk.tenant_id == tenant_id,
        Chunk.matter_id == matter_id
    )
).scalars().all()

# BAD: Missing tenant isolation - cross-tenant leak!
chunks = session.execute(
    select(Chunk).where(Chunk.matter_id == matter_id)
).scalars().all()
```

### Matter Access Control (FR-004)

Before accessing matter data, verify user has access:

```python
from app.db import user_has_matter_access

if not user_has_matter_access(user_id, tenant_id, matter_id, user_role):
    raise PermissionError("User lacks access to this matter")
```

Admins bypass this check and can access all matters in their tenant.

---

## Future Considerations

### Separate Tenant/Matter Metadata Tables

If needed for additional features, add:

```sql
CREATE TABLE tenants (
    tenant_id   STRING PRIMARY KEY,
    name        STRING NOT NULL,
    settings    JSONB,  -- Tenant-specific config
    created_at  STRING NOT NULL
);

CREATE TABLE matters (
    matter_id   STRING PRIMARY KEY,
    tenant_id   STRING NOT NULL,
    name        STRING NOT NULL,
    status      STRING NOT NULL,  -- "active" | "closed" | "hold"
    created_at  STRING NOT NULL
);
```

This would **not** require changing isolation checks in existing queries, since `tenant_id`/`matter_id` columns would remain.

### Usage Tracking for Billing

If usage-based billing is needed, add:

```sql
CREATE TABLE usage_daily (
    tenant_id               STRING NOT NULL,
    date                    DATE NOT NULL,
    queries_count           INTEGER DEFAULT 0,
    pages_ingested          INTEGER DEFAULT 0,
    llm_tokens_prompt       BIGINT DEFAULT 0,
    llm_tokens_completion   BIGINT DEFAULT 0,
    storage_bytes           BIGINT DEFAULT 0,
    PRIMARY KEY (tenant_id, date)
);
```

This data can be aggregated from the existing `telemetry` table.

### pgvector Migration

For production vector search, migrate `index_records.embedding_json` to pgvector:

1. Add `embedding vector(1536)` column
2. Backfill from JSON arrays
3. Create ivfflat index
4. Update retrieval code to use vector similarity

See [ARCHITECTURE.md](../../ARCHITECTURE.md) for deployment tier guidance.
