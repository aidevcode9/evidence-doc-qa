from typing import Any

from fastapi import APIRouter, File, UploadFile
from app.services.document_service import process_document_upload

router = APIRouter()


@router.post("/v1/docs/upload")
async def upload_doc(file: UploadFile = File(...)) -> dict[str, Any]:
    result = await process_document_upload(file)
    return result
