from fastapi import APIRouter, Depends, Header

from app.context import RequestContext, get_request_context
from app.schemas import AskRequest, AskResponse
from app.services.ask_service import execute_ask

router = APIRouter()


@router.post("/v1/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    context: RequestContext = Depends(get_request_context),
    x_docqa_session: str | None = Header(default=None),
) -> AskResponse:
    """Ask a question with tenant/matter isolation (FR-001, FR-002)."""
    return execute_ask(
        payload,
        session_id=x_docqa_session,
        tenant_id=context.tenant_id,
        matter_id=context.matter_id,
    )
