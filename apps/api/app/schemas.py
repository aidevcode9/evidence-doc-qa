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


class AskResponse(BaseModel):
    request_id: str
    answer_text: Optional[str]
    citations: Optional[List[Citation]]
    refusal_code: Optional[str]
    reason: Optional[str]
    version_snapshot: dict
