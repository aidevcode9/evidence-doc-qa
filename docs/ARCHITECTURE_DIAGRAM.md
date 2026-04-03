# Architecture Diagrams

> Maintained as Mermaid — renders in GitHub, VS Code, and most markdown viewers.
> Last updated: 2026-04-02

---

## System Overview

```mermaid
graph TB
    subgraph Frontend["Frontend (Vercel)"]
        NextJS["Next.js 16<br/>SSR + React 19"]
        Proxy["/api/backend/* proxy"]
    end

    subgraph Backend["Backend (Azure Container Apps)"]
        FastAPI["FastAPI + Uvicorn"]

        subgraph Middleware
            JWT["JWT Auth"]
            RateLimit["Rate Limiter<br/>(slowapi)"]
            CORS["CORS"]
        end

        subgraph Routers
            Ask["/v1/ask"]
            Docs["/v1/docs"]
            Matters["/v1/matters"]
            Auth["/v1/auth"]
            Admin["/v1/admin"]
            Audit["/v1/audit"]
            Metrics["/v1/metrics"]
            Export["/v1/sessions"]
            Health["/healthz"]
        end

        subgraph Services
            AskSvc["ask_service.py<br/>RAG Orchestrator"]
            DocSvc["document_service.py<br/>Upload + Parse"]
        end

        subgraph Core["Core Pipeline"]
            Retrieval["retrieval.py<br/>Hybrid Search"]
            Evidence["evidence.py<br/>Citation Validation"]
            Policy["policy.py<br/>Injection + Gates"]
            Verify["verification.py<br/>LLM Verification"]
        end
    end

    subgraph External["External Services"]
        PG["PostgreSQL<br/>(Azure Flexible Server)<br/>11 tables"]
        AzSearch["Azure AI Search<br/>BM25 + Vector + Reranker"]
        AzOpenAI["Azure OpenAI<br/>GPT-5-mini + Embeddings"]
        Blob["Azure Blob Storage<br/>Raw Documents"]
        Langfuse["Langfuse<br/>LLM Observability"]
        OTEL["Azure Monitor<br/>OpenTelemetry"]
    end

    NextJS --> Proxy
    Proxy -->|"auth headers"| FastAPI
    FastAPI --> Middleware
    Middleware --> Routers
    Ask --> AskSvc
    Docs --> DocSvc
    AskSvc --> Core
    Retrieval --> AzSearch
    Retrieval --> PG
    Verify --> AzOpenAI
    DocSvc --> Blob
    DocSvc --> PG
    AskSvc --> Langfuse
    AskSvc --> OTEL
    AskSvc --> PG
```

---

## RAG Pipeline Flow

```mermaid
flowchart TD
    Q["User Question"] --> Inject{"Injection<br/>Check"}
    Inject -->|"BLOCKED"| R1["REFUSAL:<br/>Injection Detected"]
    Inject -->|"PASS"| Cache{"Query<br/>Cache?"}
    Cache -->|"HIT"| Cached["Return Cached Response"]
    Cache -->|"MISS"| Context["Contextualize<br/>(follow-up detection)"]
    Context --> Embed["Generate Embedding<br/>(text-embedding-3-large)"]
    Embed --> Search["Hybrid Search"]

    subgraph SearchBox["Retrieval (retrieval.py)"]
        Search --> AzS{"Azure Search<br/>Available?"}
        AzS -->|"YES"| Azure["Azure AI Search<br/>BM25 + Vector + Reranker"]
        AzS -->|"NO"| Local["Local Hybrid<br/>BM25 + Cosine + RRF"]
    end

    Azure --> Conf{"Confidence<br/>>= 0.70?"}
    Local --> Conf
    Conf -->|"NO"| R2["REFUSAL:<br/>Low Confidence"]
    Conf -->|"YES"| AutoV{"Auto-Verify?<br/>reranker >= 2.5<br/>overlap >= 0.3"}
    AutoV -->|"YES"| Grade
    AutoV -->|"NO"| LLMVerify["LLM Verification<br/>(parallel, max 3 chunks)"]
    LLMVerify --> Verdict{"Verified?"}
    Verdict -->|"NO"| R3["REFUSAL:<br/>Unverified"]
    Verdict -->|"YES"| Grade["Evidence Grade<br/>A / B / C"]
    Grade --> Answer["Build Answer<br/>+ Citations"]
    Answer --> Store["Store in DB<br/>+ Cache + Telemetry"]

    style R1 fill:#fee,stroke:#c00
    style R2 fill:#fee,stroke:#c00
    style R3 fill:#fee,stroke:#c00
    style Answer fill:#efe,stroke:#0a0
    style Cached fill:#efe,stroke:#0a0
```

