# RAG Harness: Extracting a Trusted Foundation from Evidence-Bound

**Date:** 2026-03-31
**Goal:** Extract a repeatable, tested, production-grade RAG harness from the Evidence-Bound codebase that can serve as a starting point for any domain.

---

## 1. Scorecard: Evidence-Bound vs Enterprise RAG Blueprint

Scoring our current system against each principle from the enterprise RAG blueprint.

| # | Blueprint Principle | Evidence-Bound Today | Score | Gap |
|---|-------------------|---------------------|-------|-----|
| 1 | **Document Quality Router** -- route by doc quality, not assumption | Parser abstraction (3 providers), OCR detection, min-text-chars validation. But: same pipeline for all quality levels. No routing by scan quality or structure. | 4/10 | No quality classifier. Scanned 1995 invoices and clean digital PDFs hit the same chunking pipeline. |
| 2 | **Metadata > Vectors** -- structured filters beat fancier embeddings | Tenant/matter filtering in Azure Search OData. Doc-level metadata extraction (title, author, pages). But: no metadata used in retrieval scoring. Filters are identity-based, not content-based. | 5/10 | No doc_type, date, or tag filtering in search. Metadata extracted but not indexed as filterable fields. |
| 3 | **Tables as Structured Objects** -- dual embedding for tables | Zero table handling. Chunking treats tables as text. Financial tables get shredded into token soup. | 1/10 | No table detection, no structured extraction, no dual embedding. This is the biggest gap for legal contracts with indemnification schedules. |
| 4 | **Hybrid Retrieval** -- BM25 + Dense + Graph | BM25 + vector with RRF fusion. Azure semantic reranker as cross-encoder. Local reranker fallback. | 7/10 | No GraphRAG for entity relationships or cross-document multi-hop. Legal: "find all clauses referencing Party B across 50 documents" fails. |
| 5 | **Hierarchy / TreeRAG** -- respect document structure | Flat chunking with page offsets and char positions. No document hierarchy (section, subsection, clause). | 2/10 | Legal documents are deeply hierarchical (Article > Section > Clause > Sub-clause). Flat chunking loses this entirely. |
| 6 | **Agentic Loop** -- hypothesize, retrieve, verify, refine | Retrieve + verify (parallel LLM verification). Auto-verify fast path. But: single-shot. No refinement if first retrieval misses. No query rewriting. | 5/10 | No re-retrieval, no query decomposition, no "the first answer wasn't good enough, let me try differently." |
| 7 | **Retrieval as Security Boundary** -- chunks are untrusted | Injection gate pre-LLM. Chunk marked `<chunk>` (untrusted) in verifier prompt. Span blocklist. Homoglyph normalization. | 8/10 | Strongest area. Missing: content hash verification (confirm chunk wasn't tampered between index and retrieval). |
| 8 | **Observability + Citations from Day 1** | Langfuse full pipeline tracing. OTEL custom metrics. Per-request cost. Citation validation with 90% similarity threshold. Negation flip detection. | 9/10 | This is where Evidence-Bound shines. Built in from the start, not retrofitted. |

**Overall: 5.1/10** -- Strong on observability, citations, and security. Weak on document intelligence (tables, hierarchy, quality routing).

---

## 2. What's Already Reusable (the 70% that's generic)

Evidence-Bound has five clean abstraction layers that are immediately extractable:

### Provider Interfaces (all have ABC base + factory)

| Interface | Implementations | Status |
|-----------|----------------|--------|
| `SearchClient` | Azure AI Search, Local (BM25+vector) | Production-tested |
| `LLMClient` | Azure OpenAI, Anthropic, Gemini, Ollama | 4 providers shipped |
| `EmbeddingClient` | Azure OpenAI, Local (hash) | Production-tested |
| `ParserClient` | PyPDF, Marker (OCR), LlamaParse (cloud) | 3 providers shipped |
| `RerankerClient` | Local (term+phrase analysis) | Extensible |

### Generic Infrastructure

| Component | File | Reusable? |
|-----------|------|-----------|
| BM25 scoring engine | `retrieval.py` | 100% -- textbook BM25 with configurable k1, b |
| RRF fusion | `retrieval.py` | 100% -- standard reciprocal rank fusion |
| Embedding cache (LRU) | `cache.py` | 100% -- thread-safe, stats tracking |
| Query result cache (TTL) | `cache.py` | 100% -- tenant-scoped, configurable |
| Injection detection | `policy.py` | 100% -- 22 regex patterns + homoglyph normalization |
| Citation validation | `evidence.py` | 90% -- similarity check + negation detection |
| httpx connection pool | `http_client.py` | 95% -- singleton, HTTP/2, configurable limits |
| Cost tracking | `cost.py` | 100% -- token-based, per-component breakdown |
| OTEL + Langfuse setup | `otel.py` | 95% -- GenAI semantic conventions, PII-safe |
| Parallel verification | `ask_service.py` | 80% -- ThreadPoolExecutor pattern |
| Chunking with offsets | `ingestion.py` | 70% -- page/char offset preservation |

---

## 3. The Harness Architecture

### Core Idea

The harness is a **configured pipeline**, not a framework. You compose it from interchangeable providers and plug in domain-specific logic at defined extension points.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        RAG HARNESS CORE                              │
│                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌───────────┐   ┌────────────────┐  │
│  │ Ingest   │──>│  Store   │──>│ Retrieve  │──>│   Generate     │  │
│  │          │   │          │   │           │   │                │  │
│  │ Parse    │   │ Chunks   │   │ Hybrid    │   │ LLM + Verify   │  │
│  │ Chunk    │   │ Vectors  │   │ Search    │   │ Grade + Cite   │  │
│  │ Embed    │   │ Metadata │   │ Rerank    │   │ Validate       │  │
│  └──────────┘   └──────────┘   └───────────┘   └────────────────┘  │
│       │              │              │                  │             │
│  ┌────┴────┐   ┌─────┴────┐  ┌─────┴─────┐    ┌──────┴──────┐     │
│  │ Parser  │   │ Search   │  │ Embedding │    │ LLM Client  │     │
│  │ Client  │   │ Client   │  │ Client    │    │ (4 provdrs) │     │
│  │ (3 imp) │   │ (2 imp)  │  │ (2 imp)   │    │ + Reranker  │     │
│  └─────────┘   └──────────┘  └───────────┘    └─────────────┘     │
│                                                                      │
│  CROSS-CUTTING:                                                      │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Security   │ │ Observ-    │ │ Caching  │ │ Cost Tracking     │  │
│  │ (Injection │ │ ability    │ │ (Embed + │ │ (per-component,   │  │
│  │  + Blocklst│ │ (OTEL +   │ │  Query   │ │  per-request)     │  │
│  │  + Homglyph│ │  Langfuse) │ │  LRU+TTL)│ │                   │  │
│  └────────────┘ └────────────┘ └──────────┘ └───────────────────┘  │
│                                                                      │
│  EXTENSION POINTS (domain-specific):                                 │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Data       │ │ Evidence   │ │ Verifier │ │ Response          │  │
│  │ Isolation  │ │ Grader     │ │ Prompt   │ │ Schema            │  │
│  │ (tenant/   │ │ (A/B/C or  │ │ (legal,  │ │ (citations,       │  │
│  │  workspace)│ │  custom)   │ │  medical)│ │  refusals, etc)   │  │
│  └────────────┘ └────────────┘ └──────────┘ └───────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Extension Points (where domain logic plugs in)

| Extension Point | Legal (Evidence-Bound) | Medical | Financial |
|----------------|----------------------|---------|-----------|
| **Data Isolation** | tenant_id + matter_id | patient_id + study_id | client_id + portfolio_id |
| **Evidence Grader** | A/B/C (verification + reranker + overlap) | Clinical confidence levels | Regulatory confidence |
| **Verifier Prompt** | "Does chunk contain exact legal evidence?" | "Does chunk contain clinical finding?" | "Does chunk cite regulatory source?" |
| **Response Schema** | Citation (doc, page, span) + refusal codes | Finding (study, section, conclusion) | Reference (regulation, clause, date) |
| **RBAC Roles** | Admin/Attorney/Paralegal/Viewer | Admin/Doctor/Nurse/Patient | Admin/Analyst/Compliance/Auditor |
| **Quality Router** | Contract vs pleading vs memo | Lab report vs clinical note vs imaging | 10-K vs invoice vs contract |

---

## 4. What's Missing for a World-Class Harness

### Gap 1: Document Quality Router (Blueprint Principle 1)

**What it does:** Classifies incoming documents by type and quality before parsing, then routes to the appropriate pipeline.

**Why it matters:** A scanned 1995 fax should not go through the same 512-token chunking as a clean digital PDF. The fax needs aggressive OCR, table detection, and smaller chunks. The PDF needs metadata extraction and structural parsing.

**Harness design:**

```python
class DocumentQualityRouter:
    """Route documents to appropriate processing pipeline."""

    def classify(self, file_path: str, metadata: dict) -> DocumentProfile:
        """Return quality profile: digital/scanned/mixed, structure level, table density."""

    def route(self, profile: DocumentProfile) -> ProcessingPipeline:
        """Select parser, chunking strategy, and embedding approach based on profile."""
```

**What Evidence-Bound has today:** Parser selection via `PARSER_PROVIDER` env var (global, not per-document). OCR fallback in Marker. Min-text-chars detection for OCR warning.

**What to build:** Per-document classification based on: text extractability (digital vs scanned), structure detection (headers, tables, lists), page count, file size. Route to different chunk_size + parser + OCR settings.

---

### Gap 2: Table-Aware Processing (Blueprint Principle 3)

**What it does:** Detects tables in documents, extracts them as structured objects (CSV/markdown), and creates dual embeddings: one for the structured data, one for a natural language summary.

**Why it matters:** Legal contracts have indemnification schedules, fee tables, payment terms. Financial docs have balance sheets, P&L statements. Standard chunking destroys these.

**Harness design:**

```python
class TableProcessor:
    """Extract and dual-embed tables from documents."""

    def detect_tables(self, page_content: str) -> list[TableRegion]:
        """Identify table boundaries in page text."""

    def extract_structured(self, table: TableRegion) -> StructuredTable:
        """Convert to CSV/markdown preserving headers and values."""

    def dual_embed(self, table: StructuredTable) -> tuple[list[float], list[float]]:
        """Return (structural_embedding, summary_embedding)."""
```

**What Evidence-Bound has today:** Nothing. Tables are tokenized as flat text.

**What to build:** Marker already detects tables during OCR. Expose that detection, extract as markdown, generate summary via LLM, embed both representations. Store with `chunk_type: "table"` metadata for retrieval filtering.

---

### Gap 3: Metadata-Enriched Retrieval (Blueprint Principle 2)

**What it does:** Uses structured metadata (document type, date, author, section headers) as first-class retrieval filters, not just vector similarity.

**Why it matters:** "What were the Q4 2024 revenue figures?" should filter by `doc_type=10K AND date=2024Q4` before doing vector search, not rely on embeddings to figure out the date.

**Harness design:**

```python
class MetadataFilter:
    """Build search filters from query analysis and document metadata."""

    def extract_query_filters(self, question: str) -> dict[str, Any]:
        """Parse date ranges, doc types, entity names from question."""

    def apply_to_search(self, base_query: SearchQuery, filters: dict) -> SearchQuery:
        """Add metadata filters to search request."""
```

**What Evidence-Bound has today:** Metadata extraction (title, author, page_count) at ingestion. Tenant/matter filtering in Azure Search. But: metadata not indexed as filterable fields, not used in retrieval scoring.

**What to build:** Index `doc_type`, `doc_date`, `author`, custom tags as filterable + facetable fields in Azure Search. Add query analysis to extract metadata hints. Boost results matching metadata filters.

---

### Gap 4: Hierarchical Document Structure (Blueprint Principle 5)

**What it does:** Parses document structure (sections, subsections, clauses) and builds a tree. Broad questions retrieve from high-level summaries; precise questions drill down to specific clauses.

**Why it matters:** "What does Article 7 say about termination?" should go directly to Article 7, not scan all 500 chunks looking for "termination."

**Harness design:**

```python
class DocumentTree:
    """Hierarchical document representation."""

    def build_tree(self, parsed_doc: ParseResult) -> TreeNode:
        """Build section/subsection tree from parsed document."""

    def multi_level_embed(self, tree: TreeNode) -> list[TreeChunk]:
        """Embed at multiple granularity levels: section summary + leaf chunks."""

    def route_query(self, question: str, tree: TreeNode) -> list[TreeChunk]:
        """Broad question -> high-level nodes. Precise question -> leaf nodes."""
```

**What Evidence-Bound has today:** Flat chunks with page numbers. No section detection.

**What to build:** Section header detection during parsing (regex + LLM). Parent-child chunk relationships. Multi-level embedding (section summary + individual paragraphs). Query routing based on specificity.

---

### Gap 5: Agentic Retrieval Loop (Blueprint Principle 6)

**What it does:** If first retrieval doesn't find a confident answer, the system reformulates the query and tries again. Hypothesize -> Retrieve -> Verify -> Refine.

**Why it matters:** "What is the total exposure across all agreements?" requires: (1) find all agreements, (2) find exposure clauses in each, (3) aggregate. Single-shot retrieval can't do this.

**Harness design:**

```python
class AgenticRetriever:
    """Multi-turn retrieval with query refinement."""

    def retrieve_with_refinement(
        self,
        question: str,
        max_iterations: int = 3,
    ) -> AgenticResult:
        """
        Loop:
        1. Analyze question -> decompose if complex
        2. Retrieve candidates
        3. Verify relevance
        4. If confidence < threshold: reformulate query, try again
        5. If max iterations: return best result or refuse
        """
```

**What Evidence-Bound has today:** Single-shot retrieve + verify. Follow-up question detection for conversational context. Auto-verify fast path. But: no query decomposition, no re-retrieval, no refinement.

**What to build:** Query complexity classifier (simple vs multi-hop vs aggregation). Query decomposition into sub-queries. Iterative retrieval with semantic caching to avoid redundant searches. Confidence-gated loop exit.

---

## 5. Harness Package Structure

```
rag-harness/
├── pyproject.toml                # Package config
├── README.md
│
├── rag_harness/
│   ├── __init__.py
│   ├── pipeline.py               # RAGPipeline orchestrator
│   ├── config.py                 # Pydantic Settings (not flat env vars)
│   │
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── chunker.py            # Chunking with offsets (from ingestion.py)
│   │   ├── quality_router.py     # NEW: Document quality classification
│   │   └── table_processor.py    # NEW: Table detection + dual embedding
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── search/
│   │   │   ├── base.py           # SearchClient ABC (from search/base.py)
│   │   │   ├── azure.py          # Azure AI Search (from search/azure.py)
│   │   │   └── local.py          # BM25 + Vector + RRF (from search/local.py)
│   │   ├── llm/
│   │   │   ├── base.py           # LLMClient ABC (from llm/base.py)
│   │   │   ├── azure_openai.py
│   │   │   ├── anthropic.py
│   │   │   ├── gemini.py
│   │   │   └── ollama.py
│   │   ├── embedding/
│   │   │   ├── base.py           # EmbeddingClient ABC
│   │   │   ├── azure_openai.py
│   │   │   └── local.py
│   │   ├── parser/
│   │   │   ├── base.py           # ParserClient ABC (from parsers/base.py)
│   │   │   ├── pypdf.py
│   │   │   ├── marker.py
│   │   │   └── llamaparse.py
│   │   └── reranker/
│   │       ├── base.py           # RerankerClient ABC
│   │       └── local.py
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── bm25.py               # BM25 engine (from retrieval.py)
│   │   ├── fusion.py             # RRF fusion (from retrieval.py)
│   │   ├── hybrid.py             # Hybrid search orchestration
│   │   └── agentic.py            # NEW: Multi-turn retrieval loop
│   │
│   ├── verification/
│   │   ├── __init__.py
│   │   ├── verifier.py           # LLM verification (from verification.py)
│   │   ├── parallel.py           # Parallel verification (from ask_service.py)
│   │   └── auto_verify.py        # Fast path for high-confidence (from ask_service.py)
│   │
│   ├── citation/
│   │   ├── __init__.py
│   │   ├── validator.py          # Citation validation (from evidence.py)
│   │   ├── grader.py             # Evidence grading (from evidence.py, configurable)
│   │   └── negation.py           # Adversarial negation detection (from evidence.py)
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   ├── injection.py          # Prompt injection detection (from policy.py)
│   │   ├── blocklist.py          # Span content blocklist (from verification.py)
│   │   └── isolation.py          # Data isolation interface (NEW)
│   │
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── otel.py               # OpenTelemetry setup (from otel.py)
│   │   ├── langfuse.py           # Langfuse integration (from otel.py)
│   │   ├── metrics.py            # Custom metrics (from otel.py)
│   │   └── cost.py               # Cost tracking (from cost.py)
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── embedding_cache.py    # LRU embedding cache (from cache.py)
│   │   └── query_cache.py        # TTL query cache (from cache.py)
│   │
│   └── http/
│       ├── __init__.py
│       └── client.py             # httpx pool manager (from http_client.py)
│
├── tests/
│   ├── test_bm25.py
│   ├── test_fusion.py
│   ├── test_injection.py
│   ├── test_citation.py
│   ├── test_verification.py
│   ├── test_cache.py
│   ├── test_cost.py
│   └── test_pipeline.py          # End-to-end pipeline test
│
└── examples/
    ├── legal/                     # Evidence-Bound domain config
    │   ├── grader.py              # Legal evidence grading
    │   ├── verifier_prompt.txt    # Legal verification prompt
    │   ├── roles.py               # Attorney/Paralegal/Viewer
    │   └── schemas.py             # Citation + EvidenceSupport
    ├── medical/                   # Example: clinical RAG
    │   ├── grader.py
    │   ├── verifier_prompt.txt
    │   └── schemas.py
    └── quickstart.py              # Minimal working example
```

---

## 6. Quickstart Example (what using the harness looks like)

```python
from rag_harness import RAGPipeline
from rag_harness.providers.llm import AzureOpenAIClient
from rag_harness.providers.embedding import AzureOpenAIEmbeddingClient
from rag_harness.providers.search import LocalSearchClient
from rag_harness.providers.parser import MarkerParser
from rag_harness.citation import EvidenceGrader
from rag_harness.security import InjectionDetector

# Configure the pipeline
pipeline = RAGPipeline(
    llm=AzureOpenAIClient(endpoint="...", api_key="...", model="gpt-5-mini"),
    embedding=AzureOpenAIEmbeddingClient(endpoint="...", deployment="text-embedding-3-large"),
    search=LocalSearchClient(top_k=5, rrf_k=60),
    parser=MarkerParser(force_ocr=False),

    # Domain-specific extension points
    grader=EvidenceGrader(
        thresholds={"A": 2.5, "B": 1.5, "C": 0.3},
        require_verification=True,
    ),
    security=InjectionDetector(patterns="default"),

    # Infrastructure
    cache_embeddings=True,
    cache_queries=True,
    enable_langfuse=True,
    enable_otel=True,
)

# Ingest a document
pipeline.ingest("contract.pdf", metadata={"doc_type": "contract", "date": "2024-01-15"})

# Ask a question
result = pipeline.ask(
    question="What is the indemnification cap?",
    filters={"tenant_id": "acme-corp", "workspace_id": "case-42"},
)

# Result includes: answer, citations, evidence grade, cost, latency breakdown
print(result.answer)          # "According to Section 8.2 (page 14)..."
print(result.citations)       # [Citation(doc="contract.pdf", page=14, span="...")]
print(result.evidence.grade)  # "A"
print(result.cost.total_usd)  # 0.0034
print(result.latency.total_ms)# 2100
```

---

## 7. What Makes This Harness Different

Most RAG frameworks give you retrieval. This gives you **trust**.

| Feature | LangChain / LlamaIndex | This Harness |
|---------|----------------------|--------------|
| Citation validation | None (LLM generates citations) | 90% similarity check + negation detection |
| Evidence grading | None | Configurable A/B/C with multiple signals |
| Refusal policy | None (always answers) | Configurable confidence gate -- refuse when unsure |
| Injection detection | Basic | 22 patterns + homoglyph normalization + span blocklist |
| Chunk security | None (chunks are trusted) | Chunks marked untrusted in LLM context |
| Cost tracking | None or basic | Per-component, per-request, with breakdown |
| Observability | Optional add-on | Built-in: OTEL spans + Langfuse traces + PII-safe |
| Multi-tenant | Not supported | First-class data isolation at every layer |
| LLM verification | None | Parallel verification with auto-verify fast path |
| Provider abstraction | Framework-locked | 4 LLM, 3 parser, 2 search, 2 embedding providers |

**The pitch:** "Every answer is either cited and graded, or the system refuses. You can't get a hallucinated citation. You can't get a confident-sounding wrong answer. You get evidence or you get nothing."

---

## 8. Extraction Roadmap

### Phase 1: Core Package (2 weeks)

Extract the generic components into `rag-harness/`:
- Provider interfaces (SearchClient, LLMClient, EmbeddingClient, ParserClient, RerankerClient)
- BM25 engine + RRF fusion
- Citation validator + negation detector
- Injection detector + blocklist
- Embedding cache + query cache
- httpx client pool
- Cost tracker
- OTEL + Langfuse setup
- Pydantic Settings config (replace flat env vars)
- Tests for all extracted components

### Phase 2: Pipeline Orchestrator (1 week)

Build `RAGPipeline` that composes the providers:
- `pipeline.ingest()` -- parse + chunk + embed + index
- `pipeline.ask()` -- search + verify + grade + cite
- Extension points for domain-specific grading, verification prompts, response schemas
- End-to-end test with local providers (no Azure dependency)

### Phase 3: Missing Capabilities (3-4 weeks)

Build the gaps identified in the enterprise blueprint:
- Document quality router
- Table-aware processing (detect + extract + dual embed)
- Metadata-enriched retrieval
- Agentic retrieval loop (multi-turn with refinement)
- Hierarchical document structure (TreeRAG-lite)

### Phase 4: Domain Templates (1 week per domain)

Create example configurations:
- `examples/legal/` -- Evidence-Bound config (already exists)
- `examples/medical/` -- Clinical RAG config
- `examples/financial/` -- Regulatory compliance config
- `examples/quickstart.py` -- Minimal working example

---

## 9. Answer: Do We Have a Repeatable Process?

**Yes, about 70% of one.**

Evidence-Bound accidentally built a good RAG harness while building a legal product. The provider abstractions are excellent. The security, observability, and citation validation are ahead of most open-source RAG frameworks. The caching, cost tracking, and parallel verification are production-grade.

What's missing is the **document intelligence layer** (quality routing, table processing, hierarchical parsing) and the **agentic loop** (multi-turn refinement). These are the pieces that separate a demo from a system that works on real enterprise data.

The extraction is worth doing. The codebase is clean enough to refactor without rewriting. And the resulting harness would be genuinely differentiated: not another "wrapper around LangChain," but a trust-first RAG foundation where every answer is either evidence-backed or refused.
