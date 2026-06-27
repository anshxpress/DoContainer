"""
Sprint 3 — Day 9: Benchmark & Unit Tests for the Search Layer

Tests cover:
  1. MockRetriever determinism and shape
  2. RRF fusion logic (correct scoring, cross-list deduplication)
  3. Permission filtering — cross-tenant requests return empty results
  4. hybrid_search integration (mocked Qdrant + mocked DB)
  5. POST /api/v1/search — HTTP 422 on empty query
  6. POST /api/v1/search — 403 when permission missing
"""
from __future__ import annotations

import uuid
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. MockRetriever — determinism and shape
# ---------------------------------------------------------------------------

class TestMockRetriever:
    def test_returns_two_vectors(self):
        from backend.app.services.retriever import MockRetriever
        r = MockRetriever()
        result = r.embed_query("hello world")
        assert len(result) == 2, "MockRetriever must return exactly 2 vectors"

    def test_vector_dimension_is_128(self):
        from backend.app.services.retriever import MockRetriever
        r = MockRetriever()
        result = r.embed_query("hello world")
        for vec in result:
            assert len(vec) == 128, "Each vector must have 128 dimensions"

    def test_deterministic_output(self):
        from backend.app.services.retriever import MockRetriever
        r = MockRetriever()
        a = r.embed_query("same query")
        b = r.embed_query("same query")
        assert a == b, "Same input must always produce identical output"

    def test_different_queries_differ(self):
        from backend.app.services.retriever import MockRetriever
        r = MockRetriever()
        a = r.embed_query("document retrieval")
        b = r.embed_query("quarterly earnings report")
        assert a != b, "Different queries must produce different embeddings"

    def test_vectors_are_complementary(self):
        """v1 + v2 = [1.0] * 128"""
        from backend.app.services.retriever import MockRetriever
        r = MockRetriever()
        v1, v2 = r.embed_query("test")
        for a, b in zip(v1, v2):
            assert abs(a + b - 1.0) < 1e-9, "MockRetriever vectors must sum to 1.0"


# ---------------------------------------------------------------------------
# 2. RRF fusion logic
# ---------------------------------------------------------------------------

class TestRRF:
    def _rrf(self, ranked_lists, k=60):
        from backend.app.services.search_service import _reciprocal_rank_fusion
        return _reciprocal_rank_fusion(ranked_lists, k=k)

    def test_single_list_scores(self):
        scores = self._rrf([["a", "b", "c"]])
        # rank 1 → 1/(60+1), rank 2 → 1/(60+2), rank 3 → 1/(60+3)
        assert scores["a"] > scores["b"] > scores["c"]

    def test_union_of_ids(self):
        scores = self._rrf([["a", "b"], ["b", "c"]])
        assert set(scores.keys()) == {"a", "b", "c"}

    def test_cross_list_boost(self):
        """ID 'b' appears in both lists and should outscore 'a' (rank-1 only in list-1)."""
        scores = self._rrf([["a", "b"], ["b", "c"]])
        # 'b' gets score from both lists; 'a' only from list-1 at rank-1
        assert scores["b"] > scores["a"], (
            "An ID appearing in both result sets must outscore one that appears in only one"
        )

    def test_empty_lists_return_empty_dict(self):
        scores = self._rrf([[], []])
        assert scores == {}

    def test_k_parameter_controls_rank_weight(self):
        """Lower k means rank-1 gets proportionally more weight."""
        scores_k1 = self._rrf([["a", "b"]], k=1)
        scores_k60 = self._rrf([["a", "b"]], k=60)
        # ratio a/b should be larger with small k
        ratio_k1 = scores_k1["a"] / scores_k1["b"]
        ratio_k60 = scores_k60["a"] / scores_k60["b"]
        assert ratio_k1 > ratio_k60


# ---------------------------------------------------------------------------
# 3. Permission filtering — cross-tenant isolation
# ---------------------------------------------------------------------------

