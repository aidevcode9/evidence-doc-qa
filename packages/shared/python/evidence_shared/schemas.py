import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, field_validator


class RefusalCode(str, Enum):
    NO_SUPPORTING_EVIDENCE = "NO_SUPPORTING_EVIDENCE"
    LOW_RETRIEVAL_CONFIDENCE = "LOW_RETRIEVAL_CONFIDENCE"
    INJECTION_DETECTED = "INJECTION_DETECTED"
    PARSE_FAILED = "PARSE_FAILED"
    POLICY_REFUSAL = "POLICY_REFUSAL"


class VersionSnapshot(BaseModel):
    request_id: str
    docs_snapshot_id: str
    prompt_version: str
    verifier_prompt_version: Optional[str] = None
    retrieval_version: str
    model_id: str
    parser_mode: str


class AskRequest(BaseModel):
    question: str
    docs_snapshot_id: Optional[str] = None
    top_k: Optional[int] = 8
    include_debug: Optional[bool] = False

    @field_validator("docs_snapshot_id")
    @classmethod
    def validate_docs_snapshot_id(cls, v: Optional[str]) -> Optional[str]:
        """SECURITY: Prevent OData filter injection via docs_snapshot_id.

        This value is interpolated into Azure Search OData $filter strings.
        Without validation, an attacker could inject filter clauses to bypass
        tenant isolation (e.g., "' or tenant_id eq 'victim-tenant").
        """
        if v is None:
            return v
        # Same pattern as _is_valid_identifier in context.py:
        # alphanumeric with hyphens and underscores, max 64 chars.
        if not re.match(r"^[a-zA-Z0-9][-_a-zA-Z0-9]{0,63}$", v):
            msg = "docs_snapshot_id must be alphanumeric with hyphens/underscores (max 64 chars)"
            raise ValueError(msg)
        return v


class Citation(BaseModel):
    citation_index: int  # Maps to [1], [2], [3] markers in answer_text
    doc_id: str
    doc_name: str
    page_num: int
    page_end: int
    char_start: int
    char_end: int
    chunk_id: str
    snippet: str
    highlighted_text: Optional[str] = None
    score: float


class EvidenceSupport(BaseModel):
    verdict: str  # "VERIFIED" | "UNVERIFIED"
    verifier_model: Optional[str] = None
    evidence_grade: str  # "A" | "B" | "C"
    evidence_label: str  # "Strong" | "Moderate" | "Weak"
    support_count: int
    top_rrf_score: Optional[float] = None
    azure_search_score: Optional[float] = None
    azure_reranker_score: Optional[float] = None
    reranker_score: float = 0.0
    rrf_margin: float
    overlap_score: float
    supporting_span: str
    supporting_page_num: int
    supporting_doc_name: str
    docs_snapshot_id: str
    index_version: str
    confidence_threshold: float  # Shows current threshold used for refusal (FR-024)


class DebugCandidate(BaseModel):
    doc_id: str
    doc_name: str
    page_num: int
    page_end: int
    char_start: int
    char_end: int
    chunk_id: str
    rrf_score: Optional[float] = None
    azure_search_score: Optional[float] = None
    azure_reranker_score: Optional[float] = None
    overlap_score: float
    verifier_verdict: str
    reason: str
    snippet: str


class AskResponse(BaseModel):
    request_id: str
    answer_text: Optional[str] = None
    citations: Optional[List[Citation]] = None
    refusal_code: Optional[RefusalCode] = None
    reason: Optional[str] = None
    evidence: Optional[EvidenceSupport] = None
    debug_candidates: Optional[List[DebugCandidate]] = None
    version_snapshot: VersionSnapshot
