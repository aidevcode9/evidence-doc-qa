from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.config import RATE_LIMIT_QUERY
from app.context import RequestContext, get_request_context
from app.rate_limit import limiter
from app.rbac import has_permission
from app.schemas import AskRequest, AskResponse
from app.services.ask_service import execute_ask

router = APIRouter()


@router.post("/v1/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    x_docqa_session: str | None = Header(default=None),
) -> AskResponse:
    """Ask a question with tenant/matter isolation and RBAC (FR-001, FR-002, FR-003)."""
    # RBAC check (FR-003): All roles can query
    if not has_permission(context.user_role, "query"):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: query requires authentication",
        )
    from app.services.ask_service import RequestDeadlineExceeded

    try:
        return execute_ask(
            payload,
            session_id=x_docqa_session,
            tenant_id=context.tenant_id,
            matter_id=context.matter_id,
            user_id=context.user_id,
        )
    except RequestDeadlineExceeded as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {exc.deadline_seconds}s during {exc.phase}. Please try again.",
        )


# Apply shared rate limiter if enabled (NFR-012)
if limiter is not None:
    ask = limiter.limit(RATE_LIMIT_QUERY)(ask)
