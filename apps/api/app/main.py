import os
import time
import uuid

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import indexing, ingestion, policy, retrieval
from .config import (
    CONF_MIN,
    DATA_DIR,
    METRICS_ADMIN_TOKEN,
    MODEL_ID,
    PARSER_MODE,
    PROMPT_VERSION,
    RAW_DIR,
    RETRIEVAL_VERSION,
    ALLOWED_ORIGINS,
)
from .db import Chunk, Document, get_doc_name, get_latest_docs_snapshot_id, insert_chunks, insert_document
from .schemas import AskRequest, AskResponse, Citation
from .telemetry import compute_metrics, load_window_telemetry, record_telemetry

app = FastAPI(title="DocQ&A API", version="0.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    # Bootstrap data directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/v1/docs/upload")
async def upload_doc(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    doc_id = uuid.uuid4().hex
    doc_sha256 = ingestion.compute_sha256(data)
    docs_snapshot_id = ingestion.docs_snapshot_id_for(doc_sha256)
    storage_path = ingestion.save_raw_pdf(doc_id, file.filename or "upload.pdf", data)

    try:
        pages = ingestion.parse_pdf_pages(storage_path)
    except Exception as exc:  # noqa: BLE001 - returns structured parse error
        raise HTTPException(status_code=400, detail=f"PARSE_FAILED: {exc}") from exc

    chunk_rows = ingestion.build_chunk_rows(doc_id, doc_sha256, docs_snapshot_id, pages)
    insert_chunks(
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


@app.post("/v1/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    start_time = time.perf_counter()
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    request_id = str(uuid.uuid4())
    docs_snapshot_id = payload.docs_snapshot_id or get_latest_docs_snapshot_id() or "none"
    version_snapshot = {
        "request_id": request_id,
        "docs_snapshot_id": docs_snapshot_id,
        "prompt_version": PROMPT_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "model_id": MODEL_ID,
        "parser_mode": PARSER_MODE,
    }

    if policy.is_injection_attempt(question):
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="INJECTION_DETECTED",
            reason="Injection heuristics triggered.",
            failure_label="INJECTION_DETECTED",
            start_time=start_time,
        )

    results = retrieval.hybrid_search(question, docs_snapshot_id)
    if not results or results[0]["rrf_score"] == 0.0:
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="NO_SUPPORTING_EVIDENCE",
            reason="No supporting evidence found.",
            failure_label="NO_EVIDENCE",
            start_time=start_time,
        )

    top_chunk = results[0]
    top_score = top_chunk["rrf_score"]
    if top_score < CONF_MIN:
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="LOW_RETRIEVAL_CONFIDENCE",
            reason="Insufficient retrieval confidence.",
            failure_label="LOW_CONFIDENCE",
            start_time=start_time,
        )

    citation = Citation(
        doc_id=top_chunk["doc_id"],
        doc_name=top_chunk.get("doc_name") or _doc_name_for(top_chunk["doc_id"]),
        page_num=top_chunk["page_num"],
        chunk_id=top_chunk["chunk_id"],
        snippet=_snippet_for(top_chunk["chunk_text"]),
        score=round(top_score, 4),
    )
    answer_text = f"Based on the document, {citation.snippet}"

    response = AskResponse(
        request_id=request_id,
        answer_text=answer_text,
        citations=[citation],
        refusal_code=None,
        reason=None,
        version_snapshot=version_snapshot,
    )
    _record_request(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        version_snapshot=version_snapshot,
        refusal_code=None,
        failure_label=None,
        start_time=start_time,
    )
    return response


@app.get("/v1/metrics")
def metrics(x_admin_token: str | None = Header(default=None)) -> dict:
    if METRICS_ADMIN_TOKEN and x_admin_token != METRICS_ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    rows = load_window_telemetry()
    return compute_metrics(rows)


def _snippet_for(chunk_text: str, limit: int = 200) -> str:
    return chunk_text[:limit].strip()


def _doc_name_for(doc_id: str) -> str:
    return get_doc_name(doc_id) or "unknown"


def _record_request(
    *,
    request_id: str,
    docs_snapshot_id: str,
    version_snapshot: dict,
    refusal_code: str | None,
    failure_label: str | None,
    start_time: float,
) -> None:
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    record_telemetry(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        prompt_version=version_snapshot["prompt_version"],
        retrieval_version=version_snapshot["retrieval_version"],
        model_id=version_snapshot["model_id"],
        parser_mode=version_snapshot["parser_mode"],
        timestamp_utc=ingestion.utc_now(),
        latency_ms=latency_ms,
        tokens_in=0,
        tokens_out=0,
        cost_est=0.0,
        cache_hit=False,
        refusal_code=refusal_code,
        failure_label=failure_label,
    )


def _emit_refusal(
    *,
    request_id: str,
    docs_snapshot_id: str,
    version_snapshot: dict,
    refusal_code: str,
    reason: str,
    failure_label: str,
    start_time: float,
) -> AskResponse:
    response = AskResponse(
        request_id=request_id,
        answer_text=None,
        citations=None,
        refusal_code=refusal_code,
        reason=reason,
        version_snapshot=version_snapshot,
    )
    _record_request(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        version_snapshot=version_snapshot,
        refusal_code=refusal_code,
        failure_label=failure_label,
        start_time=start_time,
    )
    return response

