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
    score: float


class EvidenceSupport(BaseModel):
    verdict: str
    verifier_model: Optional[str]
    evidence_grade: str
    evidence_label: str
    support_count: int
    top_rrf_score: float
    rrf_margin: float
    overlap_score: float
    supporting_span: str
    supporting_page_num: int
    supporting_doc_name: str
    docs_snapshot_id: str
    index_version: str


class AskResponse(BaseModel):
    request_id: str
    answer_text: Optional[str]
    citations: Optional[List[Citation]]
    refusal_code: Optional[str]
    reason: Optional[str]
    evidence: Optional[EvidenceSupport] = None
    version_snapshot: dict