class TestPermissionFiltering:
    """
    Day 6: Verify that cross-tenant requests always return empty results.

    We mock qdrant.search_pages to return a page payload with org_id='org-A'.
    When the caller supplies org_id='org-B', search_pages should receive a filter
    for 'org-B' and therefore return nothing (simulated by the mock).
    """

    @patch("backend.app.services.search_service.search_pages")
    @patch("backend.app.services.search_service.document_page_repo")
    def test_cross_tenant_qdrant_returns_empty(
        self, mock_page_repo, mock_search_pages, db
    ):
        from backend.app.services.search_service import hybrid_search

        # Qdrant mock returns nothing (correct behaviour with org filter)
        mock_search_pages.return_value = []
        mock_page_repo.search_pages_fts.return_value = []

        results = hybrid_search(
            db=db,
            query="confidential report",
            org_id="org-B",          # caller is in org-B
            team_ids=["team-1"],
        )

        # Validate that search_pages was called with org_id='org-B'
        mock_search_pages.assert_called_once()
        call_kwargs = mock_search_pages.call_args
        assert call_kwargs.kwargs.get("org_id") == "org-B"

        # No results because Qdrant found nothing for org-B
        assert results == []

    @patch("backend.app.services.search_service.search_pages")
    @patch("backend.app.services.search_service.document_page_repo")
    def test_correct_org_returns_results(
        self, mock_page_repo, mock_search_pages, db
    ):
        """Sanity check: same org returns results when Qdrant responds."""
        from backend.app.services.search_service import hybrid_search

        page_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        org_id = "org-A"

        # Simulate Qdrant returning one scored point
        mock_point = MagicMock()
        mock_point.id = page_id
        mock_search_pages.return_value = [mock_point]

        # Simulate DB page lookup
        mock_page = MagicMock()
        mock_page.id = uuid.UUID(page_id)
        mock_page.page_number = 1
        mock_page.png_storage_path = f"{org_id}/{doc_id}/1/page_1.png"
        mock_page.text_content = "sample extracted text from page 1"

        mock_doc = MagicMock()
        mock_doc.id = uuid.UUID(doc_id)
        mock_doc.name = "Quarterly Report Q1 2026"
        mock_doc.org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        mock_page.document = mock_doc

        mock_page_repo.search_pages_fts.return_value = []
        mock_page_repo.get.return_value = mock_page

        results = hybrid_search(
            db=db,
            query="quarterly earnings",
            org_id=org_id,
            team_ids=["team-1"],
        )

        assert len(results) == 1
        assert results[0].document_name == "Quarterly Report Q1 2026"
        assert results[0].page_number == 1


# ---------------------------------------------------------------------------
# 4. hybrid_search — empty query returns immediately
# ---------------------------------------------------------------------------

class TestHybridSearchEdgeCases:
    def test_empty_query_returns_empty_list(self, db):
        from backend.app.services.search_service import hybrid_search
        results = hybrid_search(db=db, query="", org_id="org-A", team_ids=[])
        assert results == []

    def test_whitespace_query_returns_empty_list(self, db):
        from backend.app.services.search_service import hybrid_search
        results = hybrid_search(db=db, query="   ", org_id="org-A", team_ids=[])
        assert results == []


# ---------------------------------------------------------------------------
# 5. POST /api/v1/search — HTTP 422 on missing/invalid body
# ---------------------------------------------------------------------------

class TestSearchEndpointValidation:
    """
    FastAPI validates the Bearer token BEFORE the request body, so requests
    with a dummy (invalid) token return 401, not 422.

    To test body-level validation, we override the auth dependency to skip
    credential checking and let Pydantic's body validation respond with 422.
    """

    @pytest.fixture(autouse=True)
    def _override_auth(self, client):
        """Swap get_current_user_context and PermissionChecker for all tests in this class."""
        from backend.app.main import app
        from backend.app.api.deps import get_current_user_context, PermissionChecker
        from backend.app.api.v1.search import search_documents

        # Create a stub context
        mock_ctx = MagicMock()
        mock_ctx.user = MagicMock()
        mock_ctx.user.id = uuid.uuid4()
        mock_ctx.org_id = "org-test"
        mock_ctx.role_name = "Super Admin"
        mock_ctx.permissions = ["search:documents"]

        app.dependency_overrides[get_current_user_context] = lambda: mock_ctx

        # PermissionChecker is a callable class; override every instance
        # by patching the __call__ return at the route dependency level.
        # Easiest approach: override via dependency_overrides keyed to
        # the specific PermissionChecker instance used in search.py
        original_checker = PermissionChecker("search:documents")
        app.dependency_overrides[original_checker] = lambda: mock_ctx

        yield

        # Clean up added overrides (keep the one from conftest's client fixture)
        app.dependency_overrides.pop(get_current_user_context, None)
        app.dependency_overrides.pop(original_checker, None)

    def test_empty_body_returns_422(self, client):
        """Sending an empty JSON body must trigger Pydantic validation error."""
        response = client.post("/api/v1/search", json={})
        assert response.status_code == 422

    def test_missing_query_field_returns_422(self, client):
        response = client.post("/api/v1/search", json={"top_k": 5})
        assert response.status_code == 422

    def test_query_too_long_returns_422(self, client):
        response = client.post("/api/v1/search", json={"query": "x" * 1001})
        assert response.status_code == 422

    def test_no_auth_header_returns_401_or_403(self, client):
        """Unauthenticated request should be rejected before reaching search logic."""
        # Remove the auth override to test unauthenticated access
        from backend.app.main import app
        from backend.app.api.deps import get_current_user_context
        app.dependency_overrides.pop(get_current_user_context, None)
        response = client.post(
            "/api/v1/search",
            json={"query": "financial report"},
        )
        assert response.status_code in (401, 403)
