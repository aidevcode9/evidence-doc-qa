import os
from apps.api.app import ingestion, indexing, db
from apps.api.app.db import Chunk, Document, init_db, session_scope
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
    # Use ARCHITECTURE.md as the source (root-level slim version)
    src_path = "ARCHITECTURE.md"
    docs_snapshot_id = "snap_demo"

    # Default tenant/matter for eval seeding (multi-tenancy support)
    tenant_id = "eval-tenant"
    matter_id = "eval-matter"

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
    # Row structure from build_chunk_rows:
    # (chunk_id, docs_snapshot_id, doc_id, doc_sha256, page_num, page_end,
    #  chunk_index, char_start, char_end, chunk_text, parse_mode)
    db.insert_chunks(
        Chunk(
            chunk_id=row[0],
            tenant_id=tenant_id,
            matter_id=matter_id,
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

    # Insert Document
    db.insert_document(
        Document(
            doc_id=doc_id,
            tenant_id=tenant_id,
            matter_id=matter_id,
            doc_sha256=doc_sha256,
            doc_name="ARCHITECTURE.md",
            storage_path=src_path,
            ingested_at_utc=ingestion.utc_now(),
            docs_snapshot_id=docs_snapshot_id,
        )
    )

    # Index chunks (handles both local DB and Azure Search)
    indexing.index_chunk_rows(
        doc_id=doc_id,
        doc_name="ARCHITECTURE.md",
        docs_snapshot_id=docs_snapshot_id,
        chunk_rows=chunk_rows,
        tenant_id=tenant_id,
        matter_id=matter_id,
    )

    print("Seeding complete.")


if __name__ == "__main__":
    seed()
