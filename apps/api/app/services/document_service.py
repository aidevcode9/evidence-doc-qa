import uuid
from fastapi import UploadFile, HTTPException

from app import ingestion, indexing
from app.db import Chunk, Document, insert_chunks, insert_document


async def process_document_upload(file: UploadFile) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    doc_id = uuid.uuid4().hex
    doc_sha256 = ingestion.compute_sha256(data)
    docs_snapshot_id = ingestion.docs_snapshot_id_for(doc_sha256)
    storage_path = ingestion.save_raw_pdf(doc_id, file.filename or "upload.pdf", data)

    try:
        pages = ingestion.parse_pdf_pages(storage_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PARSE_FAILED: {exc}") from exc

    chunk_rows = ingestion.build_chunk_rows(doc_id, doc_sha256, docs_snapshot_id, pages)
    # Tuple structure (FR-013): (chunk_id, snap_id, doc_id, sha256, page_num, page_end, chunk_idx, char_start, char_end, text, mode)
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
        )
        for row in chunk_rows
    )
    insert_document(
        Document(
            doc_id=doc_id,
            doc_sha256=doc_sha256,
            doc_name=file.filename or "upload.pdf",
            storage_path=storage_path,
            ingested_at_utc=ingestion.utc_now(),
            docs_snapshot_id=docs_snapshot_id,
        )
    )

    indexing.index_chunk_rows(
        doc_id=doc_id,
        doc_name=file.filename or "upload.pdf",
        docs_snapshot_id=docs_snapshot_id,
        chunk_rows=chunk_rows,
    )

    return {
        "doc_id": doc_id,
        "doc_sha256": doc_sha256,
        "docs_snapshot_id": docs_snapshot_id,
    }
