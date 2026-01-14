from fastapi import APIRouter, Header
from app.schemas import AskRequest, AskResponse
from app.services.ask_service import execute_ask

router = APIRouter()

@router.post("/v1/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    x_docqa_session: str | None = Header(default=None),
) -> AskResponse:
    return execute_ask(payload, session_id=x_docqa_session)
