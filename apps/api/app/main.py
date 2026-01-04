import hashlib
import os
import time
import uuid
from contextlib import contextmanager

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import evidence, indexing, ingestion, policy, retrieval, verification, otel
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
    AZURE_RERANK_MIN,
    AZURE_SEARCH_SCORE_MIN,
    CONFIDENCE_VERSION,
)
from .db import Chunk, Document, get_doc_name, get_latest_docs_snapshot_id, insert_chunks, insert_document, init_db
from .indexing import ensure_index
from .schemas import AskRequest, AskResponse, Citation, EvidenceSupport, DebugCandidate
from .telemetry import compute_metrics, load_window_telemetry, record_telemetry, logger

app = FastAPI(title="DocQ&A API", version="0.0.0")
otel.setup_otel(app)
try:
    from opentelemetry import trace

    _TRACER = trace.get_tracer("docqa.api")
except Exception:
    _TRACER = None


@contextmanager
def _span(name: str, **attrs):
    if not _TRACER:
        yield None
        return
    with _TRACER.start_as_current_span(name) as span:
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, value)
        yield span

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
def ask(
    payload: AskRequest,
    x_docqa_session: str | None = Header(default=None),
    x_docqa_user_name: str | None = Header(default=None),
    x_docqa_user_email: str | None = Header(default=None),
) -> AskResponse:
    start_time = time.perf_counter()
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    request_id = str(uuid.uuid4())
    docs_snapshot_id = payload.docs_snapshot_id or get_latest_docs_snapshot_id() or "none"
    question_len = len(question)
    question_hash = _hash_text(question) if question else None
    
    logger.info(f"Incoming Request [{request_id}] - Snapshot: {docs_snapshot_id}")

    version_snapshot = {
        "request_id": request_id,
        "docs_snapshot_id": docs_snapshot_id,
        "prompt_version": PROMPT_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "model_id": MODEL_ID,
        "parser_mode": PARSER_MODE,
    }

    trace_metadata = {
        "session_id": x_docqa_session,
        "user_name": x_docqa_user_name,
        "user_email": x_docqa_user_email,
        "question_hash": question_hash,
        "question_len": question_len,
    }
    trace_metadata = {k: v for k, v in trace_metadata.items() if v}
    if not trace_metadata:
        trace_metadata = None

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
            question_len=question_len,
            trace_metadata=trace_metadata,
        )

    with _span("retrieval", docs_snapshot_id=docs_snapshot_id) as retrieval_span:
        results = retrieval.hybrid_search(question, docs_snapshot_id)
        if retrieval_span and results:
            retrieval_span.set_attribute(
                "retrieval.mode",
                "azure" if "azure_search_score" in results[0] else "local",
            )
    retrieval_trace = _build_retrieval_trace(results)
    if retrieval_trace:
        trace_metadata = {**(trace_metadata or {}), **retrieval_trace}

    retrieval_score_key = _retrieval_score_key(results)
    confidence_score_key = _confidence_score_key(results)
    confidence_min = _confidence_threshold(confidence_score_key)
    confidence_version = (
        f"{CONFIDENCE_VERSION}|local={CONF_MIN}|azure_search={AZURE_SEARCH_SCORE_MIN}|azure_rerank={AZURE_RERANK_MIN}"
    )
    confidence_meta = {
        "confidence_version": confidence_version,
        "confidence_score_key": confidence_score_key,
        "confidence_threshold": confidence_min,
    }
    trace_metadata = {**(trace_metadata or {}), **confidence_meta}

    if not results or _score_value(results[0], retrieval_score_key) == 0.0:
        logger.warning(f"Retrieval Fail [{request_id}]: No evidence found")
        debug_candidates = (
            _build_debug_candidates(question, results, reason_override="NO_SUPPORTING_EVIDENCE")
            if results
            else None
        )
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="NO_SUPPORTING_EVIDENCE",
            reason="No supporting evidence found.",
            failure_label="NO_EVIDENCE",
            start_time=start_time,
            question_len=question_len,
            debug_candidates=debug_candidates,
            trace_metadata=trace_metadata,
        )

    # Filter results by confidence first
    candidates = [
        r for r in results if _score_value(r, confidence_score_key) >= confidence_min
    ]
    if not candidates:
        logger.warning(
            f"Confidence Fail [{request_id}]: No results met threshold {confidence_min} ({confidence_score_key})"
        )
        debug_candidates = _build_debug_candidates(
            question,
            results,
            reason_override="BELOW_CONFIDENCE_THRESHOLD",
        )
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code="LOW_RETRIEVAL_CONFIDENCE",
            reason="Insufficient retrieval confidence.",
            failure_label="LOW_CONFIDENCE",
            start_time=start_time,
            question_len=question_len,
            debug_candidates=debug_candidates,
            trace_metadata=trace_metadata,
        )

    verified_chunk = None
    verification_status = "UNVERIFIED"
    verification_rejected = False
    verification_results: dict[str, tuple[str, str | None]] = {}
    verification_reasons: dict[str, str] = {}
    last_verifier_reason = None
    if verification.is_enabled():
        verification_rejected = True
        verified_span = None
        trace_metadata = {
            **(trace_metadata or {}),
            **verification.verifier_trace_metadata(),
        }
        with _span("verification", candidate_count=len(candidates)) as verify_span:
            for chunk in candidates[:3]:
                status, span, reason = verification.verify_relevance(
                    question,
                    chunk["chunk_text"],
                    request_id=request_id,
                    chunk_id=chunk["chunk_id"],
                )
                verification_results[chunk["chunk_id"]] = (status, span)
                verification_reasons[chunk["chunk_id"]] = reason
                last_verifier_reason = reason
                if status == "verified":
                    verified_chunk = chunk
                    verification_status = "VERIFIED"
                    verified_span = span
                    verification_rejected = False
                    if verify_span:
                        verify_span.set_attribute("verifier.verdict", "YES")
                        verify_span.set_attribute("verifier.reason", reason)
                    break
                if status == "unverified":
                    verification_status = "UNVERIFIED"
                    verification_rejected = False
                    if verify_span:
                        verify_span.set_attribute("verifier.verdict", "UNVERIFIED")
                    break
            if verify_span and verification_rejected and verified_chunk is None:
                verify_span.set_attribute("verifier.verdict", "NO")
                verify_span.set_attribute("verifier.reason", last_verifier_reason or "NOT_FOUND")

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
                    question_len=question_len,
                    trace_metadata=trace_metadata,
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
                    question_len=question_len,
                    trace_metadata=trace_metadata,
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
                question_len=question_len,
                trace_metadata=trace_metadata,
            )
        verified_chunk = candidates[0]

    if verification_status == "VERIFIED" and verified_chunk:
        verifier_result = {
            "verdict": "YES",
            "reason": verification_reasons.get(verified_chunk["chunk_id"], "FOUND"),
        }
    elif verification_rejected:
        verifier_result = {
            "verdict": "NO",
            "reason": last_verifier_reason or "NOT_FOUND",
        }
    else:
        verifier_result = {
            "verdict": "UNVERIFIED",
            "reason": "UNVERIFIED",
        }
    trace_metadata = {**(trace_metadata or {}), "verifier_result": verifier_result}

    question_tokens = evidence.tokenize(question)
    supporting_span = evidence.best_supporting_span(question, verified_chunk["chunk_text"])
    if not supporting_span:
        supporting_span = _snippet_for(verified_chunk["chunk_text"])
    if verification_status == "VERIFIED" and verified_span:
        supporting_span = verified_span
    overlap = evidence.overlap_score(question_tokens, supporting_span)
    if verification_status == "VERIFIED":
        overlap = max(overlap, 0.6)
    top_score = _score_value(results[0], retrieval_score_key)
    second_score = _score_value(results[1], retrieval_score_key) if len(results) > 1 else 0.0
    rrf_margin = top_score - second_score
    retrieval_score = _score_value(verified_chunk, retrieval_score_key)
    reranker_score = _score_value(verified_chunk, "azure_reranker_score")
    support_count = sum(
        1
        for r in candidates
        if evidence.overlap_score(question_tokens, r["chunk_text"]) >= 0.2
    )
    support_count = max(1, support_count)
    with _span(
        "evidence.grade",
        verification_status=verification_status,
        retrieval_score=retrieval_score,
        reranker_score=reranker_score,
        overlap_score=overlap,
    ):
        grade, label = evidence.evidence_grade(
            verification_status == "VERIFIED",
            retrieval_score,
            rrf_margin,
            overlap,
            reranker_score=reranker_score,
        )
    citation = Citation(
        doc_id=verified_chunk["doc_id"],
        doc_name=verified_chunk.get("doc_name") or _doc_name_for(verified_chunk["doc_id"]),
        page_num=verified_chunk["page_num"],
        chunk_id=verified_chunk["chunk_id"],
        snippet=supporting_span,
        highlighted_text=verified_chunk.get("highlighted_text"),
        score=round(retrieval_score, 4),
    )
    evidence_support = EvidenceSupport(
        verdict=verification_status,
        verifier_model=verification.verifier_model(),
        evidence_grade=grade,
        evidence_label=label,
        support_count=support_count,
        top_rrf_score=round(top_score, 4) if retrieval_score_key == "rrf_score" else None,
        azure_search_score=(
            round(results[0].get("azure_search_score", 0.0), 4)
            if "azure_search_score" in results[0]
            else None
        ),
        azure_reranker_score=(
            round(verified_chunk.get("azure_reranker_score", 0.0), 4)
            if "azure_reranker_score" in verified_chunk
            else None
        ),
        reranker_score=round(verified_chunk.get("reranker_score", 0.0), 4),
        rrf_margin=round(rrf_margin, 4),
        overlap_score=round(overlap, 4),
        supporting_span=supporting_span,
        supporting_page_num=citation.page_num,
        supporting_doc_name=citation.doc_name,
        docs_snapshot_id=docs_snapshot_id,
        index_version=INDEX_VERSION,
    )
    debug_candidates = _build_debug_candidates(
        question,
        candidates,
        verification_results=verification_results,
        verification_reasons=verification_reasons,
    )
    if (
        STRICT_EVIDENCE
        and verification_status != "VERIFIED"
        and grade != "A"
        and not (ALLOW_UNVERIFIED and verification_status == "UNVERIFIED")
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
            question_len=question_len,
            evidence=evidence_support,
            citations=[citation],
            debug_candidates=debug_candidates,
            trace_metadata=trace_metadata,
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
        question_len=question_len,
        answer_len=len(answer_text),
        trace_metadata=trace_metadata,
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


def _retrieval_score_key(results: list[dict]) -> str:
    if not results:
        return "rrf_score"
    if "rrf_score" in results[0]:
        return "rrf_score"
    if "azure_search_score" in results[0]:
        return "azure_search_score"
    return "rrf_score"


def _confidence_score_key(results: list[dict]) -> str:
    if not results:
        return "rrf_score"
    if "azure_search_score" in results[0]:
        if results[0].get("azure_reranker_score") is not None:
            return "azure_reranker_score"
        return "azure_search_score"
    return "rrf_score"


def _confidence_threshold(score_key: str) -> float:
    if score_key == "azure_reranker_score":
        return AZURE_RERANK_MIN
    if score_key == "azure_search_score":
        return AZURE_SEARCH_SCORE_MIN
    return CONF_MIN


def _score_value(chunk: dict, key: str) -> float:
    value = chunk.get(key)
    if value is None:
        return 0.0
    return float(value)


def _build_debug_candidates(
    question: str,
    chunks: list[dict],
    *,
    verification_results: dict[str, tuple[str, str | None]] | None = None,
    verification_reasons: dict[str, str] | None = None,
    reason_override: str | None = None,
) -> list[DebugCandidate]:
    question_tokens = evidence.tokenize(question)
    debug_candidates: list[DebugCandidate] = []
    for chunk in chunks[:3]:
        span = evidence.best_supporting_span(question, chunk["chunk_text"])
        if not span:
            span = _snippet_for(chunk["chunk_text"])
        status = "skipped"
        verified_span = None
        if verification_results:
            status, verified_span = verification_results.get(chunk["chunk_id"], ("skipped", None))
        if verified_span:
            span = verified_span
        overlap_score = evidence.overlap_score(question_tokens, span)
        if reason_override:
            reason = reason_override
        else:
            reason = {
                "verified": "LLM_VERIFIED",
                "rejected": "LLM_REJECTED",
                "unverified": "LLM_UNAVAILABLE",
                "skipped": "NOT_EVALUATED",
            }.get(status, "UNKNOWN")
            if verification_reasons and status in {"verified", "rejected"}:
                reason = verification_reasons.get(chunk["chunk_id"], reason)
        debug_candidates.append(
            DebugCandidate(
                doc_id=chunk["doc_id"],
                doc_name=chunk.get("doc_name") or _doc_name_for(chunk["doc_id"]),
                page_num=chunk["page_num"],
                chunk_id=chunk["chunk_id"],
                rrf_score=round(chunk["rrf_score"], 4) if "rrf_score" in chunk else None,
                azure_search_score=(
                    round(chunk.get("azure_search_score", 0.0), 4)
                    if "azure_search_score" in chunk
                    else None
                ),
                azure_reranker_score=(
                    round(chunk.get("azure_reranker_score", 0.0), 4)
                    if "azure_reranker_score" in chunk
                    else None
                ),
                overlap_score=round(overlap_score, 4),
                verifier_verdict=status.upper(),
                reason=reason,
                snippet=span,
            )
        )
    return debug_candidates


def _build_retrieval_trace(results: list[dict]) -> dict | None:
    if not results:
        return None
    trace: dict[str, float | str | bool | None] = {}
    if "azure_search_score" in results[0]:
        trace["lexical_mode"] = "azure_hybrid"
        trace["azure_search_score_top"] = round(
            results[0].get("azure_search_score", 0.0),
            4,
        )
        if results[0].get("azure_reranker_score") is not None:
            trace["semantic_reranker_enabled"] = True
            trace["azure_reranker_score_top"] = round(
                results[0].get("azure_reranker_score", 0.0),
                4,
            )
        else:
            trace["semantic_reranker_enabled"] = False
    else:
        top_rrf = results[0].get("rrf_score")
        second_rrf = results[1].get("rrf_score") if len(results) > 1 else 0.0
        trace = {
            "top_rrf_score": round(top_rrf, 4) if top_rrf is not None else None,
            "rrf_margin": round(top_rrf - second_rrf, 4) if top_rrf is not None else None,
            "semantic_reranker_enabled": False,
            "lexical_mode": "local_bm25",
        }
        if "bm25_score" in results[0]:
            trace["top_lexical_score"] = round(
                max(r.get("bm25_score", 0.0) for r in results),
                4,
            )
        if "vector_score" in results[0]:
            trace["top_vector_score"] = round(
                max(r.get("vector_score", 0.0) for r in results),
                4,
            )
    if "semantic_requested" in results[0]:
        trace["semantic_requested"] = bool(results[0].get("semantic_requested"))
    if "semantic_used" in results[0]:
        trace["semantic_used"] = bool(results[0].get("semantic_used"))
    if results[0].get("semantic_fallback_reason"):
        trace["semantic_fallback_reason"] = results[0].get("semantic_fallback_reason")
    return {k: v for k, v in trace.items() if v is not None}


def _record_request(
    *,
    request_id: str,
    docs_snapshot_id: str,
    version_snapshot: dict,
    refusal_code: str | None,
    failure_label: str | None,
    start_time: float,
    question_len: int = 0,
    answer_len: int = 0,
    trace_metadata: dict | None = None,
) -> None:
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    if trace_metadata is None:
        trace_metadata = {"question_len": question_len, "answer_len": answer_len}
    else:
        trace_metadata = {**trace_metadata, "question_len": question_len, "answer_len": answer_len}
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
        question_len=question_len,
        answer_len=answer_len,
        trace_metadata=trace_metadata,
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
    question_len: int = 0,
    evidence: EvidenceSupport | None = None,
    citations: list[Citation] | None = None,
    debug_candidates: list[DebugCandidate] | None = None,
    trace_metadata: dict | None = None,
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
        question_len=question_len,
        answer_len=0,
        trace_metadata=trace_metadata,
    )
    return response


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
