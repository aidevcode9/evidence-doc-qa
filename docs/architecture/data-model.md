# Data Model

> All tables include: `created_at TIMESTAMP`, `updated_at TIMESTAMP`, `created_by UUID` where applicable.

## Core Tables

```sql
-- Tenant isolation
tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    settings_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users scoped to tenant
users (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    email TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'admin', 'attorney', 'paralegal', 'viewer'
    mfa_enabled BOOL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Matters (cases) scoped to tenant
matters (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- 'active', 'closed', 'hold'
    retention_days INT DEFAULT 365,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Matter membership (RBAC per matter)
matter_members (
    matter_id UUID REFERENCES matters(id),
    user_id UUID REFERENCES users(id),
    role TEXT NOT NULL,  -- 'owner', 'editor', 'viewer'
    PRIMARY KEY (matter_id, user_id)
);
```

## Document & Chunk Tables

```sql
-- Uploaded documents
documents (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID REFERENCES matters(id),
    filename TEXT NOT NULL,
    storage_uri TEXT NOT NULL,  -- S3/MinIO path
    sha256 TEXT NOT NULL,       -- Deduplication
    page_count INT,
    metadata_json JSONB,        -- doc_type, date, custodian, tags
    privilege_flag BOOL DEFAULT FALSE,
    status TEXT DEFAULT 'queued',  -- 'queued', 'processing', 'ready', 'failed'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document chunks with embeddings
doc_chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID REFERENCES matters(id),
    page_number INT NOT NULL,
    char_start INT NOT NULL,
    char_end INT NOT NULL,
    text TEXT NOT NULL,
    embedding_model TEXT NOT NULL,  -- Track which model generated embedding
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- pgvector column and index
ALTER TABLE doc_chunks ADD COLUMN embedding vector(1536);
CREATE INDEX idx_chunks_embedding ON doc_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-text search index (for BM25 hybrid)
ALTER TABLE doc_chunks ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX idx_chunks_fts ON doc_chunks USING gin(search_vector);
```

## Q&A & Session Tables

```sql
-- Chat sessions per matter
qa_sessions (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID REFERENCES matters(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Messages in session (user + assistant)
qa_messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES qa_sessions(id),
    role TEXT NOT NULL,  -- 'user', 'assistant'
    content TEXT NOT NULL,
    citations_json JSONB,  -- [{chunk_id, page, text_snippet}, ...]
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Audit & Usage Tables

```sql
-- Immutable audit log
audit_events (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID,
    user_id UUID REFERENCES users(id),
    event_type TEXT NOT NULL,    -- 'query', 'upload', 'export', 'delete'
    event_json JSONB NOT NULL,   -- Details (no PII, redacted excerpts)
    response_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily usage rollup (billing)
usage_daily (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    date DATE NOT NULL,
    queries_count INT DEFAULT 0,
    pages_ingested INT DEFAULT 0,
    llm_tokens_prompt BIGINT DEFAULT 0,
    llm_tokens_completion BIGINT DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    PRIMARY KEY (tenant_id, date)
);
```

## Key Indexes

| Index | Purpose |
|-------|---------|
| `idx_chunks_embedding` | Vector similarity search (ivfflat) |
| `idx_chunks_fts` | Full-text/BM25 search (GIN) |
| `idx_llm_calls_tenant_date` | Billing queries by tenant + date |
| `idx_llm_calls_langfuse` | Correlation lookups for debugging |
