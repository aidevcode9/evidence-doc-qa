import os
import uuid
import json
from apps.api.app import ingestion, indexing, db
from apps.api.app.db import Chunk, Document, IndexRecord, init_db, session_scope
from sqlalchemy import select

def is_already_seeded(snapshot_id: str) -> bool:
    """Checks if the specific snapshot already exists in the DB."""
    try:
        with session_scope() as session:
            stmt = select(Document).where(Document.docs_snapshot_id == snapshot_id)
            result = session.execute(stmt).first()
            return result is not None
    except Exception:
        # If table doesn't exist yet, it's not seeded
        return False

def seed():
    # Use ARCHITECTURE.md as the source
    src_path = "docs/ARCHITECTURE.md"
    docs_snapshot_id = "snap_demo"

    if not os.path.exists(src_path):
        print(f"Source file not found: {src_path}")
        return

    # Initialize DB (create tables if they don't exist)
    init_db()

    # Idempotency check
    if is_already_seeded(docs_snapshot_id):
        print(f"Snapshot '{docs_snapshot_id}' already exists. Skipping seed.")
        return

    print(f"Seeding fresh data for snapshot '{docs_snapshot_id}'...")

    with open(src_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    doc_id = "doc_demo"
    doc_sha256 = ingestion.compute_sha256(text.encode("utf-8"))
    
    # Parse and chunk
    pages = [text]
    chunk_rows = ingestion.build_chunk_rows(doc_id, doc_sha256, docs_snapshot_id, pages)
    
    print(f"Building {len(chunk_rows)} chunks...")

    # Insert Chunks
    db.insert_chunks(
        Chunk(
            chunk_id=row[0],
            docs_snapshot_id=row[1],
            doc_id=row[2],
            doc_sha256=row[3],
            page_num=row[4],
            chunk_index=row[5],
            char_start=row[6],
            char_end=row[7],
            chunk_text=row[8],
            parse_mode=row[9],
        )
        for row in chunk_rows
    )

    # Insert Document
    db.insert_document(
        Document(
            doc_id=doc_id,
            doc_sha256=doc_sha256,
            doc_name="ARCHITECTURE.md",
            storage_path=src_path,
            ingested_at_utc=ingestion.utc_now(),
            docs_snapshot_id=docs_snapshot_id,
        )
    )

    # Insert IndexRecords (Local mode)
    from apps.api.app.embeddings import embed_texts
    texts = [row[8] for row in chunk_rows]
    embeddings = embed_texts(texts)
    indexed_at = ingestion.utc_now()
    
    from apps.api.app.config import INDEX_VERSION, RETRIEVAL_VERSION

    db.insert_index_records(
        IndexRecord(
            chunk_id=row[0],
            docs_snapshot_id=row[1],
            doc_id=row[2],
            doc_name="ARCHITECTURE.md",
            page_num=row[4],
            chunk_index=row[5],
            chunk_text=row[8],
            embedding_json=json.dumps(embedding),
            indexed_at_utc=indexed_at,
            index_version=INDEX_VERSION,
            retrieval_version=RETRIEVAL_VERSION,
        )
        for row, embedding in zip(chunk_rows, embeddings)
    )

    # NEW: Also index into Azure Search if enabled
    indexing.index_chunk_rows(
        doc_id=doc_id,
        doc_name="ARCHITECTURE.md",
        docs_snapshot_id=docs_snapshot_id,
        chunk_rows=chunk_rows,
    )

    print("Seeding complete.")

if __name__ == "__main__":
    seed()