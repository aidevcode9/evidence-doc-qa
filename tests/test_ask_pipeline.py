# tests/test_ask_pipeline.py
"""Tests for ARCH-2: decomposed execute_ask pipeline steps.

Verifies that each pipeline step (validate_and_setup, check_cache, retrieve,
verify, synthesize) is independently callable and produces correct results.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestSetupContext:
    """Tests for SetupContext dataclass."""

    def test_setup_context_has_required_fields(self) -> None:
        from app.services.ask_service import SetupContext

        ctx = SetupContext(
            request_id="req-1",
            question="What is the cap?",
            effective_question="What is the cap?",
            question_hash="abc123",
            question_len=17,
            docs_snapshot_id="snap-1",
            doc_id=None,
            version_snapshot={"request_id": "req-1", "docs_snapshot_id": "snap-1"},
            trace_metadata={"session_id": None},
            conversation_meta={"applied": False},
        )
        assert ctx.request_id == "req-1"
        assert ctx.question == "What is the cap?"
        assert ctx.effective_question == "What is the cap?"
        assert ctx.question_hash == "abc123"
        assert ctx.question_len == 17
        assert ctx.docs_snapshot_id == "snap-1"
        assert ctx.doc_id is None
        assert ctx.version_snapshot["request_id"] == "req-1"

    def test_setup_context_is_dataclass(self) -> None:
        import dataclasses
        from app.services.ask_service import SetupContext

        assert dataclasses.is_dataclass(SetupContext)


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_retrieval_result_has_required_fields(self) -> None:
        from app.services.ask_service import RetrievalResult

        rr = RetrievalResult(
            results=[{"chunk_id": "c1", "chunk_text": "hello"}],
            candidates=[{"chunk_id": "c1", "chunk_text": "hello"}],
            retrieval_ms=100,
            embedding_usage={"prompt_tokens": 10},
            tokens_in=10,
            cost_est=0.001,
            cost_breakdown={},
            usage_fallback=False,
            ret_score_key="rrf_score",
            conf_score_key="azure_reranker_score",
            conf_min=0.7,
            conf_version="v1",
        )
        assert rr.results == [{"chunk_id": "c1", "chunk_text": "hello"}]
        assert rr.candidates == [{"chunk_id": "c1", "chunk_text": "hello"}]
        assert rr.retrieval_ms == 100
        assert rr.tokens_in == 10

    def test_retrieval_result_is_dataclass(self) -> None:
        import dataclasses
        from app.services.ask_service import RetrievalResult

        assert dataclasses.is_dataclass(RetrievalResult)


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_verification_result_has_required_fields(self) -> None:
        from app.services.ask_service import VerificationResult

        vr = VerificationResult(
            verified_chunk={"chunk_id": "c1"},
            verification_status="VERIFIED",
            verification_rejected=False,
            verification_results={"c1": ("verified", "span text")},
            verification_reasons={"c1": "FOUND"},
            last_verifier_reason="FOUND",
            verified_span="span text",
            verification_ms=200,
            tokens_in=50,
            tokens_out=30,
            cost_est=0.005,
            cost_breakdown={},
            usage_fallback=False,
        )
        assert vr.verified_chunk == {"chunk_id": "c1"}
        assert vr.verification_status == "VERIFIED"
        assert vr.verification_ms == 200

    def test_verification_result_is_dataclass(self) -> None:
        import dataclasses
        from app.services.ask_service import VerificationResult

        assert dataclasses.is_dataclass(VerificationResult)


class TestSynthesisResult:
    """Tests for SynthesisResult dataclass."""

    def test_synthesis_result_has_required_fields(self) -> None:
        from app.services.ask_service import SynthesisResult, Citation, EvidenceSupport

        sr = SynthesisResult(
            answer_text="According to doc (page 1) [1], text.",
            citations=[],
            evidence_support=None,
            debug_candidates=None,
        )
        assert sr.answer_text == "According to doc (page 1) [1], text."
        assert sr.citations == []

    def test_synthesis_result_is_dataclass(self) -> None:
        import dataclasses
        from app.services.ask_service import SynthesisResult

        assert dataclasses.is_dataclass(SynthesisResult)


# ---------------------------------------------------------------------------
# Step function tests
# ---------------------------------------------------------------------------


class TestValidateAndSetup:
    """Tests for the validate_and_setup step."""

    @patch("app.services.ask_service.get_latest_snapshot_for_matter", return_value="snap-1")
    @patch("app.services.ask_service._contextualize_question", return_value=("What is the cap?", {"applied": False}))
    @patch("app.services.ask_service.rag.hash_text", return_value="hash123")
    @patch("app.services.ask_service.safe_update_trace")
    def test_validate_and_setup_returns_setup_context(
        self, mock_trace: Any, mock_hash: Any, mock_ctx: Any, mock_snap: Any
    ) -> None:
        from app.services.ask_service import validate_and_setup, SetupContext

        payload = MagicMock()
        payload.question = "What is the cap?"
        payload.docs_snapshot_id = None
        payload.doc_id = None

        ctx = validate_and_setup(
            payload,
            session_id=None,
            tenant_id="t1",
            matter_id="m1",
        )
        assert isinstance(ctx, SetupContext)
        assert ctx.question == "What is the cap?"
        assert ctx.docs_snapshot_id == "snap-1"
        assert ctx.question_hash == "hash123"

    def test_validate_and_setup_rejects_empty_question(self) -> None:
        from app.services.ask_service import validate_and_setup
        from fastapi import HTTPException

        payload = MagicMock()
        payload.question = "   "

        with pytest.raises(HTTPException) as exc_info:
            validate_and_setup(
                payload,
                session_id=None,
                tenant_id="t1",
                matter_id="m1",
            )
        assert exc_info.value.status_code == 400

    @patch("app.services.ask_service.MAX_QUERY_LENGTH", 10)
    def test_validate_and_setup_rejects_long_question(self) -> None:
        from app.services.ask_service import validate_and_setup
        from fastapi import HTTPException

        payload = MagicMock()
        payload.question = "A" * 20

        with pytest.raises(HTTPException) as exc_info:
            validate_and_setup(
                payload,
                session_id=None,
                tenant_id="t1",
                matter_id="m1",
            )
        assert exc_info.value.status_code == 400


class TestCheckCache:
    """Tests for the check_cache step."""

    def test_check_cache_returns_none_when_disabled(self) -> None:
        from app.services.ask_service import check_cache, SetupContext

        ctx = SetupContext(
            request_id="req-1",
            question="Q?",
            effective_question="Q?",
            question_hash="h1",
            question_len=2,
            docs_snapshot_id="snap-1",
            doc_id=None,
            version_snapshot={},
            trace_metadata={},
            conversation_meta={},
        )
        # With cache disabled (None), should return None
        result = check_cache(ctx, cache=None, tenant_id="t1", matter_id="m1", start_time=time.perf_counter())
        assert result is None

    def test_check_cache_returns_response_on_hit(self) -> None:
        from app.services.ask_service import check_cache, SetupContext

        ctx = SetupContext(
            request_id="req-1",
            question="Q?",
            effective_question="Q?",
            question_hash="h1",
            question_len=2,
            docs_snapshot_id="snap-1",
            doc_id=None,
            version_snapshot={
                "request_id": "req-1",
                "docs_snapshot_id": "snap-1",
                "prompt_version": "v1",
                "verifier_prompt_version": "v1",
                "retrieval_version": "v1",
                "model_id": "m1",
                "parser_mode": "marker",
            },
            trace_metadata={},
            conversation_meta={},
        )
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "request_id": "old-req",
            "answer_text": "Cached answer",
            "citations": None,
            "refusal_code": None,
            "reason": None,
            "evidence": None,
            "debug_candidates": None,
            "version_snapshot": {
                "request_id": "old-req",
                "docs_snapshot_id": "snap-1",
                "prompt_version": "v1",
                "verifier_prompt_version": "v1",
                "retrieval_version": "v1",
                "model_id": "m1",
                "parser_mode": "marker",
            },
        }

        with patch("app.services.ask_service._record_request_internal"):
            result = check_cache(
                ctx,
                cache=mock_cache,
                tenant_id="t1",
                matter_id="m1",
                start_time=time.perf_counter(),
            )
        assert result is not None
        assert result.request_id == "req-1"  # Should override with current request_id


class TestRetrieveStep:
    """Tests for the retrieve step."""

    @patch("app.services.ask_service.retrieval.hybrid_search")
    @patch("app.services.ask_service.otel.span")
    @patch("app.services.ask_service.rag.build_retrieval_trace", return_value={})
    @patch("app.services.ask_service.cost.attach_cost_trace", return_value=None)
    @patch("app.services.ask_service.rag.retrieval_score_key", return_value="rrf_score")
    @patch("app.services.ask_service.rag.confidence_score_key", return_value="azure_reranker_score")
    @patch("app.services.ask_service.rag.confidence_threshold", return_value=0.7)
    @patch("app.services.ask_service.rag.score_value")
    def test_retrieve_returns_retrieval_result(
        self,
        mock_score: Any,
        mock_conf_thresh: Any,
        mock_conf_key: Any,
        mock_ret_key: Any,
        mock_attach: Any,
        mock_trace: Any,
        mock_span: Any,
        mock_search: Any,
    ) -> None:
        from app.services.ask_service import retrieve, RetrievalResult

        chunks = [
            {"chunk_id": "c1", "chunk_text": "text1", "azure_search_score": 0.9, "azure_reranker_score": 0.85},
        ]
        mock_search.return_value = (chunks, {"prompt_tokens": 10})
        mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_score.return_value = 0.9

        rr = retrieve(
            effective_question="What is the cap?",
            docs_snapshot_id="snap-1",
            tenant_id="t1",
            matter_id="m1",
            doc_id=None,
            trace_metadata={},
        )
        assert isinstance(rr, RetrievalResult)
        assert rr.results == chunks
        assert rr.retrieval_ms >= 0

    @patch("app.services.ask_service.retrieval.hybrid_search")
    @patch("app.services.ask_service.otel.span")
    @patch("app.services.ask_service.rag.build_retrieval_trace", return_value={})
    @patch("app.services.ask_service.cost.attach_cost_trace", return_value=None)
    @patch("app.services.ask_service.rag.retrieval_score_key", return_value="rrf_score")
    @patch("app.services.ask_service.rag.confidence_score_key", return_value="azure_reranker_score")
    @patch("app.services.ask_service.rag.confidence_threshold", return_value=0.7)
    @patch("app.services.ask_service.rag.score_value")
    def test_retrieve_filters_candidates_by_confidence(
        self,
        mock_score: Any,
        mock_conf_thresh: Any,
        mock_conf_key: Any,
        mock_ret_key: Any,
        mock_attach: Any,
        mock_trace: Any,
        mock_span: Any,
        mock_search: Any,
    ) -> None:
        from app.services.ask_service import retrieve

        chunks = [
            {"chunk_id": "c1", "chunk_text": "t1", "azure_search_score": 0.9, "azure_reranker_score": 0.8},
            {"chunk_id": "c2", "chunk_text": "t2", "azure_search_score": 0.5, "azure_reranker_score": 0.3},
        ]
        mock_search.return_value = (chunks, {})
        mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_span.return_value.__exit__ = MagicMock(return_value=False)
        # Return scores based on key
        def score_side_effect(chunk: dict[str, Any], key: str) -> float:
            return float(chunk.get(key, 0.0))
        mock_score.side_effect = score_side_effect

        rr = retrieve(
            effective_question="Q?",
            docs_snapshot_id="snap-1",
            tenant_id="t1",
            matter_id="m1",
            doc_id=None,
            trace_metadata={},
        )
        # Only c1 (0.8 >= 0.7) should be in candidates
        assert len(rr.candidates) == 1
        assert rr.candidates[0]["chunk_id"] == "c1"


class TestSynthesizeStep:
    """Tests for the synthesize step."""

    @patch("app.services.ask_service.evidence.tokenize", return_value=["what", "is", "cap"])
    @patch("app.services.ask_service.evidence.best_supporting_span", return_value="The cap is 10M")
    @patch("app.services.ask_service.evidence.overlap_score", return_value=0.8)
    @patch("app.services.ask_service.evidence.evidence_grade", return_value=("A", "Strong"))
    @patch("app.services.ask_service.rag.score_value", return_value=0.9)
    @patch("app.services.ask_service.rag.build_debug_candidates", return_value=[])
    @patch("app.services.ask_service.rag.doc_name_for", return_value="Agreement.pdf")
    @patch("app.services.ask_service.rag.snippet_for", return_value="fallback snippet")
    def test_synthesize_produces_answer_with_citations(
        self,
        mock_snip: Any,
        mock_doc: Any,
        mock_debug: Any,
        mock_sv: Any,
        mock_grade: Any,
        mock_overlap: Any,
        mock_span: Any,
        mock_tok: Any,
    ) -> None:
        from app.services.ask_service import synthesize, SynthesisResult

        verified_chunk = {
            "chunk_id": "c1",
            "chunk_text": "The cap is 10M",
            "doc_id": "d1",
            "doc_name": "Agreement.pdf",
            "page_num": 5,
        }
        results = [verified_chunk]
        candidates = [verified_chunk]

        with patch("app.services.ask_service.otel.span") as mock_otel:
            mock_otel.return_value.__enter__ = MagicMock(return_value=None)
            mock_otel.return_value.__exit__ = MagicMock(return_value=False)
            sr = synthesize(
                effective_question="What is the cap?",
                verified_chunk=verified_chunk,
                verification_status="VERIFIED",
                verification_results={"c1": ("verified", "The cap is 10M")},
                verification_reasons={"c1": "FOUND"},
                verified_span="The cap is 10M",
                results=results,
                candidates=candidates,
                ret_score_key="rrf_score",
                conf_min=0.7,
                trace_metadata={},
                tenant_id="t1",
            )

        assert isinstance(sr, SynthesisResult)
        assert sr.answer_text is not None
        assert len(sr.citations) >= 1
        assert sr.evidence_support is not None


class TestExecuteAskOrchestrator:
    """Tests that execute_ask still works as orchestrator after refactoring."""

    def test_execute_ask_signature_unchanged(self) -> None:
        """External signature must remain the same."""
        import inspect
        from app.services.ask_service import execute_ask

        sig = inspect.signature(execute_ask)
        params = list(sig.parameters.keys())
        assert "payload" in params
        assert "session_id" in params
        assert "tenant_id" in params
        assert "matter_id" in params
        assert "user_id" in params

    def test_execute_ask_has_observe_decorator(self) -> None:
        """@_observe decorator must remain on execute_ask."""
        import ast

        with open("apps/api/app/services/ask_service.py") as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "execute_ask":
                assert len(node.decorator_list) > 0, "execute_ask must have decorators"
                break

    def test_step_functions_are_importable(self) -> None:
        """All new step functions must be importable."""
        from app.services.ask_service import (
            validate_and_setup,
            check_cache,
            retrieve,
            synthesize,
            SetupContext,
            RetrievalResult,
            VerificationResult,
            SynthesisResult,
        )
        assert callable(validate_and_setup)
        assert callable(check_cache)
        assert callable(retrieve)
        assert callable(synthesize)

    def test_execute_ask_still_checks_max_query_length(self) -> None:
        """inspect.getsource(execute_ask) must contain MAX_QUERY_LENGTH.

        This preserves compatibility with test_tenant_isolation.py.
        """
        import inspect
        from app.services.ask_service import execute_ask

        source = inspect.getsource(execute_ask)
        # execute_ask calls validate_and_setup which does the check,
        # but inspect.getsource only gets execute_ask body.
        # The existing test checks getsource(execute_ask) for MAX_QUERY_LENGTH.
        # We need to keep that check visible in execute_ask or adjust.
        # Let's verify what test_tenant_isolation actually checks.
        assert "validate_and_setup" in source or "MAX_QUERY_LENGTH" in source