---

## Data Model

```mermaid
erDiagram
    MATTERS ||--o{ DOCUMENTS : contains
    MATTERS ||--o{ MATTER_ASSIGNMENTS : "access via"
    DOCUMENTS ||--o{ CHUNKS : "parsed into"
    CHUNKS ||--o{ INDEX_RECORDS : "indexed as"
    QA_SESSIONS ||--o{ QA_MESSAGES : contains
    USERS ||--o{ MATTER_ASSIGNMENTS : "assigned to"
    USERS ||--o{ REFRESH_TOKENS : "authenticates via"

    MATTERS {
        string matter_id PK
        string tenant_id PK
        string display_name
        string created_at_utc
    }

    DOCUMENTS {
        string doc_id PK
        string tenant_id
        string matter_id
        string doc_name
        string doc_sha256
        string status
        string storage_path
    }

    CHUNKS {
        string chunk_id PK
        string tenant_id
        string matter_id
        int page_num
        int char_start
        int char_end
        text chunk_text
    }

    INDEX_RECORDS {
        string chunk_id PK
        string tenant_id
        string matter_id
        text embedding_json
    }

    USERS {
        string user_id PK
        string tenant_id
        string email
        string role
        string password_hash
        bool is_active
    }

    QA_SESSIONS {
        string session_id PK
        string tenant_id
        string user_id
        string matter_id
    }

    TELEMETRY {
        string request_id PK
        string tenant_id
        int latency_ms
        int tokens_in
        int tokens_out
        float cost_est
    }
```

---

## Deployment Architecture

```mermaid
graph LR
    subgraph GitHub
        Push["git push main"] --> GHA["GitHub Actions"]
    end

    subgraph Azure
        GHA -->|"docker build + push"| ACR["Azure Container Registry<br/>docqaregistry.azurecr.io"]
        ACR -->|"az containerapp update"| ACA["Container Apps<br/>docqa-api"]
        ACA --> PG["PostgreSQL<br/>Flexible Server"]
        ACA --> Search["AI Search"]
        ACA --> OpenAI["Azure OpenAI"]
        ACA --> Blob["Blob Storage"]
    end

    subgraph Vercel
        GitPush["git push main"] --> VercelBuild["Vercel Build"]
        VercelBuild --> CDN["Edge CDN<br/>Next.js SSR"]
    end

    CDN -->|"/api/backend/*"| ACA
```

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as API
    participant DB as PostgreSQL

    U->>F: Enter email + password
    F->>A: POST /v1/auth/login
    A->>DB: Verify credentials (Argon2id)
    A->>DB: Check lockout status
    A->>A: Generate JWT (30 min) + Refresh (7 day)
    A-->>F: Set httpOnly cookies
    F-->>U: Redirect to /

    Note over U,A: Subsequent requests
    F->>A: GET /v1/matters (Bearer token)
    A->>A: Validate JWT, extract tenant_id
    A->>DB: Query with tenant isolation
    A-->>F: Response

    Note over U,A: Token refresh
    F->>A: POST /v1/auth/refresh
    A->>DB: Validate refresh token
    A->>A: Issue new JWT + rotate refresh
    A-->>F: New cookies
```
