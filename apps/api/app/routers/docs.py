from fastapi import APIRouter, File, UploadFile
from app.services.document_service import process_document_upload

router = APIRouter()

@router.post("/v1/docs/upload")
async def upload_doc(file: UploadFile = File(...)) -> dict:
    return await process_document_upload(file)
