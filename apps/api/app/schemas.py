from typing import List, Optional

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    docs_snapshot_id: Optional[str] = None


class Citation(BaseModel):
    doc_id: str
    doc_name: str
    page_num: int
    chunk_id: str
    snippet: str
    highlighted_text: Optional[str] = None
    score: float


class EvidenceSupport(BaseModel):
    verdict: str
    verifier_model: Optional[str]
    evidence_grade: str
    evidence_label: str
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


class DebugCandidate(BaseModel):
    doc_id: str
    doc_name: str
    page_num: int
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
    answer_text: Optional[str]
    citations: Optional[List[Citation]]
    refusal_code: Optional[str]
    reason: Optional[str]
    evidence: Optional[EvidenceSupport] = None
    debug_candidates: Optional[List[DebugCandidate]] = None
    version_snapshot: dict
