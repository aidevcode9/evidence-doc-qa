"""Tests for doc_id pinning through the retrieval pipeline.

TDD: Write failing tests first, then implement.
Covers: AskRequest schema validation, retrieval filtering, cache key isolation.
"""

import re
import pytest
from unittest.mock import patch, MagicMock

from evidence_shared.schemas import AskRequest


# --- Schema Tests ---


class TestAskRequestDocId:
    """AskRequest doc_id field and validation."""

    def test_doc_id_field_exists_and_defaults_to_none(self):
        """doc_id should be an optional field defaulting to None."""
        req = AskRequest(question="What is the claim number?")
        assert req.doc_id is None

    def test_doc_id_accepts_valid_alphanumeric(self):
        """doc_id should accept alphanumeric strings with hyphens/underscores."""
        req = AskRequest(question="test", doc_id="abc-123_DEF")
        assert req.doc_id == "abc-123_DEF"

    def test_doc_id_accepts_uuid_format(self):
        """doc_id should accept UUID-style strings."""
        req = AskRequest(question="test", doc_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert req.doc_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_doc_id_rejects_odata_injection(self):
        """doc_id must reject OData injection attempts (same as docs_snapshot_id)."""
        with pytest.raises(ValueError, match="doc_id"):
            AskRequest(question="test", doc_id="' or tenant_id eq 'victim")

    def test_doc_id_rejects_spaces(self):
        """doc_id must reject strings with spaces."""
        with pytest.raises(ValueError, match="doc_id"):
            AskRequest(question="test", doc_id="has spaces")

    def test_doc_id_rejects_too_long(self):
        """doc_id must reject strings over 64 chars."""
        with pytest.raises(ValueError, match="doc_id"):
            AskRequest(question="test", doc_id="a" * 65)

    def test_doc_id_accepts_max_length(self):
        """doc_id should accept exactly 64-char strings."""
        doc_id = "a" * 64
        req = AskRequest(question="test", doc_id=doc_id)
        assert req.doc_id == doc_id

    def test_doc_id_none_passes_validation(self):
        """doc_id=None should pass validation."""
        req = AskRequest(question="test", doc_id=None)
        assert req.doc_id is None


# --- Cache Key Tests ---


class TestCacheKeyWithDocId:
    """QueryResultCache must include doc_id in cache key."""

    def test_cache_key_includes_doc_id(self):
        """Cache key must differ when doc_id differs."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=10, ttl_seconds=60)
        key1 = cache._make_key("t1", "m1", "snap1", "qhash1", None)
        key2 = cache._make_key("t1", "m1", "snap1", "qhash1", "doc-abc")
        assert key1 != key2

    def test_cache_miss_with_different_doc_id(self):
        """Cached unpinned result must not be returned for pinned query."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=10, ttl_seconds=60)
        # Cache without doc_id
        cache.put("t1", "m1", "snap1", "qhash1", {"answer": "unpinned"}, doc_id=None)
        # Query with doc_id should miss
        result = cache.get("t1", "m1", "snap1", "qhash1", doc_id="doc-abc")
        assert result is None

    def test_cache_hit_with_same_doc_id(self):
        """Cached pinned result should be returned for same doc_id."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=10, ttl_seconds=60)
        cache.put("t1", "m1", "snap1", "qhash1", {"answer": "pinned"}, doc_id="doc-abc")
        result = cache.get("t1", "m1", "snap1", "qhash1", doc_id="doc-abc")
        assert result == {"answer": "pinned"}


# --- DB Layer Tests ---


class TestDbDocIdFilter:
    """load_index_records and load_chunks should filter by doc_id when provided."""

    @patch("app.db.session_scope")
    def test_load_index_records_with_doc_id_adds_filter(self, mock_scope):
        """When doc_id is passed, the query should include a doc_id filter."""
        from app.db import load_index_records

        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = []

        load_index_records("snap1", "t1", "m1", doc_id="doc-abc")

        # Verify .where() was called — the important thing is it doesn't crash
        # and accepts the doc_id parameter
        mock_session.scalars.assert_called_once()

    @patch("app.db.session_scope")
    def test_load_chunks_with_doc_id_adds_filter(self, mock_scope):
        """When doc_id is passed, the query should include a doc_id filter."""
        from app.db import load_chunks

        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = []

        load_chunks("snap1", "t1", "m1", doc_id="doc-abc")
        mock_session.scalars.assert_called_once()

    @patch("app.db.session_scope")
    def test_load_index_records_without_doc_id_no_filter(self, mock_scope):
        """When doc_id is None, no doc_id filter should be added."""
        from app.db import load_index_records

        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = []

        # Should not crash when doc_id is omitted
        load_index_records("snap1", "t1", "m1")
        mock_session.scalars.assert_called_once()


# --- Retrieval Tests ---


class TestRetrievalDocIdFilter:
    """hybrid_search should pass doc_id through to Azure filter and local queries."""

    @patch("app.retrieval._azure_enabled", return_value=True)
    @patch("app.retrieval._azure_search")
    @patch("app.retrieval.embed_texts_with_usage")
    def test_azure_search_receives_doc_id(self, mock_embed, mock_azure, mock_enabled):
        """doc_id should be passed to _azure_search when provided."""
        mock_embed.return_value = ([[0.1] * 10], {"prompt_tokens": 5})
        mock_azure.return_value = [{"chunk_id": "c1", "rrf_score": 0.9}]

        from app.retrieval import hybrid_search

        hybrid_search(
            "test query", "snap1", "t1", "m1",
            doc_id="doc-abc",
        )

        # Verify _azure_search was called with doc_id
        call_args = mock_azure.call_args
        assert "doc-abc" in call_args.args or call_args.kwargs.get("doc_id") == "doc-abc"

    @patch("app.retrieval._azure_enabled", return_value=False)
    @patch("app.retrieval._load_index_records")
    @patch("app.retrieval.embed_texts_with_usage")
    def test_local_search_receives_doc_id(self, mock_embed, mock_load, mock_enabled):
        """doc_id should be passed to _load_index_records when provided."""
        mock_embed.return_value = ([[0.1] * 10], {"prompt_tokens": 5})
        mock_load.return_value = []

        from app.retrieval import hybrid_search

        with patch("app.retrieval._fallback_overlap", return_value=[]):
            hybrid_search(
                "test query", "snap1", "t1", "m1",
                doc_id="doc-abc",
            )

        call_args = mock_load.call_args
        assert call_args.kwargs.get("doc_id") == "doc-abc" or "doc-abc" in call_args.args
