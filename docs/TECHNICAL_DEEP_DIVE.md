# Evidence-Bound: Technical Deep Dive

> How Evidence-Grounded Document Q&A Works Under the Hood — From RAG Pipeline to Production Engineering

**Audience:** Senior AI engineers, architects, and technical evaluators who want to understand both the retrieval/verification pipeline and the production hardening that makes this system enterprise-ready.

---

## Table of Contents

**Core RAG Pipeline**
1. [System Overview](#system-overview)
2. [Request Flow Architecture](#request-flow-architecture)
3. [Retrieval Pipeline](#retrieval-pipeline)
4. [Evidence Verification](#evidence-verification)
5. [Citation Validation](#citation-validation)
6. [Security & Policy Enforcement](#security--policy-enforcement)
7. [Provider Abstractions](#provider-abstractions)

**UX & Document Interaction**
8. [Document Disambiguation & Pinning](#document-disambiguation--pinning)
9. [Case Management & Auto-Naming](#case-management--auto-naming)

**Production Engineering**
10. [Observability Stack](#observability-stack)
11. [Performance & Latency Controls](#performance--latency-controls)
12. [Caching Architecture](#caching-architecture)
13. [Cost Tracking & Estimation](#cost-tracking--estimation)
14. [Rate Limiting & Concurrency](#rate-limiting--concurrency)
15. [PII Redaction](#pii-redaction)
16. [Graceful Degradation](#graceful-degradation)
17. [Test Architecture](#test-architecture)
18. [Data Model](#data-model)

---

## System Overview

Evidence-Bound is a document Q&A system designed for high-stakes environments (legal, compliance, regulated industries) where **every answer must cite source documents**. The system refuses to answer if it cannot find verifiable evidence.

### Core Guarantee

```
If the system returns an answer, that answer includes:
  1. A citation to a specific document, page, and character range
  2. A snippet that exists verbatim in the source
  3. A confidence score above the configured threshold
  4. An evidence grade (A/B/C) based on verification status
```

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Ask Service | Orchestrates the full RAG pipeline | [apps/api/app/services/ask_service.py](../apps/api/app/services/ask_service.py) |
| Retrieval | Hybrid search (BM25 + vector + reranker) | [apps/api/app/retrieval.py](../apps/api/app/retrieval.py) |
| Evidence | Citation extraction and grading | [apps/api/app/evidence.py](../apps/api/app/evidence.py) |
| Verification | LLM-based relevance checking | [apps/api/app/verification.py](../apps/api/app/verification.py) |
| Policy | Injection detection, confidence gating | [apps/api/app/policy.py](../apps/api/app/policy.py) |

---

## Request Flow Architecture

Every `/ask` request goes through a multi-stage pipeline with explicit refusal points:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              POST /v1/ask                                     │
│                                                                              │
│  ┌─────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐    ┌───────┐ │
│  │ Policy  │───▶│ Retrieval│───▶│ Confidence │───▶│ Verify   │───▶│ Grade │ │
│  │ Check   │    │ (Hybrid) │    │ Filter     │    │ (LLM)    │    │       │ │
│  └────┬────┘    └────┬─────┘    └─────┬──────┘    └────┬─────┘    └───┬───┘ │
│       │              │                │                 │              │     │
│       ▼              ▼                ▼                 ▼              ▼     │
│   REFUSAL:       REFUSAL:         REFUSAL:          REFUSAL:       ANSWER   │
│   Injection      No Evidence      Low Confidence    LLM Rejected   + Citation│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Orchestration Code

The main entry point is `execute_ask()` in [ask_service.py:41-606](../apps/api/app/services/ask_service.py#L41-L606):

```python
@_observe(name="execute_ask", capture_input=False, capture_output=False)
def execute_ask(
    payload: AskRequest,
    session_id: str | None = None,
    *,
    tenant_id: str,
    matter_id: str,
) -> AskResponse:
    # 1. Input validation
    question = payload.question.strip()
    if len(question) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=400, detail="Question too long")

    # 2. Policy check (injection detection)
    if policy.is_injection_attempt(question):
        return _emit_refusal(refusal_code=RefusalCode.INJECTION_DETECTED, ...)

    # 3. Hybrid retrieval with tenant/matter isolation
    results, embedding_usage = retrieval.hybrid_search(
        question, docs_snapshot_id,
        tenant_id=tenant_id,    # FR-001: Tenant isolation
        matter_id=matter_id,    # FR-002: Matter isolation
        doc_id=doc_id,          # Optional: pin to single document
        return_usage=True,
    )

    # 4. Confidence filtering
    candidates = [r for r in results if score >= conf_min]
    if not candidates:
        return _emit_refusal(refusal_code=RefusalCode.LOW_RETRIEVAL_CONFIDENCE, ...)

    # 5. LLM verification (optional but recommended)
    if verification.is_enabled():
        for chunk in candidates[:3]:
            status, span, reason, usage = verification.verify_relevance(
                question, chunk["chunk_text"], ...
            )
            if status == "verified":
                verified_chunk = chunk
                break

    # 6. Evidence grading
    grade, label = evidence.evidence_grade(
        verified, rrf_score, rrf_margin, overlap,
        reranker_score=azure_rerank_score,
    )

    # 7. Build response with citations
    return AskResponse(
        answer_text=f"According to {doc_name} (page {page}) [1], {span}",
        citations=[Citation(...)],
        evidence=EvidenceSupport(verdict="VERIFIED", evidence_grade=grade, ...),
    )
```

---

## Retrieval Pipeline

The system uses **hybrid search** combining lexical (BM25) and semantic (vector) approaches, with optional semantic reranking.

### Hybrid Search Algorithm

Located in [retrieval.py:32-105](../apps/api/app/retrieval.py#L32-L105):

```python
def hybrid_search(
    question: str,
    docs_snapshot_id: str | None,
    tenant_id: str,           # REQUIRED for isolation
    matter_id: str,           # REQUIRED for isolation
    *,
    doc_id: str | None = None,  # Optional: pin to single document
) -> list[ChunkRecord]:
    # Generate query embedding
    embeddings, embedding_usage = embed_texts_with_usage([question])
    query_embedding = embeddings[0]

    # Route to Azure AI Search if configured
    if _azure_enabled():
        results = _azure_search(question, docs_snapshot_id, query_embedding,
                                tenant_id, matter_id)
        if results:
            return results

    # Local hybrid fallback
    query_tokens = _tokenize(question)
    for rec in records:
        rec["bm25_score"] = _bm25_score(query_tokens, ...)
        rec["vector_score"] = _cosine(query_embedding, rec["embedding_vector"])

    # Reciprocal Rank Fusion
    bm25_ranked = sorted(records, key=lambda r: r["bm25_score"], reverse=True)[:TOP_K_BM25]
    vec_ranked = sorted(records, key=lambda r: r["vector_score"], reverse=True)[:TOP_K_VECTOR]

    for idx, rec in enumerate(bm25_ranked, start=1):
        combined[rec["chunk_id"]]["rrf_score_raw"] += 1 / (RRF_K + idx)
    for idx, rec in enumerate(vec_ranked, start=1):
        combined[rec["chunk_id"]]["rrf_score_raw"] += 1 / (RRF_K + idx)

    return sorted(combined.values(), key=lambda r: r["rrf_score"], reverse=True)[:TOP_K]
```

### BM25 Implementation

The BM25 (Okapi) scoring in [retrieval.py:440-461](../apps/api/app/retrieval.py#L440-L461):

```python
def _bm25_score(
    query_tokens: list[str],
    tf: Counter[str],          # Term frequency in document
    df: Counter[str],          # Document frequency in corpus
    num_docs: int,
    dl: int,                   # Document length
    avgdl: float,              # Average document length
    k1: float = 1.2,           # Term saturation parameter
    b: float = 0.75,           # Length normalization
) -> float:
    score = 0.0
    for term in set(query_tokens):
        df_t = df.get(term, 0)
        idf = math.log((num_docs - df_t + 0.5) / (df_t + 0.5) + 1)
        tf_t = tf.get(term, 0)
        denom = tf_t + k1 * (1 - b + b * (dl / avgdl))
        score += idf * ((tf_t * (k1 + 1)) / denom)
    return score
```

### Azure AI Search Integration

For production, Azure AI Search provides semantic reranking in [retrieval.py:112-250](../apps/api/app/retrieval.py#L112-L250):

```python
def _azure_search(question, docs_snapshot_id, query_embedding, tenant_id, matter_id,
                   doc_id=None):
    # Build isolation filter (REQUIRED for FR-001, FR-002)
    filters = [
        f"tenant_id eq '{tenant_id}'",
        f"matter_id eq '{matter_id}'",
    ]
    if docs_snapshot_id:
        filters.append(f"docs_snapshot_id eq '{docs_snapshot_id}'")
    if doc_id:
        filters.append(f"doc_id eq '{doc_id}'")  # Pin to single document

    payload = {
        "search": question,
        "vectorQueries": [{
            "kind": "vector",
            "vector": query_embedding,
            "fields": "embedding_vector",
            "k": TOP_K_VECTOR,
        }],
        "queryType": "semantic",
        "semanticConfiguration": "default",
        "captions": "extractive|highlight-true",
        "filter": " and ".join(filters),
    }

    data = _request_azure_search(url, payload)
    # Results include:
    # - @search.score (hybrid lexical+vector)
    # - @search.rerankerScore (semantic reranker, 0-4 scale)
    # - @search.captions (extractive highlights)
```

---

## Evidence Verification

The LLM verification layer ensures retrieved chunks actually answer the question.

### Verifier Architecture

Located in [verification.py:27-131](../apps/api/app/verification.py#L27-L131):

```python
@_observe(name="verify_relevance", capture_input=False, capture_output=False)
def verify_relevance(
    question: str,
    chunk_text: str,
    request_id: str | None = None,
) -> tuple[str, str | None, str, UsageInfo]:
    """
    Returns: (status, span, reason, usage)
    - status: "verified" | "rejected" | "unverified"
    - span: Exact contiguous substring from chunk (if verified)
    - reason: FOUND | NOT_FOUND | PARTIAL | AMBIGUOUS | REQUIRES_INFERENCE
    """
    system_prompt = _load_verifier_prompt()
    user_prompt = (
        "QUESTION:\n"
        f"{question}\n\n"
        "CHUNK (untrusted):\n"
        "<chunk>\n"
        f"{chunk_text}\n"
        "</chunk>\n"
    )

    response = _call_openai({"messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]})

    return _parse_verifier_output(response["choices"][0]["message"]["content"], chunk_text)
```

### Verifier Output Parsing

The verifier returns structured JSON with span validation in [verification.py:330-377](../apps/api/app/verification.py#L330-L377):

```python
def _parse_verifier_output(raw: str, chunk_text: str) -> tuple[str, str | None, str]:
    payload = _extract_json_payload(raw)

    # Expected format:
    # {"verdict": "YES", "span": "exact text", "start": 0, "end": 10, "reason": "FOUND"}

    verdict = payload.get("verdict")
    span = payload.get("span")
    start = payload.get("start")
    end = payload.get("end")

    # CRITICAL: Verify span matches chunk_text[start:end]
    if verdict == "YES":
        expected = chunk_text[start:end]
        if span != expected:
            return "rejected", None, "SPAN_MISMATCH"
        if _span_contains_blocked_content(span):
            return "rejected", None, "BLOCKED_CONTENT"
        return "verified", span, payload.get("reason", "FOUND")

    return "rejected", None, payload.get("reason", "NOT_FOUND")
```

### Span Security Blocklist

Prevents injection via verified spans in [verification.py:308-327](../apps/api/app/verification.py#L308-L327):

```python
_SPAN_BLOCKLIST_PATTERNS = [
    r"ignore\s*(previous|prior|all|the|your)?\s*instructions?",
    r"system\s*prompt",
    r"jailbreak",
    r"bypass",
    r"disregard",
    r"override\s*(the|your|all)?\s*(instructions?|rules?)",
    r"<\s*script",
    r"javascript\s*:",
    r"on\w+\s*=",  # onclick=, onerror=, etc.
]

def _span_contains_blocked_content(span: str) -> bool:
    lower = span.lower()
    return any(re.search(pat, lower) for pat in _SPAN_BLOCKLIST_PATTERNS)
```

---

## Citation Validation

The evidence module prevents fabricated citations through text matching and adversarial detection.

### Evidence Grading

Located in [evidence.py:58-80](../apps/api/app/evidence.py#L58-L80):

```python
def evidence_grade(
    verified: bool,
    rrf_score: float,
    rrf_margin: float,
    overlap: float,
    reranker_score: float = 0.0,
) -> tuple[str, str]:
    """Grade evidence quality as A/B/C."""

    # Grade A: Semantic reranker high confidence (score 0-4, threshold 2.5)
    if reranker_score >= 2.5:
        return "A", "Strong (Semantic)"

    # Grade A: LLM verified + high retrieval signals
    if verified and rrf_score >= 0.5 and (overlap >= 0.3 or (overlap >= 0.15 and rrf_margin >= 0.02)):
        return "A", "Strong"

    # Grade B: Verified with moderate signals
    if verified and (rrf_score >= 0.4 or reranker_score >= 1.5) and overlap >= 0.1:
        return "B", "Moderate"

    # Grade C: Everything else
    return "C", "Weak"
```

### Citation Validation

Located in [evidence.py:139-188](../apps/api/app/evidence.py#L139-L188):

```python
def validate_citation(
    snippet: str | None,
    chunk: str | None,
    similarity_threshold: float = 0.90,
    strict_negation_check: bool = True,
) -> tuple[bool, float, str]:
    """
    Validate citation snippet matches source chunk.

    Returns: (is_valid, similarity_score, status)
    Status: "VALID" | "PARTIAL_MATCH" | "NOT_FOUND" | "NEGATION_MISMATCH"
    """
    # Fast path: exact substring match
    if norm_snippet in norm_chunk:
        return True, 1.0, "VALID"

    # Adversarial detection: negation mismatch
    if strict_negation_check and _has_negation_mismatch(snippet, chunk):
        return False, similarity, "NEGATION_MISMATCH"

    # Token-based similarity (Jaccard)
    similarity = text_similarity(norm_snippet, norm_chunk)

    if similarity >= 0.90:
        return True, similarity, "VALID"
    elif similarity >= 0.50:
        return False, similarity, "PARTIAL_MATCH"
    else:
        return False, similarity, "NOT_FOUND"
```

### Negation Mismatch Detection

Catches adversarial attempts to flip meaning in [evidence.py:115-136](../apps/api/app/evidence.py#L115-L136):

```python
_NEGATION_WORDS = frozenset({
    "not", "no", "never", "neither", "nobody", "nothing", "nowhere",
    "without", "hardly", "barely", "scarcely", "don", "doesn", "didn",
    "won", "wouldn", "couldn", "shouldn", "isn", "aren", "wasn", "weren",
})

def _has_negation_mismatch(snippet: str, chunk: str) -> bool:
    """
    Detect if negation differs between snippet and chunk.
    Catches attacks like: Source says "not guilty", LLM cites "guilty".
    """
    snippet_tokens = set(tokenize(snippet))
    chunk_tokens = set(tokenize(chunk))

    snippet_negations = snippet_tokens & _NEGATION_WORDS
    chunk_negations = chunk_tokens & _NEGATION_WORDS

    # Mismatch if one has negation and the other doesn't
    return bool(snippet_negations ^ chunk_negations)
```

---

## Security & Policy Enforcement

### Injection Detection

Located in [policy.py:1-48](../apps/api/app/policy.py#L1-L48):

```python
_INJECTION_PATTERNS = [
    r"ignore\s*(previous|prior|all|the|your)?\s*instructions?",
    r"system\s*prompt",
    r"developer\s*message",
    r"reveal\s*(your|the)?\s*prompt",
    r"jailbreak",
    r"bypass\s*(the|your|all)?\s*(rules?|filters?|restrictions?|safety)?",
    r"disregard\s*(previous|prior|all|the|your)?\s*(instructions?|rules?)?",
    r"override\s*(the|your|all)?\s*(instructions?|rules?|system)?",
    r"act\s*as\s*(if|a|an)",
    r"pretend\s*(you|to\s*be)",
    r"roleplay\s*as",
]

def _normalize_text(text: str) -> str:
    """Normalize unicode to catch homoglyph attacks."""
    # NFKC converts lookalike characters to ASCII
    normalized = unicodedata.normalize("NFKC", text)

    # Handle chars that survive NFKC (Cyrillic/Greek lookalikes)
    homoglyph_map = {
        "І": "I", "О": "O", "Ε": "E", "Α": "A", "Ρ": "P",  # Cyrillic/Greek
        "і": "i", "о": "o", "е": "e", "а": "a", "р": "p",
    }
    for char, replacement in homoglyph_map.items():
        normalized = normalized.replace(char, replacement)

    return re.sub(r"\s+", " ", normalized).lower()

def is_injection_attempt(question: str) -> bool:
    normalized = _normalize_text(question)
    return any(re.search(pat, normalized) for pat in _INJECTION_PATTERNS)
```

### Tenant/Matter Isolation

Every database query and search MUST include tenant/matter filters:

```python
# In retrieval.py - Azure Search filter
filters = [
    f"tenant_id eq '{tenant_id}'",    # FR-001
    f"matter_id eq '{matter_id}'",    # FR-002
]
filter_string = " and ".join(filters)

# In db.py - SQL queries
def load_chunks(docs_snapshot_id, tenant_id, matter_id):
    return session.query(DocChunk).filter(
        DocChunk.tenant_id == tenant_id,
        DocChunk.matter_id == matter_id,
        ...
    ).all()
```

---

## Provider Abstractions

The system uses pluggable interfaces for LLM, parser, search, and embeddings.

### LLM Client Interface

Located in [apps/api/app/llm/base.py](../apps/api/app/llm/base.py):

```python
@dataclass
class LLMResponse:
    content: str
    provider: str           # 'azure_openai', 'anthropic', 'openai', 'ollama'
    model: str              # 'gpt-4o', 'claude-3.5-sonnet', etc.
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int

class LLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate completion from the LLM."""
        pass

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def model(self) -> str: ...
```

**Available implementations:**
- `AzureOpenAIClient` - Azure OpenAI (GPT-4o, GPT-5)
- `AnthropicClient` - Claude models
- `OllamaClient` - Local models (Llama 3.2)

### Parser Client Interface

Located in [apps/api/app/parsers/base.py](../apps/api/app/parsers/base.py):

```python
@dataclass
class PageContent:
    page_number: int      # 1-indexed
    text: str
    char_start: int       # Absolute offset from document start
    char_end: int

@dataclass
class ParseResult:
    text: str                      # Full text
    pages: list[PageContent]       # Per-page with offsets
    tables: list[dict]             # Extracted tables
    metadata: dict                 # Title, author, page_count
    provider: str                  # 'pypdf', 'marker', 'llamaparse'
    parse_time_ms: int

class ParserClient(ABC):
    @abstractmethod
    async def parse(self, file_path: str, *, force_ocr: bool = False) -> ParseResult:
        """Parse document and return structured result."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return supported extensions: {"pdf", "png", "jpg", ...}"""
        pass
```

**Available implementations:**
- `PyPDFParser` - Lightweight, no OCR
- `MarkerParser` - Open source, OCR support
- `LlamaParseClient` - Cloud API, best for complex layouts

### Configuration-Driven Selection

```bash
# Environment variables select providers
LLM_PROVIDER=azure_openai    # azure_openai | anthropic | gemini | ollama
PARSER_PROVIDER=marker       # pypdf | marker | llamaparse
SEARCH_PROVIDER=pgvector     # pgvector | azure
EMBEDDINGS_MODE=local        # local | remote
```

---

## Document Disambiguation & Pinning

A recurring problem in multi-document Q&A: when a matter contains 30 similar PDFs (e.g., monthly claim reports), the system may retrieve chunks from the wrong document. The user knows which document they mean, but the retrieval pipeline doesn't.

### The Problem

```
User: "What was the total payout?"

Retrieval returns 5 candidates from 5 different documents — all with high scores,
all containing "total payout" text. The system picks the one with the highest RRF
score, which may be from the wrong monthly report.
```

Traditional RAG systems either guess (returning potentially wrong answers) or refuse (frustrating users who know exactly which document they want). Evidence-Bound solves this with **interactive disambiguation**.

### How It Works

The pipeline exposes `debug_candidates` — the top-3 scored chunks with their source documents — in every response. When the user sees candidates from multiple documents, they can click one to **pin** their query to that specific document.

```
┌──────────────────────────────────────────────────────────────┐
│ User asks question ──▶ Retrieval returns candidates          │
│                                                              │
│   Candidate 1: March_Report.pdf  (RRF 0.82) ◀── clickable  │
│   Candidate 2: April_Report.pdf  (RRF 0.79) ◀── clickable  │
│   Candidate 3: May_Report.pdf    (RRF 0.77) ◀── clickable  │
│                                                              │
│ User clicks "March_Report.pdf"                               │
│   ──▶ Re-runs query with doc_id="march-report-pdf"          │
│   ──▶ Pins document for follow-up questions                  │
│   ──▶ Shows "Pinned: March_Report.pdf" indicator             │
└──────────────────────────────────────────────────────────────┘
```

### Backend: doc_id Threading

The optional `doc_id` field is threaded through every layer of the retrieval pipeline:

```python
# schemas.py — Input validation with OData injection prevention
class AskRequest(BaseModel):
    doc_id: Optional[str] = None

    @field_validator("doc_id")
    def validate_doc_id(cls, v):
        # Same regex as docs_snapshot_id — prevents Azure Search OData injection
        if v and not re.match(r"^[a-zA-Z0-9][-_a-zA-Z0-9]{0,63}$", v):
            raise ValueError("doc_id must be alphanumeric with hyphens/underscores")
        return v

# retrieval.py — Adds filter to Azure Search OData $filter string
if doc_id:
    filters.append(f"doc_id eq '{doc_id}'")

# db.py — Adds WHERE clause to local PostgreSQL queries
if doc_id:
    stmt = stmt.where(Chunk.doc_id == doc_id)

# cache.py — doc_id in cache key prevents pinned/unpinned cross-contamination
key = f"{tenant_id}:{matter_id}:{docs_snapshot_id}:{question_hash}:{doc_id or ''}"
```

**Security:** The `doc_id` validator uses the same strict alphanumeric regex as `docs_snapshot_id`. This prevents OData filter injection — a critical concern since the value is interpolated directly into Azure AI Search `$filter` strings.

### Frontend: React State Timing

When a user clicks a candidate card, the system must (1) set the pinned document and (2) re-run the query scoped to it. A naive implementation has a race condition — `setState` is async, so the `doc_id` might not be set when `handleAsk` reads it.

The solution: pass `overrideDocId` directly to the function, bypassing React state:

```tsx
const handleCandidateSelect = async (docId: string, docName: string) => {
  setPinnedDocId(docId);
  setPinnedDocName(docName);
  // Pass docId directly — don't rely on setState timing
  const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
  if (lastUserMsg) await handleAsk(lastUserMsg.text, docId);
};

const handleAsk = async (question: string, overrideDocId?: string) => {
  const effectiveDocId = overrideDocId ?? pinnedDocId ?? undefined;
  // ... send effectiveDocId in request body
};
```

### Interview Talking Points

- **Why not just filter at upload time?** Because users don't know which document matters until they see the ambiguous results. This is a classic exploration vs. exploitation tradeoff — you want broad retrieval first, then let the user narrow.
- **Why not a dropdown?** Dropdown selection before asking is high-friction. Disambiguation after seeing results is lower cognitive load — the user sees *why* the system was confused.
- **Cache key design:** Including `doc_id` in the cache key means an unpinned query (`doc_id=None`) and a pinned query (`doc_id="doc-abc"`) produce different cache keys. Without this, a cached unpinned result could be incorrectly returned for a pinned query — a subtle correctness bug.

---

## Case Management & Auto-Naming

### The Problem

Law firm cases start with a file upload, but they need human-readable names. The original system defaulted every case to `"demo-matter"` — useless in production. Manually naming each case adds friction at the moment of highest urgency (initial document intake).

### Auto-Naming From First Upload

When the first document is uploaded to a matter, the system derives a display name from the filename:

```python
# document_service.py
def _display_name_from_filename(filename: str) -> str:
    """'Smith_Claim_2024.pdf' → 'Smith Claim 2024'"""
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    name = name.replace("_", " ").replace("-", " ")
    return name.strip().title() or filename

# Called after document insert
ensure_matter_exists(matter_id, tenant_id, display_name)
```

The `ensure_matter_exists` function is idempotent — it creates a row in the `matters` table only if one doesn't exist. Subsequent uploads to the same matter don't overwrite the name.

### Rename API

Users can rename matters via inline editing in the CasePicker dropdown:

```python
# PUT /v1/matters/{matter_id}/name
@router.put("/v1/matters/{matter_id}/name")
async def rename_matter(matter_id, body: RenameMatterRequest, ctx):
    # RBAC + matter access checks
    display_name = body.display_name.strip()
    if not display_name or len(display_name) > 100:
        raise HTTPException(400, "Display name must be 1-100 characters.")
    updated = update_matter_display_name(matter_id, ctx.tenant_id, display_name)
    if not updated:
        raise HTTPException(404, "Matter not found.")
    return {"matter_id": matter_id, "display_name": display_name}
```

### Composite Primary Key for Tenant Isolation

The `matters` table uses a composite PK `(matter_id, tenant_id)` so different tenants can independently use the same case slug (e.g., both might have a `smith-claim` matter):

```python
class Matter(Base):
    __tablename__ = "matters"
    matter_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)
```

The `list_matters_for_tenant` query LEFT JOINs this table and falls back to a slug-derived name when no matter row exists (backward compatible with pre-existing data):

```sql
SELECT documents.matter_id, COUNT(*) as doc_count,
       MAX(documents.ingested_at_utc) as latest_ingested,
       (SELECT d2.docs_snapshot_id FROM documents d2 ...),
       m.display_name as matter_display_name
FROM documents
LEFT JOIN matters m ON m.matter_id = documents.matter_id
  AND m.tenant_id = documents.tenant_id
WHERE documents.tenant_id = :tenant_id AND documents.status = 'ready'
GROUP BY documents.matter_id, m.display_name
```

### Document Strip Overflow

With 30+ documents in a matter, the horizontal document strip scrolls off-screen with no indication. The `DocumentStrip` component shows the first 5 documents as pills, then a "+N more" button that expands the full list:

```tsx
const MAX_VISIBLE = 5;
const visibleDocs = expanded ? documents : documents.slice(0, MAX_VISIBLE);
const overflowCount = documents.length - MAX_VISIBLE;

{overflowCount > 0 && !expanded && (
  <button onClick={() => setExpanded(true)}>
    +{overflowCount} more
  </button>
)}
```

This is a simple but important UX detail — without it, users don't know their other documents exist.

### Interview Talking Points

- **Why auto-name from filename?** Law firm filenames are descriptive by convention (`Smith_Claim_2024.pdf`). Deriving case names from the first upload eliminates a manual step while producing names that are 80%+ correct for the domain.
- **Why composite PK?** A single `matter_id` PK would create cross-tenant collisions — tenant A's `smith-claim` would block tenant B from using the same slug. The composite PK `(matter_id, tenant_id)` is the standard pattern for multi-tenant data.
- **Why LEFT JOIN?** Backward compatibility. Pre-existing matters (created before the `matters` table existed) have no row. The LEFT JOIN + COALESCE-style fallback means the system gracefully degrades to slug-derived names instead of breaking.

---

## Observability Stack

The system runs three parallel observability layers, each serving a different audience and failure mode:

| Layer | Tool | Purpose | Audience |
|-------|------|---------|----------|
| **LLM Tracing** | Langfuse | Token usage, prompt debugging, model comparison | AI/ML engineers |
| **Infrastructure** | OpenTelemetry + Azure Monitor | Request latency, error rates, resource utilization | DevOps/SRE |
| **Business Metrics** | PostgreSQL `telemetry` table + `/v1/metrics` | Cost, refusal rates, cache performance | Product/Business |

### Layer 1: Langfuse LLM Observability

Every `/ask` request creates a Langfuse trace with nested observations — a waterfall of every sub-operation:

```
execute_ask                     (trace root — tenant/session context)
  |-- hybrid_search             (mode, result_count, latency)
  |   +-- embed_texts_with_usage  (model, tokens, embeddings_mode)
  +-- verify_relevance          (model, tokens, verdict)
      +-- call_openai           (generation span — model, tokens)
```

The `@observe` decorator from Langfuse wraps each function. When Langfuse is disabled, a no-op decorator is substituted — zero overhead, no code changes:

```python
# otel.py — decorator factory with graceful fallback
def get_observe_decorator():
    if observe is not None and LANGFUSE_ENABLED:
        return observe
    return _noop_observe  # Identity decorator, no tracing

# ask_service.py — used identically whether Langfuse is on or off
_observe = get_observe_decorator()

@_observe(name="execute_ask", capture_input=False, capture_output=False)
def execute_ask(payload, ...) -> AskResponse:
    ...
```

Trace metadata is enriched via `safe_update_observation()` and `safe_update_trace()` — both are no-ops if Langfuse is disabled, and wrapped in try/except to never break the request pipeline.

### Layer 2: OpenTelemetry + Azure Monitor

Five custom OTEL metrics are emitted on every request via `record_request_metrics()`:

```python
# otel.py — custom metrics (NFR-022)
"docqa.request.count"       # Counter: total requests, labeled by component/refusal/cache
"docqa.request.latency_ms"  # Histogram: latency distribution per component
"docqa.tokens.total"        # Counter: tokens consumed (input/output, per component)
"docqa.cache.hit"           # Counter: cache hit count by cache type
"docqa.cost.usd"            # Counter: estimated cost in USD per component
```

LLM calls additionally set GenAI semantic convention attributes on the active span:

```python
# otel.py — set_genai_span_attributes()
span.set_attribute("gen_ai.system", "azure_openai")
span.set_attribute("gen_ai.request.model", "gpt-4o")
span.set_attribute("gen_ai.usage.prompt_tokens", 800)
span.set_attribute("gen_ai.usage.completion_tokens", 50)
span.set_attribute("llm.latency_ms", 1200)
span.set_attribute("llm.request_id", "req-abc123")
```

### Layer 3: Telemetry Table + Metrics Endpoint

Every request writes a row to the `telemetry` PostgreSQL table with full request metadata:

```python
# telemetry.py — record_telemetry()
insert_telemetry(Telemetry(
    request_id, tenant_id, matter_id, docs_snapshot_id,
    prompt_version, retrieval_version, model_id, parser_mode,
    timestamp_utc, latency_ms, tokens_in, tokens_out, cost_est,
    cache_hit, refusal_code, failure_label, trace_metadata,  # JSON blob
    langfuse_trace_id,                                       # Cross-links to Langfuse
))
```

The `GET /v1/metrics` endpoint computes aggregates over a 24-hour window:

```json
{
  "p50_latency_ms": 1200,
  "p95_latency_ms": 4500,
  "p99_latency_ms": 6800,
  "max_latency_ms": 9200,
  "total_requests": 342,
  "avg_cost_per_query": 0.0042,
  "refusals_by_code": {"LOW_RETRIEVAL_CONFIDENCE": 12, "INJECTION_DETECTED": 2},
  "cache_hit_rate": 0.15,
  "latency_by_component": {
    "retrieval_ms": 450.2,
    "verification_ms": 2100.5,
    "llm_ms": 2100.5,
    "overhead_ms": 35.1
  }
}
```

---

## Performance & Latency Controls

### End-to-End Timing

Every request is timed with `time.perf_counter()` from the first line of `execute_ask()`:

```python
# ask_service.py
start_time = time.perf_counter()
# ... entire pipeline ...
latency_ms = int((time.perf_counter() - start_time) * 1000)
```

This captures the true wall-clock time including all sub-operations, serialization, and overhead. The value is recorded in both the `telemetry` table and OTEL metrics on every request — including refusals and cache hits.

### Sub-Component Latency Breakdown

Each pipeline phase is individually timed and stored in `trace_metadata.latency_breakdown`:

```python
# ask_service.py — sub-component timing (NFR-011)
retrieval_start = time.perf_counter()
results, embedding_usage = retrieval.hybrid_search(...)
retrieval_ms = int((time.perf_counter() - retrieval_start) * 1000)

verification_start = time.perf_counter()
# ... verification loop (1-3 LLM calls) ...
verification_ms = int((time.perf_counter() - verification_start) * 1000)

# Stored per-request for analysis
trace_metadata["latency_breakdown"] = {
    "retrieval_ms": retrieval_ms,       # Embedding + search (200-1500ms)
    "verification_ms": verification_ms, # LLM relevance check (500-3000ms)
    "llm_ms": verification_ms,          # Primary LLM call
    "overhead_ms": total - (retrieval + verification),  # Serialization, caching
}
```

### Latency Target

| Metric | Target | Config | Default |
|--------|--------|--------|---------|
| p95 end-to-end | < 8000ms | `DOCQA_LATENCY_TARGET_MS` | 8000 |

The verification step dominates latency (1-3 LLM calls to validate chunk relevance). The latency budget:

```
Retrieval (embedding + search):  200-1500ms  (~30%)
Verification (LLM):             500-3000ms  (~55%)
Evidence grading:                    <10ms   (~0%)
Overhead:                         10-50ms    (~1%)
                                ────────────
Total p95 target:                   <8000ms
```

### Percentile Calculation

The `compute_metrics()` function uses linear interpolation for percentiles:

```python
# telemetry.py — _percentile()
def _percentile(values: list[int], pct: int) -> int:
    k = (len(values) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(values) - 1)
    if f == c: return values[f]
    return int(values[f] * (c - k) + values[c] * (k - f))
```

---

## Caching Architecture

Two independent LRU caches reduce cost and latency:

### Embedding Cache

**Problem:** Identical questions produce identical embeddings, but Azure OpenAI charges per token.

```python
# cache.py — EmbeddingCache
class EmbeddingCache:
    """LRU cache for question embeddings. Thread-safe."""
    def __init__(self, max_size: int = 5000):
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()  # Thread-safe under concurrent requests
```

| Setting | Default | Config |
|---------|---------|--------|
| Enabled | Yes | `EMBEDDING_CACHE_ENABLED` |
| Max entries | 5000 | `EMBEDDING_CACHE_MAX_SIZE` |
| TTL | None (deterministic) | N/A |
| Key | SHA-256 of question text | N/A |

No TTL needed because the same text always produces the same embedding. The `stats()` method exposes hits, misses, and size via `/v1/metrics`.

### Query Result Cache

**Problem:** Repeated identical questions waste LLM tokens and latency.

```python
# cache.py — QueryResultCache
class QueryResultCache:
    """LRU cache for Q&A responses with tenant isolation and TTL."""
    def _make_key(self, tenant_id, matter_id, docs_snapshot_id, question_hash,
                  doc_id=None):
        return f"{tenant_id}:{matter_id}:{docs_snapshot_id}:{question_hash}:{doc_id or ''}"
```

| Setting | Default | Config |
|---------|---------|--------|
| Enabled | No (opt-in) | `QUERY_CACHE_ENABLED` |
| Max entries | 500 | `QUERY_CACHE_MAX_SIZE` |
| TTL | 3600s | `QUERY_CACHE_TTL_SECONDS` |
| Key | `tenant:matter:snapshot:question_hash:doc_id` | N/A |

The key includes `docs_snapshot_id`, so re-indexing documents automatically invalidates stale cached answers. The `doc_id` segment ensures pinned queries never return cached unpinned results (and vice versa). Tenant isolation is enforced at the key level — cross-tenant cache hits are structurally impossible.

### Thread Safety

Both caches use `threading.Lock` around all reads and writes. Under 50 concurrent requests (NFR-012), this has been validated with `ThreadPoolExecutor` tests. The lock granularity is per-cache — retrieval and caching never block each other.

### Per-Instance Tradeoffs

Caches are in-memory per-process. Under horizontal scaling:
- Each Azure Container Apps replica warms its own cache independently
- Cache hit rate decreases with more replicas (acceptable tradeoff for availability)
- No shared state means no cache invalidation complexity

---

## Cost Tracking & Estimation

Every request tracks cost at component level, stored in `trace_metadata.cost_breakdown`:

```python
# services/cost.py
def estimate_cost(prompt_tokens, completion_tokens, input_per_1k, output_per_1k):
    return (prompt_tokens / 1000) * input_per_1k + (completion_tokens / 1000) * output_per_1k

# Per-component breakdown accumulated during request
cost_breakdown = {
    "embeddings": {"prompt_tokens": 50, "cost_est": 0.000005, "source": "azure_openai"},
    "azure_search": {"cost_est": 0.001},
    "verification": {"prompt_tokens": 800, "completion_tokens": 50, "cost_est": 0.0004},
}
```

Cost rates are configurable via environment:

| Cost Item | Config | Default |
|-----------|--------|---------|
| LLM input (per 1K tokens) | `DOCQA_MODEL_COST_INPUT_PER_1K` | $0.0004 |
| LLM output (per 1K tokens) | `DOCQA_MODEL_COST_OUTPUT_PER_1K` | $0.0016 |
| Embeddings (per 1K tokens) | `DOCQA_EMBEDDINGS_COST_PER_1K` | $0.0001 |
| Azure Search (per query) | `AZURE_SEARCH_COST_PER_QUERY` | $0.001 |

When real token counts aren't available (e.g., cached embeddings), the system estimates at ~4 chars per token and flags `"usage_fallback": true` in the trace metadata — so downstream analytics know the cost is approximate.

The `avg_cost_per_query` metric in `/v1/metrics` aggregates across the 24-hour window.

---

## Rate Limiting & Concurrency

### Rate Limiting via slowapi

Rate limits are applied per-IP using [slowapi](https://github.com/laurentS/slowapi) decorators:

```python
# routers/ask.py
@router.post("/v1/ask")
@limiter.limit(RATE_LIMIT_QUERY)   # 20/minute per IP
async def ask(request: Request, ...):
    ...

# routers/docs.py
@router.post("/v1/docs/upload")
@limiter.limit(RATE_LIMIT_UPLOAD)  # 10/minute per IP
async def upload_doc(request: Request, ...):
    ...
```

| Endpoint | Default Limit | Config |
|----------|---------------|--------|
| `/v1/ask` | 20/minute | `RATE_LIMIT_QUERY` |
| `/v1/docs/upload` | 10/minute | `RATE_LIMIT_UPLOAD` |
| All other routes | 100/minute | `RATE_LIMIT_DEFAULT` |
| Kill switch | On | `RATE_LIMIT_ENABLED` |

Exceeded limits return `HTTP 429` with `Retry-After` header. The limiter is conditionally created — when `RATE_LIMIT_ENABLED=0`, decorators are no-ops and no 429s are ever returned.

### Concurrency Model

FastAPI runs on uvicorn. Sync route handlers (most of ours) execute in a thread pool managed by Starlette. The system handles 50+ concurrent requests without deadlocks:

```python
# Validated by test_performance.py::TestConcurrentRequests
with ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(make_request) for _ in range(50)]
    results = [f.result() for f in as_completed(futures)]
assert len(results) == 50
assert all(code == 200 for code in results)
```

### Horizontal Scaling

| Setting | Value | Rationale |
|---------|-------|-----------|
| Min replicas | 1 | Always-on for latency |
| Max replicas | 4 | Handles 50+ concurrent users |
| Scale trigger | Concurrent requests > 15 | Proactive scale-out |
| CPU/instance | 2 vCPU | Sync processing headroom |
| Memory/instance | 4 GiB | Embedding cache fits |

---

## PII Redaction

Law firm document Q&A handles confidential client data. The system enforces PII safety at every observability boundary:

### What's Never Logged

| Data | Where Blocked | How |
|------|---------------|-----|
| Raw question text | Langfuse, OTEL spans, structured logs | `capture_input=False` on all `@observe` decorators |
| Raw answer text | Langfuse, OTEL spans, structured logs | `capture_output=False` on all `@observe` decorators |
| Document content/snippets | Langfuse metadata | Excluded from `redact_for_langfuse()` |
| Document names | Langfuse metadata | May contain client names; excluded from metadata |
| Client/tenant names | All logs | Only `tenant_id` (UUID) is logged, never names |

### What IS Logged (Safe Metrics Only)

```python
# otel.py — redact_for_langfuse()
def redact_for_langfuse(*, question_len, answer_len, citation_count,
                        evidence_grade, evidence_label, refusal_code,
                        verification_status, doc_count) -> dict:
    return {
        "question_len": question_len,       # Length, not content
        "answer_len": answer_len,           # Length, not content
        "citation_count": citation_count,   # Count, not text
        "evidence_grade": evidence_grade,   # "A"/"B"/"C"
        "evidence_label": evidence_label,   # "Strong"/"Moderate"/"Weak"
        "refusal_code": refusal_code,       # Enum value
        "verification_status": verification_status,
        "doc_count": doc_count,             # Count, not names
    }
```

This is compliant with NFR-004 (No PII in logs). The principle: log **metrics about** the data, never the data itself.

---

## Graceful Degradation

Every external dependency is optional. The system runs with or without each one:

| Dependency | When Missing | Mechanism |
|------------|--------------|-----------|
| **Langfuse** | `@observe` becomes identity decorator; `safe_update_*` are no-ops | `get_observe_decorator()` returns `_noop_observe` |
| **OTEL SDK** | `span()` yields `None`; `record_request_metrics()` is no-op | Conditional `if _TRACER` / `if _REQUEST_COUNTER` checks |
| **Azure Monitor** | OTEL spans collected but not exported | `setup_otel()` returns early if no connection string |
| **Azure AI Search** | Falls back to local pgvector hybrid search | `_azure_enabled()` check in `retrieval.py` |
| **Embedding cache** | Embeddings computed on every request (higher cost, same correctness) | `EMBEDDING_CACHE_ENABLED=0` |
| **Query cache** | Full pipeline runs on every request (higher cost, same correctness) | `QUERY_CACHE_ENABLED=0` |
| **Rate limiting** | No 429s returned; unlimited requests | `RATE_LIMIT_ENABLED=0` |

The pattern is consistent: every `safe_*` function wraps calls in `try/except` that logs debug-level and continues. The request pipeline **never breaks** due to an observability failure.

```python
# Pattern used throughout otel.py — defensive, never breaks
def safe_update_observation(*, model=None, usage=None, metadata=None):
    if not _LANGFUSE_INITIALIZED or langfuse_context is None:
        return  # No-op
    try:
        langfuse_context.update_current_observation(**kwargs)
    except Exception as exc:
        logger.debug("Langfuse update failed: %s", exc)  # Log and continue
```

---

## Test Architecture

### Test Categories

| Category | Location | Purpose | Run In CI |
|----------|----------|---------|-----------|
| Unit tests | `tests/test_*.py` | Component correctness | Yes |
| Performance tests | `tests/test_performance.py` | Latency targets, concurrency, rate limits | Yes |
| Telemetry tests | `tests/test_telemetry.py` | Metrics computation, OTEL spans | Yes |
| Rate limit tests | `tests/test_rate_limit.py` | slowapi integration | Yes |
| Cache tests | `tests/test_cache.py` | Thread-safety, LRU eviction, TTL | Yes |
| Golden queries | `evals/golden.jsonl` | Retrieval/answer quality regression | Yes |
| Load tests | `tests/loadtest/locustfile.py` | 50-user sustained load | Manual only |

### Performance Test Suite (`test_performance.py`)

Eight tests covering NFR-011 (latency) and NFR-012 (concurrency):

```python
# Config validation
test_latency_target_config_exists       # LATENCY_TARGET_MS == 8000

# Metrics computation
test_compute_metrics_p50_p95_p99_calculation  # Percentile math on 100 rows
test_compute_metrics_empty_rows               # Zero defaults on empty window
test_compute_metrics_latency_by_component     # Component averaging

# Endpoint integration
test_metrics_endpoint_returns_enhanced_fields  # /v1/metrics response shape

# Pipeline integration
test_latency_breakdown_stored                  # trace_metadata has latency_breakdown

# Concurrency (NFR-012)
test_concurrent_requests_no_crash              # 50 ThreadPoolExecutor requests

# Rate limiting
test_rate_limit_returns_429                    # 429 after exceeding limit
```

### TDD Enforcement

All features follow RED → GREEN → REFACTOR:

1. **RED**: Write failing test that proves the test works
2. **GREEN**: Write minimum code to pass
3. **REFACTOR**: Clean up while maintaining green

Example from NFR-011: `test_latency_breakdown_stored` was written before the sub-component timing code in `ask_service.py`. The test mocks the entire ask pipeline, calls `execute_ask()`, and asserts that `record_telemetry` was called with `trace_metadata` containing a `latency_breakdown` dict with `retrieval_ms`, `verification_ms`, `llm_ms`, and `overhead_ms` — all non-negative integers.

### Load Testing

For manual performance validation against staging/production:

```bash
# Install
pip install locust

# Run against staging (50 users, 5 users/sec spawn rate)
locust -f tests/loadtest/locustfile.py --host=https://YOUR_API_URL -u 50 -r 5

# Headless mode for CI integration
locust -f tests/loadtest/locustfile.py --host=https://YOUR_API_URL \
    -u 50 -r 5 --run-time 5m --headless --csv results/loadtest
```

Baseline targets:

| Scenario | Users | Expected p95 |
|----------|-------|-------------|
| Light | 1 | < 4000ms |
| Normal | 10 | < 6000ms |
| Peak (NFR-012 target) | 50 | < 8000ms |
| Stress | 100 | < 12000ms (graceful degradation) |

---

## Data Model

### API Request/Response

Located in [packages/shared/python/evidence_shared/schemas.py](../packages/shared/python/evidence_shared/schemas.py):

```python
class AskRequest(BaseModel):
    question: str
    docs_snapshot_id: Optional[str] = None
    doc_id: Optional[str] = None     # Pin query to a single document
    top_k: Optional[int] = 8

class Citation(BaseModel):
    citation_index: int     # Maps to [1], [2] markers in answer
    doc_id: str
    doc_name: str
    page_num: int
    page_end: int
    char_start: int         # Exact character offset
    char_end: int
    chunk_id: str
    snippet: str            # Verbatim text from source
    score: float

class EvidenceSupport(BaseModel):
    verdict: str            # "VERIFIED" | "UNVERIFIED"
    evidence_grade: str     # "A" | "B" | "C"
    evidence_label: str     # "Strong" | "Moderate" | "Weak"
    support_count: int
    top_rrf_score: Optional[float]
    azure_reranker_score: Optional[float]
    overlap_score: float
    supporting_span: str
    confidence_threshold: float  # Threshold used for refusal decision

class RefusalCode(str, Enum):
    NO_SUPPORTING_EVIDENCE = "NO_SUPPORTING_EVIDENCE"
    LOW_RETRIEVAL_CONFIDENCE = "LOW_RETRIEVAL_CONFIDENCE"
    INJECTION_DETECTED = "INJECTION_DETECTED"
    POLICY_REFUSAL = "POLICY_REFUSAL"

class AskResponse(BaseModel):
    request_id: str
    answer_text: Optional[str]           # None if refused
    citations: Optional[List[Citation]]   # Citation markers [1], [2]
    refusal_code: Optional[RefusalCode]   # Why refused (if applicable)
    reason: Optional[str]                 # Human-readable refusal reason
    evidence: Optional[EvidenceSupport]   # Verification metadata
```

### Database Schema (Core Tables)

```sql
-- Document chunks with embeddings
doc_chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    tenant_id UUID REFERENCES tenants(id),     -- FR-001: Isolation
    matter_id UUID REFERENCES matters(id),     -- FR-002: Isolation
    page_number INT NOT NULL,
    char_start INT NOT NULL,                   -- Character offset
    char_end INT NOT NULL,
    text TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding vector(1536)                     -- pgvector
);

-- Full-text search (BM25 hybrid)
ALTER TABLE doc_chunks ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX idx_chunks_fts ON doc_chunks USING gin(search_vector);

-- Vector similarity search
CREATE INDEX idx_chunks_embedding ON doc_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## Example: Full Request Trace

```
POST /v1/ask
{
  "question": "What is the termination notice period?",
  "docs_snapshot_id": "snap_abc123"
}

1. Policy Check: "termination notice period" → PASS (no injection patterns)

2. Embedding: Generate 1536-dim vector for query
   └─ Cost: 0.0001 tokens

3. Hybrid Search (Azure AI Search):
   └─ Filter: tenant_id='t1' AND matter_id='m1' AND docs_snapshot_id='snap_abc123'
   └─ Results:
      [0] chunk_id=c1, azure_score=12.4, reranker_score=3.2
      [1] chunk_id=c2, azure_score=10.1, reranker_score=2.8
      [2] chunk_id=c3, azure_score=8.7, reranker_score=1.9

4. Confidence Filter: threshold=0.7 (azure_reranker_score >= 2.0)
   └─ [0] PASS (3.2), [1] PASS (2.8), [2] FAIL (1.9)

5. LLM Verification (chunk c1):
   └─ Prompt: "Does this chunk contain the answer?"
   └─ Response: {"verdict": "YES", "span": "30 days written notice", "start": 142, "end": 164, "reason": "FOUND"}
   └─ Span check: chunk_text[142:164] == "30 days written notice" ✓
   └─ Blocklist check: No injection patterns ✓
   └─ Status: VERIFIED

6. Evidence Grade:
   └─ reranker_score=3.2 >= 2.5 → Grade A (Strong Semantic)

7. Response:
{
  "request_id": "req_xyz",
  "answer_text": "According to Employment Agreement (page 12) [1], 30 days written notice",
  "citations": [{
    "citation_index": 1,
    "doc_name": "Employment Agreement",
    "page_num": 12,
    "char_start": 142,
    "char_end": 164,
    "snippet": "30 days written notice",
    "score": 3.2
  }],
  "evidence": {
    "verdict": "VERIFIED",
    "evidence_grade": "A",
    "evidence_label": "Strong (Semantic)",
    "confidence_threshold": 0.7
  }
}
```

---

## Summary

Evidence-Bound enforces evidence-grounded answers through:

**Core RAG Pipeline**
1. **Hybrid Retrieval** — BM25 + vector + semantic reranking finds relevant chunks
2. **Confidence Gating** — Low-confidence results trigger refusal
3. **LLM Verification** — Second pass confirms chunk answers the question
4. **Citation Validation** — Spans must exist verbatim in source text
5. **Adversarial Detection** — Negation mismatch, injection patterns, homoglyph normalization, blocklists
6. **Tenant Isolation** — Every query filtered by tenant_id + matter_id

**UX & Document Interaction**
7. **Document Disambiguation** — Ambiguous queries expose top candidates; users click to pin and re-query scoped to a specific document
8. **Doc Pinning** — Optional `doc_id` threads through the entire pipeline (schema, retrieval, cache key), with OData injection validation
9. **Case Auto-Naming** — Matters named from first uploaded filename; editable via inline rename with tenant-isolated composite PK
10. **Overflow-Aware UI** — Document strips, candidate cards, and case pickers handle 30+ items without losing content off-screen

**Production Engineering**
11. **Three-Layer Observability** — Langfuse (LLM tracing) + OpenTelemetry (infrastructure) + telemetry table (business metrics)
12. **Sub-Component Latency Tracking** — Per-request breakdown: retrieval, verification, LLM, overhead (p50/p95/p99)
13. **Thread-Safe LRU Caching** — Embedding cache (5K entries) + query result cache (tenant-isolated, TTL, auto-invalidated on re-index, doc_id-aware)
14. **Per-Request Cost Estimation** — Component-level cost breakdown with configurable rates
15. **Rate Limiting** — Per-IP slowapi decorators on all routes (20/min query, 10/min upload)
16. **PII Redaction** — Raw questions, answers, and document names never reach logs or traces
17. **Graceful Degradation** — Every external dependency is optional; the pipeline never breaks due to observability failures
18. **Performance Test Suite** — 8 automated tests: percentile math, concurrency (50 threads), rate limit enforcement, latency breakdown validation

The system refuses to answer rather than risk hallucination or fabricated citations. And when it does answer, every aspect of the request — latency, cost, tokens, cache behavior, and evidence quality — is tracked, measured, and available for audit.
