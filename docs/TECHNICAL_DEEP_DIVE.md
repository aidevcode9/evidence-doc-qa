# Evidence-Bound: Technical Deep Dive

> How Evidence-Grounded Document Q&A Works Under the Hood

**Audience:** Engineers, architects, and technical evaluators who want to understand the system internals.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Request Flow Architecture](#request-flow-architecture)
3. [Retrieval Pipeline](#retrieval-pipeline)
4. [Evidence Verification](#evidence-verification)
5. [Citation Validation](#citation-validation)
6. [Security & Policy Enforcement](#security--policy-enforcement)
7. [Provider Abstractions](#provider-abstractions)
8. [Observability](#observability)
9. [Data Model](#data-model)

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
def _azure_search(question, docs_snapshot_id, query_embedding, tenant_id, matter_id):
    # Build isolation filter (REQUIRED for FR-001, FR-002)
    filters = [
        f"tenant_id eq '{tenant_id}'",
        f"matter_id eq '{matter_id}'",
    ]
    if docs_snapshot_id:
        filters.append(f"docs_snapshot_id eq '{docs_snapshot_id}'")

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

## Observability

### OpenTelemetry Integration

Located in [otel.py:78-127](../apps/api/app/otel.py#L78-L127):

```python
@contextmanager
def span(name: str, **attrs: Any) -> Generator[Any, None, None]:
    """Create an OTEL span with attributes."""
    if not _TRACER or not OTEL_ENABLED:
        yield None
        return
    with _TRACER.start_as_current_span(name) as s:
        for key, value in attrs.items():
            if value is not None:
                s.set_attribute(key, value)
        yield s

def setup_otel(app: FastAPI) -> None:
    """Initialize OpenTelemetry with Azure Monitor exporter."""
    resource = Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = AzureMonitorTraceExporter(connection_string=connection_string)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    URLLibInstrumentor().instrument()
```

### Langfuse LLM Observability

Located in [otel.py:130-189](../apps/api/app/otel.py#L130-L189):

```python
def get_observe_decorator():
    """Get Langfuse @observe decorator or no-op fallback."""
    if observe is not None and LANGFUSE_ENABLED:
        return observe
    return _noop_observe  # Graceful degradation

# Usage in ask_service.py:
@_observe(name="execute_ask", capture_input=False, capture_output=False)
def execute_ask(payload: AskRequest, ...) -> AskResponse:
    ...

# Usage in verification.py:
@_observe(name="verify_relevance", capture_input=False, capture_output=False)
def verify_relevance(question: str, chunk_text: str, ...) -> tuple:
    ...

def flush_langfuse() -> None:
    """Flush traces on shutdown - BOTH decorator context AND client."""
    if langfuse_context is not None:
        langfuse_context.flush()  # @observe decorator buffer
    if _langfuse_client is not None:
        _langfuse_client.flush()  # Manual tracing buffer
```

---

## Data Model

### API Request/Response

Located in [packages/shared/python/evidence_shared/schemas.py](../packages/shared/python/evidence_shared/schemas.py):

```python
class AskRequest(BaseModel):
    question: str
    docs_snapshot_id: Optional[str] = None
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

1. **Hybrid Retrieval** - BM25 + vector + semantic reranking finds relevant chunks
2. **Confidence Gating** - Low-confidence results trigger refusal
3. **LLM Verification** - Second pass confirms chunk answers the question
4. **Citation Validation** - Spans must exist verbatim in source text
5. **Adversarial Detection** - Negation mismatch, injection patterns, blocklists
6. **Tenant Isolation** - Every query filtered by tenant_id + matter_id

The system refuses to answer rather than risk hallucination or fabricated citations.
