import json
import time
import uuid
from typing import Any

from fastapi import HTTPException

from app import evidence, otel, policy, retrieval, verification, ingestion
from app.db import QAMessage, get_or_create_session, insert_qa_message
from app.config import (
    MODEL_ID,
    PROMPT_VERSION,
    PARSER_MODE,
    RETRIEVAL_VERSION,
    MODEL_COST_INPUT_PER_1K,
    MODEL_COST_OUTPUT_PER_1K,
    EMBEDDINGS_COST_PER_1K,
    STRICT_EVIDENCE,
    ALLOW_UNVERIFIED,
    CONFIDENCE_VERSION,
    CONFIDENCE_THRESHOLD,
    AZURE_SEARCH_SCORE_MIN,
    AZURE_RERANK_MIN,
    INDEX_VERSION,
)
from app.db import get_latest_docs_snapshot_id
from app.schemas import AskRequest, AskResponse, Citation, DebugCandidate, EvidenceSupport, RefusalCode
from app.telemetry import logger, record_telemetry
from app.services import cost, rag
from app.services.cost import CostBreakdown, TraceMetadata

ChunkDict = dict[str, Any]
VersionSnapshot = dict[str, str]


def execute_ask(
    payload: AskRequest,
    session_id: str | None = None,
) -> AskResponse:
    start_time = time.perf_counter()
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    request_id = str(uuid.uuid4())
    docs_snapshot_id = payload.docs_snapshot_id or get_latest_docs_snapshot_id() or "none"
    question_len = len(question)
    question_hash = rag.hash_text(question) if question else None
    
    tokens_in = 0
    tokens_out = 0
    cost_est = 0.0
    cost_breakdown: CostBreakdown = {}
    usage_fallback = False
    
    logger.info(f"Incoming Request [{request_id}] - Snapshot: {docs_snapshot_id}")

    version_snapshot: VersionSnapshot = {
        "request_id": request_id,
        "docs_snapshot_id": docs_snapshot_id,
        "prompt_version": PROMPT_VERSION,
        "verifier_prompt_version": verification.VERIFIER_PROMPT_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "model_id": MODEL_ID,
        "parser_mode": PARSER_MODE,
    }

    trace_metadata: TraceMetadata = {
        "session_id": session_id,
        "question_hash": question_hash,
        "question_len": question_len,
    }
    trace_metadata = {k: v for k, v in trace_metadata.items() if v}

    if policy.is_injection_attempt(question):
        logger.warning(f"Policy Trigger [{request_id}]: Injection Attempt Detected")
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code=RefusalCode.INJECTION_DETECTED,
            reason="Injection heuristics triggered.",
            failure_label="INJECTION_DETECTED",
            start_time=start_time,
            question_len=question_len,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_est=cost_est,
            trace_metadata=trace_metadata,
            session_id=session_id,
            question=question,
        )

    with otel.span("retrieval", docs_snapshot_id=docs_snapshot_id) as retrieval_span:
        search_result = retrieval.hybrid_search(
            question,
            docs_snapshot_id,
            return_usage=True,
        )
        # hybrid_search with return_usage=True returns tuple
        results: list[ChunkDict]
        embedding_usage: dict[str, Any]
        if isinstance(search_result, tuple):
            results, embedding_usage = search_result
        else:
            results = search_result
            embedding_usage = {}
        if retrieval_span and results:
            retrieval_span.set_attribute(
                "retrieval.mode",
                "azure" if "azure_search_score" in results[0] else "local",
            )
    
    if not embedding_usage:
        embedding_usage = {}
    embed_prompt_tokens = int(embedding_usage.get("prompt_tokens") or 0)
    embed_cost = cost.estimate_cost(
        embed_prompt_tokens,
        0,
        EMBEDDINGS_COST_PER_1K,
        0.0,
    )
    tokens_in += embed_prompt_tokens
    cost_est += embed_cost
    embed_estimated = bool(embedding_usage.get("estimated"))
    
    if embed_prompt_tokens or embed_cost or embed_estimated:
        embed_source = embedding_usage.get("source")
        cost.merge_cost_breakdown(
            cost_breakdown,
            "embeddings",
            embed_prompt_tokens,
            0,
            embed_cost,
            embed_estimated,
            str(embed_source) if embed_source else None,
        )
    if embed_estimated:
        usage_fallback = True
        
    retrieval_trace = rag.build_retrieval_trace(results)
    if retrieval_trace:
        trace_metadata = {**trace_metadata, **retrieval_trace}

    attached_trace = cost.attach_cost_trace(trace_metadata, cost_breakdown, usage_fallback)
    if attached_trace is not None:
        trace_metadata = attached_trace

    ret_score_key = rag.retrieval_score_key(results)
    conf_score_key = rag.confidence_score_key(results)
    conf_min = rag.confidence_threshold(conf_score_key)
    conf_version = (
        f"{CONFIDENCE_VERSION}|local={CONFIDENCE_THRESHOLD}|azure_search={AZURE_SEARCH_SCORE_MIN}|azure_rerank={AZURE_RERANK_MIN}"
    )
    confidence_meta: TraceMetadata = {
        "confidence_version": conf_version,
        "confidence_score_key": conf_score_key,
        "confidence_threshold": conf_min,
    }
    trace_metadata = {**trace_metadata, **confidence_meta}

    if not results or rag.score_value(results[0], ret_score_key) == 0.0:
        logger.warning(f"Retrieval Fail [{request_id}]: No evidence found")
        debug_candidates = (
            rag.build_debug_candidates(question, results, reason_override="NO_SUPPORTING_EVIDENCE")
            if results
            else None
        )
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code=RefusalCode.NO_SUPPORTING_EVIDENCE,
            reason="No supporting evidence found.",
            failure_label="NO_EVIDENCE",
            start_time=start_time,
            question_len=question_len,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_est=cost_est,
            debug_candidates=debug_candidates,
            trace_metadata=trace_metadata,
            session_id=session_id,
            question=question,
        )

    # Filter by confidence
    candidates = [
        r for r in results if rag.score_value(r, conf_score_key) >= conf_min
    ]
    if not candidates:
        logger.warning(
            f"Confidence Fail [{request_id}]: No results met threshold {conf_min} ({conf_score_key})"
        )
        debug_candidates = rag.build_debug_candidates(
            question,
            results,
            reason_override="BELOW_CONFIDENCE_THRESHOLD",
        )
        return _emit_refusal(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            version_snapshot=version_snapshot,
            refusal_code=RefusalCode.LOW_RETRIEVAL_CONFIDENCE,
            reason="Insufficient retrieval confidence.",
            failure_label="LOW_CONFIDENCE",
            start_time=start_time,
            question_len=question_len,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_est=cost_est,
            debug_candidates=debug_candidates,
            trace_metadata=trace_metadata,
            session_id=session_id,
            question=question,
        )

    verified_chunk = None
    verification_status = "UNVERIFIED"
    verification_rejected = False
    verification_results: dict[str, tuple[str, str | None]] = {}
    verification_reasons: dict[str, str] = {}
    last_verifier_reason = None
    
    if verification.is_enabled():
        verification_rejected = True
        trace_metadata = {
            **(trace_metadata or {}),
            **verification.verifier_trace_metadata(),
        }
        with otel.span("verification", candidate_count=len(candidates)) as verify_span:
            for chunk in candidates[:3]:
                status, span, reason, usage = verification.verify_relevance(
                    question,
                    chunk["chunk_text"],
                    request_id=request_id,
                    chunk_id=chunk["chunk_id"],
                )
                usage = usage or {}
                v_prompt_t = int(usage.get("prompt_tokens") or 0)
                v_compl_t = int(usage.get("completion_tokens") or 0)
                v_cost = cost.estimate_cost(
                    v_prompt_t,
                    v_compl_t,
                    MODEL_COST_INPUT_PER_1K,
                    MODEL_COST_OUTPUT_PER_1K,
                )
                tokens_in += v_prompt_t
                tokens_out += v_compl_t
                cost_est += v_cost
                v_estimated = bool(usage.get("estimated"))
                
                if v_prompt_t or v_compl_t or v_cost or v_estimated:
                    v_source = usage.get("source")
                    cost.merge_cost_breakdown(
                        cost_breakdown,
                        "verifier",
                        v_prompt_t,
                        v_compl_t,
                        v_cost,
                        v_estimated,
                        str(v_source) if v_source else None,
                    )
                if v_estimated:
                    usage_fallback = True
                    
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

        attached_trace2 = cost.attach_cost_trace(trace_metadata, cost_breakdown, usage_fallback)
        if attached_trace2 is not None:
            trace_metadata = attached_trace2

        if verified_chunk is None:
            if verification_rejected:
                logger.warning(f"Verification Fail [{request_id}]: All top candidates rejected by LLM.")
                return _emit_refusal(
                    request_id=request_id,
                    docs_snapshot_id=docs_snapshot_id,
                    version_snapshot=version_snapshot,
                    refusal_code=RefusalCode.NO_SUPPORTING_EVIDENCE,
                    reason="Retrieval found matches, but they were judged irrelevant by the model.",
                    failure_label="LLM_VERIFICATION_FAILED",
                    start_time=start_time,
                    question_len=question_len,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_est=cost_est,
                    trace_metadata=trace_metadata,
                    session_id=session_id,
                    question=question,
                )

            if STRICT_EVIDENCE and not ALLOW_UNVERIFIED:
                logger.warning(f"Verification Fail [{request_id}]: LLM verification unavailable (strict mode).")
                return _emit_refusal(
                    request_id=request_id,
                    docs_snapshot_id=docs_snapshot_id,
                    version_snapshot=version_snapshot,
                    refusal_code=RefusalCode.POLICY_REFUSAL,
                    reason="LLM verification required but unavailable.",
                    failure_label="LLM_VERIFICATION_UNAVAILABLE",
                    start_time=start_time,
                    question_len=question_len,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_est=cost_est,
                    trace_metadata=trace_metadata,
                    session_id=session_id,
                    question=question,
                )
            verified_chunk = candidates[0]
    else:
        if STRICT_EVIDENCE and not ALLOW_UNVERIFIED:
            logger.warning(f"Verification Fail [{request_id}]: LLM verification disabled (strict mode).")
            return _emit_refusal(
                request_id=request_id,
                docs_snapshot_id=docs_snapshot_id,
                version_snapshot=version_snapshot,
                refusal_code=RefusalCode.POLICY_REFUSAL,
                reason="LLM verification required but not configured.",
                failure_label="LLM_VERIFICATION_DISABLED",
                start_time=start_time,
                question_len=question_len,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_est=cost_est,
                trace_metadata=trace_metadata,
                session_id=session_id,
                question=question,
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

    q_tokens = evidence.tokenize(question)
    supporting_span = evidence.best_supporting_span(question, verified_chunk["chunk_text"])
    if not supporting_span:
        supporting_span = rag.snippet_for(verified_chunk["chunk_text"])
    
    # Use verified span if available
    if verification_status == "VERIFIED" and "verified_span" in locals() and verified_span: # verified_span comes from the loop
         supporting_span = verified_span
    
    overlap = evidence.overlap_score(q_tokens, supporting_span)
    if verification_status == "VERIFIED":
        overlap = max(overlap, 0.6)
    
    top_score = rag.score_value(results[0], ret_score_key)
    second_score = rag.score_value(results[1], ret_score_key) if len(results) > 1 else 0.0
    rrf_margin = top_score - second_score
    ret_score = rag.score_value(verified_chunk, ret_score_key)
    azure_rerank_score = rag.score_value(verified_chunk, "azure_reranker_score")
    
    support_count = sum(
        1
        for r in candidates
        if evidence.overlap_score(q_tokens, r["chunk_text"]) >= 0.2
    )
    support_count = max(1, support_count)
    
    with otel.span(
        "evidence.grade",
        verification_status=verification_status,
        retrieval_score=ret_score,
        reranker_score=azure_rerank_score,
        overlap_score=overlap,
    ):
        grade, label = evidence.evidence_grade(
            verification_status == "VERIFIED",
            ret_score,
            rrf_margin,
            overlap,
            reranker_score=azure_rerank_score,
        )
        
    # Build multiple citations from verified/high-confidence chunks (FR-023)
    verified_chunks = [verified_chunk]
    for chunk in candidates[:3]:
        chunk_id = chunk["chunk_id"]
        if chunk_id != verified_chunk["chunk_id"]:
            status, _ = verification_results.get(chunk_id, ("skipped", None))
            if status == "verified":
                verified_chunks.append(chunk)
        if len(verified_chunks) >= 3:
            break

    citations = []
    answer_parts = []
    for idx, chunk in enumerate(verified_chunks, start=1):
        # Get span for this chunk
        chunk_span = verification_results.get(chunk["chunk_id"], (None, None))[1]
        if not chunk_span:
            chunk_span = evidence.best_supporting_span(question, chunk["chunk_text"])
        if not chunk_span:
            chunk_span = rag.snippet_for(chunk["chunk_text"])

        doc_name = chunk.get("doc_name") or rag.doc_name_for(chunk["doc_id"])
        page = chunk["page_num"]
        chunk_score = rag.score_value(chunk, ret_score_key)

        citation = Citation(
            citation_index=idx,
            doc_id=chunk["doc_id"],
            doc_name=doc_name,
            page_num=page,
            page_end=chunk.get("page_end", page),
            char_start=chunk.get("char_start", 0),
            char_end=chunk.get("char_end", 0),
            chunk_id=chunk["chunk_id"],
            snippet=chunk_span,
            highlighted_text=chunk.get("highlighted_text"),
            score=round(chunk_score, 4),
        )
        citations.append(citation)

        # Build answer part with [N] marker (FR-023)
        if idx == 1:
            answer_parts.append(f"According to {doc_name} (page {page}) [{idx}], {chunk_span}")
        else:
            answer_parts.append(f"Additionally, {doc_name} (page {page}) [{idx}] states: {chunk_span}")
    
    # Use first citation for evidence support metadata
    primary_citation = citations[0]

    evidence_support = EvidenceSupport(
        verdict=verification_status,
        verifier_model=verification.verifier_model(),
        evidence_grade=grade,
        evidence_label=label,
        support_count=support_count,
        top_rrf_score=round(top_score, 4) if ret_score_key == "rrf_score" else None,
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
        supporting_page_num=primary_citation.page_num,
        supporting_doc_name=primary_citation.doc_name,
        docs_snapshot_id=docs_snapshot_id,
        index_version=INDEX_VERSION,
        confidence_threshold=conf_min,  # FR-024: Show threshold in response
    )
    
    debug_candidates = rag.build_debug_candidates(
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
            refusal_code=RefusalCode.LOW_RETRIEVAL_CONFIDENCE,
            reason="Evidence strength below Strong threshold.",
            failure_label="EVIDENCE_WEAK",
            start_time=start_time,
            question_len=question_len,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_est=cost_est,
            evidence=evidence_support,
            citations=citations,
            debug_candidates=debug_candidates,
            trace_metadata=trace_metadata,
            session_id=session_id,
            question=question,
        )

    # Build answer with [N] citation markers (FR-023)
    answer_text = ". ".join(answer_parts) + "."

    response = AskResponse(
        request_id=request_id,
        answer_text=answer_text,
        citations=citations,
        refusal_code=None,
        reason=None,
        evidence=evidence_support,
        debug_candidates=debug_candidates,
        version_snapshot=version_snapshot,
    )
    
    _record_request_internal(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        version_snapshot=version_snapshot,
        refusal_code=None,
        failure_label=None,
        start_time=start_time,
        question_len=question_len,
        answer_len=len(answer_text),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_est=cost_est,
        trace_metadata=trace_metadata,
    )

    # Store Q&A messages for export (FR-032)
    if session_id:
        _store_qa_messages(
            session_id=session_id,
            docs_snapshot_id=docs_snapshot_id,
            question=question,
            request_id=request_id,
            answer_text=answer_text,
            citations=citations,
            evidence=evidence_support,
            refusal_code=None,
            version_snapshot=version_snapshot,
        )

    logger.info(f"Success [{request_id}]: Response returned with {len(citations)} citation(s) from {primary_citation.doc_name}")
    return response


def _record_request_internal(
    *,
    request_id: str,
    docs_snapshot_id: str,
    version_snapshot: VersionSnapshot,
    refusal_code: RefusalCode | None,
    failure_label: str | None,
    start_time: float,
    question_len: int = 0,
    answer_len: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_est: float = 0.0,
    trace_metadata: TraceMetadata | None = None,
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
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_est=cost_est,
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
    version_snapshot: VersionSnapshot,
    refusal_code: RefusalCode,
    reason: str,
    failure_label: str,
    start_time: float,
    question_len: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_est: float = 0.0,
    evidence: EvidenceSupport | None = None,
    citations: list[Citation] | None = None,
    debug_candidates: list[DebugCandidate] | None = None,
    trace_metadata: TraceMetadata | None = None,
    session_id: str | None = None,
    question: str | None = None,
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
    _record_request_internal(
        request_id=request_id,
        docs_snapshot_id=docs_snapshot_id,
        version_snapshot=version_snapshot,
        refusal_code=refusal_code,
        failure_label=failure_label,
        start_time=start_time,
        question_len=question_len,
        answer_len=0,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_est=cost_est,
        trace_metadata=trace_metadata,
    )

    # Store Q&A messages for export (FR-032) - even for refusals
    if session_id and question:
        _store_qa_messages(
            session_id=session_id,
            docs_snapshot_id=docs_snapshot_id,
            question=question,
            request_id=request_id,
            answer_text=reason,
            citations=citations,
            evidence=evidence,
            refusal_code=refusal_code,
            version_snapshot=version_snapshot,
        )

    return response


def _store_qa_messages(
    *,
    session_id: str,
    docs_snapshot_id: str,
    question: str,
    request_id: str,
    answer_text: str | None,
    citations: list[Citation] | None,
    evidence: EvidenceSupport | None,
    refusal_code: RefusalCode | None,
    version_snapshot: VersionSnapshot,
) -> None:
    """Store user question and assistant response as QA messages (FR-032)."""
    try:
        # Ensure session exists
        get_or_create_session(session_id, docs_snapshot_id)

        timestamp = ingestion.utc_now()

        # Store user message
        user_message = QAMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=question,
            citations_json=None,
            evidence_json=None,
            refusal_code=None,
            version_snapshot_json=None,
            created_at_utc=timestamp,
        )
        insert_qa_message(user_message)

        # Store assistant response
        assistant_message = QAMessage(
            message_id=request_id,
            session_id=session_id,
            role="assistant",
            content=answer_text or "",
            citations_json=(
                json.dumps([c.model_dump() for c in citations])
                if citations
                else None
            ),
            evidence_json=(
                json.dumps(evidence.model_dump())
                if evidence
                else None
            ),
            refusal_code=str(refusal_code.value) if refusal_code else None,
            version_snapshot_json=json.dumps(version_snapshot),
            created_at_utc=timestamp,
        )
        insert_qa_message(assistant_message)
    except Exception as e:
        # Don't fail the request if message storage fails
        logger.warning(f"Failed to store QA messages: {e}")
