import os
import time
import uuid

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import evidence, indexing, ingestion, policy, retrieval, verification
from .config import (
    CONF_MIN,
    DATA_DIR,
    INDEX_VERSION,
    METRICS_ADMIN_TOKEN,
    MODEL_ID,
    PARSER_MODE,
    PROMPT_VERSION,
    RAW_DIR,
    RETRIEVAL_VERSION,
    ALLOWED_ORIGINS,
    STRICT_EVIDENCE,
    ALLOW_UNVERIFIED,
)
from .db import Chunk, Document, get_doc_name, get_latest_docs_snapshot_id, insert_chunks, insert_document, init_db
from .indexing import ensure_index
from .schemas import AskRequest, AskResponse, Citation, EvidenceSupport, DebugCandidate
from .telemetry import compute_metrics, load_window_telemetry, record_telemetry, logger

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
    # Initialize DB
    try:
        init_db()
    except Exception as e:
        logger.error(f"DB initialization failed: {e}")

    # Ensure Search Index exists
    try:
        ensure_index()
    except Exception as e:
        logger.error(f"Search index initialization failed: {e}")

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
    
    logger.info(f"Incoming Request [{request_id}] - Snapshot: {docs_snapshot_id}")

    version_snapshot = {
        "request_id": request_id,
        "docs_snapshot_id": docs_snapshot_id,
        "prompt_version": PROMPT_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "model_id": MODEL_ID,
        "parser_mode": PARSER_MODE,
    }

    if policy.is_injection_attempt(question):
        logger.warning(f"Policy Trigger [{request_id}]: Injection Attempt Detected")
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="INJECTION_DETECTED",
            reason="Injection heuristics triggered.",
            failure_label="INJECTION_DETECTED",
            start_time=start_time,
            question_text=question,
        )

    results = retrieval.hybrid_search(question, docs_snapshot_id)
    if not results or results[0]["rrf_score"] == 0.0:
        logger.warning(f"Retrieval Fail [{request_id}]: No evidence found")
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="NO_SUPPORTING_EVIDENCE",
            reason="No supporting evidence found.",
            failure_label="NO_EVIDENCE",
            start_time=start_time,
            question_text=question,
        )

    # Filter results by confidence first
    candidates = [r for r in results if r["rrf_score"] >= CONF_MIN]
    if not candidates:
        logger.warning(f"Confidence Fail [{request_id}]: No results met threshold {CONF_MIN}")
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="LOW_RETRIEVAL_CONFIDENCE",
            reason="Insufficient retrieval confidence.",
            failure_label="LOW_CONFIDENCE",
            start_time=start_time,
            question_text=question,
        )

    verified_chunk = None
    verification_status = "UNVERIFIED"
    verification_rejected = False
    verification_results: dict[str, tuple[str, str | None]] = {}
    if verification.is_enabled():
        verification_rejected = True
        verified_span = None
        for chunk in candidates[:3]:
            status, span = verification.verify_relevance(question, chunk["chunk_text"])
            verification_results[chunk["chunk_id"]] = (status, span)
            if status == "verified":
                verified_chunk = chunk
                verification_status = "VERIFIED"
                verified_span = span
                verification_rejected = False
                break
            if status == "unverified":
                verification_status = "UNVERIFIED"
                verification_rejected = False
                break

        if verified_chunk is None:
            if verification_rejected:
                logger.warning(f"Verification Fail [{request_id}]: All top candidates rejected by LLM.")
                return _emit_refusal(
                    request_id=request_id,
                    docs_snapshot_id=docs_snapshot_id,
                    version_snapshot=version_snapshot,
                    refusal_code="NO_SUPPORTING_EVIDENCE",
                    reason="Retrieval found matches, but they were judged irrelevant by the model.",
                    failure_label="LLM_VERIFICATION_FAILED",
                    start_time=start_time,
                    question_text=question,
                )

            if STRICT_EVIDENCE and not ALLOW_UNVERIFIED:
                logger.warning(f"Verification Fail [{request_id}]: LLM verification unavailable (strict mode).")
                return _emit_refusal(
                    request_id=request_id,
                    docs_snapshot_id=docs_snapshot_id,
                    version_snapshot=version_snapshot,
                    refusal_code="POLICY_REFUSAL",
                    reason="LLM verification required but unavailable.",
                    failure_label="LLM_VERIFICATION_UNAVAILABLE",
                    start_time=start_time,
                    question_text=question,
                )
            verified_chunk = candidates[0]
    else:
        if STRICT_EVIDENCE and not ALLOW_UNVERIFIED:
            logger.warning(f"Verification Fail [{request_id}]: LLM verification disabled (strict mode).")
            return _emit_refusal(
                request_id=request_id,
                docs_snapshot_id=docs_snapshot_id,
                version_snapshot=version_snapshot,
                refusal_code="POLICY_REFUSAL",
                reason="LLM verification required but not configured.",
                failure_label="LLM_VERIFICATION_DISABLED",
                start_time=start_time,
                question_text=question,
            )
        verified_chunk = candidates[0]

    question_tokens = evidence.tokenize(question)
    supporting_span = evidence.best_supporting_span(question, verified_chunk["chunk_text"])
    if not supporting_span:
        supporting_span = _snippet_for(verified_chunk["chunk_text"])
    if verification_status == "VERIFIED" and verified_span:
        supporting_span = verified_span
    overlap = evidence.overlap_score(question_tokens, supporting_span)
    if verification_status == "VERIFIED":
        overlap = max(overlap, 0.6)
    top_score = results[0]["rrf_score"]
    second_score = results[1]["rrf_score"] if len(results) > 1 else 0.0
    rrf_margin = top_score - second_score
    support_count = sum(
        1
        for r in candidates
        if evidence.overlap_score(question_tokens, r["chunk_text"]) >= 0.2
    )
    support_count = max(1, support_count)
    grade, label = evidence.evidence_grade(
        verification_status == "VERIFIED",
        verified_chunk["rrf_score"],
        rrf_margin,
        overlap,
    )
    citation = Citation(
        doc_id=verified_chunk["doc_id"],
        doc_name=verified_chunk.get("doc_name") or _doc_name_for(verified_chunk["doc_id"]),
        page_num=verified_chunk["page_num"],
        chunk_id=verified_chunk["chunk_id"],
        snippet=supporting_span,
        score=round(verified_chunk["rrf_score"], 4),
    )
    evidence_support = EvidenceSupport(
        verdict=verification_status,
        verifier_model=verification.verifier_model(),
        evidence_grade=grade,
        evidence_label=label,
        support_count=support_count,
        top_rrf_score=round(top_score, 4),
        rrf_margin=round(rrf_margin, 4),
        overlap_score=round(overlap, 4),
        supporting_span=supporting_span,
        supporting_page_num=citation.page_num,
        supporting_doc_name=citation.doc_name,
        docs_snapshot_id=docs_snapshot_id,
        index_version=INDEX_VERSION,
    )
    debug_candidates: list[DebugCandidate] = []
    for chunk in candidates[:3]:
        span = evidence.best_supporting_span(question, chunk["chunk_text"])
        if not span:
            span = _snippet_for(chunk["chunk_text"])
        status, verified_span = verification_results.get(chunk["chunk_id"], ("skipped", None))
        if verified_span:
            span = verified_span
        overlap_score = evidence.overlap_score(question_tokens, span)
        reason = {
            "verified": "LLM_VERIFIED",
            "rejected": "LLM_REJECTED",
            "unverified": "LLM_UNAVAILABLE",
            "skipped": "NOT_EVALUATED",
        }.get(status, "UNKNOWN")
        debug_candidates.append(
            DebugCandidate(
                doc_id=chunk["doc_id"],
                doc_name=chunk.get("doc_name") or _doc_name_for(chunk["doc_id"]),
                page_num=chunk["page_num"],
                chunk_id=chunk["chunk_id"],
                rrf_score=round(chunk["rrf_score"], 4),
                overlap_score=round(overlap_score, 4),
                verifier_verdict=status.upper(),
                reason=reason,
                snippet=span,
            )
        )
    if STRICT_EVIDENCE and grade != "A" and not (
        ALLOW_UNVERIFIED and verification_status == "UNVERIFIED"
    ):
        logger.warning(f"Evidence Fail [{request_id}]: Grade {grade} below Strong threshold.")
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="LOW_RETRIEVAL_CONFIDENCE",
            reason="Evidence strength below Strong threshold.",
            failure_label="EVIDENCE_WEAK",
            start_time=start_time,
            question_text=question,
            evidence=evidence_support,
            citations=[citation],
            debug_candidates=debug_candidates,
        )
    answer_text = f"Based on the document, {supporting_span}"

    response = AskResponse(
        request_id=request_id,
        answer_text=answer_text,
        citations=[citation],
        refusal_code=None,
        reason=None,
        evidence=evidence_support,
        debug_candidates=debug_candidates,
        version_snapshot=version_snapshot,
    )
    _record_request(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        version_snapshot=version_snapshot,
        refusal_code=None,
        failure_label=None,
        start_time=start_time,
        question_text=question,
        answer_text=answer_text,
    )
    logger.info(f"Success [{request_id}]: Response returned with citation from {citation.doc_name}")
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
    question_text: str = "",
    answer_text: str = "",
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
        question_text=question_text,
        answer_text=answer_text or "",
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
    question_text: str = "",
    evidence: EvidenceSupport | None = None,
    citations: list[Citation] | None = None,
    debug_candidates: list[DebugCandidate] | None = None,
) -> AskResponse:
    response = AskResponse(
        request_id=request_id,
        answer_text=None,
        citations=citations,
        refusal_code=refusal_code,
        reason=reason,
        evidence=evidence,
        debug_candidates=debug_candidates,
        version_snapshot=version_snapshot,
    )
    _record_request(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        version_snapshot=version_snapshot,
        refusal_code=refusal_code,
        failure_label=failure_label,
        start_time=start_time,
        question_text=question_text,
        answer_text="",
    )
    return response
