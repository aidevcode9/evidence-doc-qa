import asyncio
import os
from apps.api.app import ingestion, indexing, retrieval, verification, db
from apps.api.app.db import Chunk, Document, insert_chunks, insert_document, init_db

# Mock file upload
PDF_PATH = "errs/Sample_Loan_Estimate_Demo.pdf"

def run_debug():
    print(f"Ingesting {PDF_PATH}...")
    
    with open(PDF_PATH, "rb") as f:
        data = f.read()

    doc_id = "debug_loan_doc"
    doc_sha256 = ingestion.compute_sha256(data)
    docs_snapshot_id = ingestion.docs_snapshot_id_for(doc_sha256)
    
    print(f"Snapshot ID: {docs_snapshot_id}")

    # 1. Parse & Chunk
    # We save it to a temp path for parsing
    temp_path = ingestion.save_raw_pdf(doc_id, "loan_estimate.pdf", data)
    pages = ingestion.parse_pdf_pages(temp_path)
    chunk_rows = ingestion.build_chunk_rows(doc_id, doc_sha256, docs_snapshot_id, pages)
    
    print(f"Generated {len(chunk_rows)} chunks.")

    # 2. Insert into DB (Local)
    init_db()
    insert_chunks(
        Chunk(
            chunk_id=row[0], docs_snapshot_id=row[1], doc_id=row[2], doc_sha256=row[3],
            page_num=row[4], chunk_index=row[5], char_start=row[6], char_end=row[7],
            chunk_text=row[8], parse_mode=row[9],
        ) for row in chunk_rows
    )
    
    # 3. Index (Azure or Local)
    indexing.index_chunk_rows(doc_id, "loan_estimate.pdf", docs_snapshot_id, chunk_rows)
    
    # 4. Run Query
    question = "What is the loan amount for Taylor?"
    print(f"\n--- Querying: '{question}' ---")
    
    results = retrieval.hybrid_search(question, docs_snapshot_id)
    print(f"Retrieval found {len(results)} hits.")
    
    if not results:
        print("FAIL: No results found.")
        return

    top_chunk = results[0]
    print(f"Top Hit Score: {top_chunk['rrf_score']:.4f}")
    print(f"Top Chunk Text:\n{top_chunk['chunk_text'][:200]}...")

    # 5. Verify
    print("\n--- Verifying ---")
    is_relevant = verification.verify_relevance(question, top_chunk['chunk_text'])
    print(f"LLM Verification: {'YES' if is_relevant else 'NO'}")

if __name__ == "__main__":
    run_debug()
