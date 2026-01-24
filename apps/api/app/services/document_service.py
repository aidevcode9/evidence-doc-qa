import uuid
from typing import Any, TYPE_CHECKING

from fastapi import UploadFile, HTTPException

from app import ingestion, indexing
from app.config import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB, MIN_EXTRACTED_TEXT_CHARS
from app.db import Chunk, Document, insert_chunks, insert_document
from app.parsers import get_parser_client
from app.telemetry import logger

if TYPE_CHECKING:
    from app.parsers.base import ParseResult

# Type alias for chunk row tuple
ChunkRowTuple = tuple[str, str, str, str, int, int, int, int, int, str, str]


async def process_document_upload(
    file: UploadFile,
    *,
    tenant_id: str,
    matter_id: str,
) -> dict[str, Any]:
    """Process an uploaded document.

    Handles PDF and image uploads (FR-010). Uses the configured parser
    for text extraction including OCR for scanned documents (FR-012).

    Args:
        file: Uploaded file from FastAPI.
        tenant_id: Tenant ID for isolation (FR-001).
        matter_id: Matter ID for isolation (FR-002).

    Returns:
        Dict with doc_id, doc_sha256, docs_snapshot_id, and optional warnings.

    Raises:
        HTTPException: If file is empty, too large, unsupported type, or parsing fails.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    # Check file size limit
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB.",
        )

    # Validate file extension
    filename = file.filename or "upload.pdf"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    parser = get_parser_client()
    if ext not in parser.supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. "
            f"Supported: {', '.join(sorted(parser.supported_extensions))}",
        )

    doc_id = uuid.uuid4().hex
    doc_sha256 = ingestion.compute_sha256(data)
    docs_snapshot_id = ingestion.docs_snapshot_id_for(doc_sha256)
    storage_path = ingestion.save_raw_pdf(doc_id, filename, data)

    try:
        # Use new async parse_document (FR-012)
        parse_result = await ingestion.parse_document(storage_path)
    except Exception as exc:
        # Sanitize error message to not leak internal paths
        error_msg = str(exc)
        if storage_path in error_msg:
            error_msg = error_msg.replace(storage_path, "[document]")
        logger.error(f"Parse failed for doc_id={doc_id}: {exc}")
        raise HTTPException(status_code=400, detail=f"PARSE_FAILED: {error_msg}") from exc

    # Build chunk rows from ParseResult pages (preserves page/char offsets)
    chunk_rows = _build_chunk_rows_from_parse_result(
        doc_id=doc_id,
        doc_sha256=doc_sha256,
        docs_snapshot_id=docs_snapshot_id,
        parse_result=parse_result,
    )

    # Check for empty extraction (OCR failure or empty document)
    total_text_chars = sum(len(row[9]) for row in chunk_rows)  # row[9] is chunk_text
    warnings = []

    if not chunk_rows or total_text_chars < MIN_EXTRACTED_TEXT_CHARS:
        logger.warning(
            f"Low text extraction for doc_id={doc_id}: "
            f"chunks={len(chunk_rows)}, chars={total_text_chars}, "
            f"provider={parse_result.provider}"
        )
        warnings.append(
            f"Low text extracted ({total_text_chars} chars). "
            "Document may be scanned/image-based with OCR issues. "
            "Queries against this document may not return results."
        )

    # Tuple structure (FR-013): (chunk_id, snap_id, doc_id, sha256, page_num, page_end, chunk_idx, char_start, char_end, text, mode)
    # Set tenant_id and matter_id for isolation (FR-001, FR-002)
    insert_chunks(
        Chunk(
            chunk_id=row[0],
            docs_snapshot_id=row[1],
            doc_id=row[2],
            doc_sha256=row[3],
            page_num=row[4],
            page_end=row[5],
            chunk_index=row[6],
            char_start=row[7],
            char_end=row[8],
            chunk_text=row[9],
            parse_mode=row[10],
            tenant_id=tenant_id,
            matter_id=matter_id,
        )
        for row in chunk_rows
    )
    # Set tenant_id and matter_id for isolation (FR-001, FR-002)
    insert_document(
        Document(
            doc_id=doc_id,
            doc_sha256=doc_sha256,
            doc_name=filename,
            storage_path=storage_path,
            ingested_at_utc=ingestion.utc_now(),
            docs_snapshot_id=docs_snapshot_id,
            tenant_id=tenant_id,
            matter_id=matter_id,
        )
    )

    indexing.index_chunk_rows(
        doc_id=doc_id,
        doc_name=filename,
        docs_snapshot_id=docs_snapshot_id,
        chunk_rows=chunk_rows,
        tenant_id=tenant_id,
        matter_id=matter_id,
    )

    result: dict[str, Any] = {
        "doc_id": doc_id,
        "doc_sha256": doc_sha256,
        "docs_snapshot_id": docs_snapshot_id,
    }

    if warnings:
        result["warnings"] = warnings

    return result


def _build_chunk_rows_from_parse_result(
    doc_id: str,
    doc_sha256: str,
    docs_snapshot_id: str,
    parse_result: "ParseResult",
) -> list[ChunkRowTuple]:
    """Build chunk rows from ParseResult.

    This preserves the page numbers and character offsets from the parser
    while applying the configured chunking strategy.

    Args:
        doc_id: Document ID.
        doc_sha256: Document SHA256 hash.
        docs_snapshot_id: Snapshot ID.
        parse_result: Result from parse_document().

    Returns:
        List of chunk row tuples.
    """
    from app.config import PARSER_MODE

    rows: list[ChunkRowTuple] = []
    for page in parse_result.pages:
        page_num = page.page_number
        page_end = page_num  # Single-page chunks for now (FR-013)

        # Apply chunking to page text
        for chunk_index, (char_start_rel, char_end_rel, chunk_text) in enumerate(
            ingestion.chunk_page_text(page.text)
        ):
            # Convert relative char offsets to absolute
            char_start = page.char_start + char_start_rel
            char_end = page.char_start + char_end_rel

            chunk_id = ingestion.make_chunk_id(doc_id, page_num, chunk_index)
            rows.append(
                (
                    chunk_id,
                    docs_snapshot_id,
                    doc_id,
                    doc_sha256,
                    page_num,
                    page_end,
                    chunk_index,
                    char_start,
                    char_end,
                    chunk_text,
                    PARSER_MODE,
                )
            )
    return rows
