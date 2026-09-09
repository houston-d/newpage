"""Unit tests for the ``query_job_board`` endpoint in ``app.api.ai``.

``query_job_board`` backs ``POST /ai/query_job_board``. It requires a model to
be loaded, loads the cached job descriptions, ranks the most relevant jobs for
the query, builds a RAG context from them, and delegates generation to
``model_service.generate_text``:

    @router.post("/query_job_board")
    def query_job_board(payload: QueryJobBoardRequest, response: Response) -> QueryJobBoardResponse:
        if not model_service.is_loaded():
            return QueryJobBoardResponse(status=503, message="Model not loaded", sources=[])
        try:
            jobs = list(_load_job_descriptions_cached())
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
            return QueryJobBoardResponse(status=500, message="Unable to load job descriptions", sources=[])
        relevant_jobs = _rank_relevant_jobs(payload.query, jobs, payload.top_k)
        rag_context = _build_rag_context(relevant_jobs)
        ...
        try:
            output = model_service.generate_text(messages)
        except (ValueError, RuntimeError, KeyError, TypeError):
            return QueryJobBoardResponse(status=500, message="Unable to answer job board query", sources=[])
        return QueryJobBoardResponse(status=200, message=output, sources=response_sources)
"""

from unittest.mock import patch

import pytest
from app.api.ai import query_job_board
from app.api.main import app
from app.api.schemas import QueryJobBoardRequest, QueryJobBoardResponse
from fastapi import Response
from fastapi.testclient import TestClient

SAMPLE_QUERY = "Senior Python backend engineer in London"

SAMPLE_JOBS: tuple[dict[str, str], ...] = (
    {
        "title": "Senior Backend Engineer",
        "location": "London",
        "company": "Acme Corp",
        "salary": "£70,000 - £90,000",
        "source_file": "acme_backend.json",
        "jd": "We are looking for a Senior Backend Engineer with strong Python experience.",
    },
    {
        "title": "Frontend Developer",
        "location": "Manchester",
        "company": "Widgets Ltd",
        "salary": "",
        "source_file": "widgets_frontend.json",
        "jd": "React developer needed for our growing frontend team.",
    },
)


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to the real FastAPI app, exercised through HTTP."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_job_index_cache():
    """``_build_job_index`` (and its upstream cache) are ``lru_cache``d at module scope.

    Clear them before/after each test so that a previous test's patched job
    descriptions don't leak into the TF-IDF index used by a later test.
    """
    from app.api.ai import _build_job_index, _load_job_descriptions_cached

    _load_job_descriptions_cached.cache_clear()
    _build_job_index.cache_clear()
    yield
    _load_job_descriptions_cached.cache_clear()
    _build_job_index.cache_clear()


class TestQueryJobBoardFunction:
    """Direct, unit-level tests calling the handler function itself."""

    def test_returns_success_with_generated_answer_and_sources(self):
        """Core behaviour: a loaded model returns 200 with the answer and matching sources.

        Only the backend job shares terms with the query, so it is the sole ranked match.
        """
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", return_value="Here is a great match") as mock_generate,
        ):
            result = query_job_board(payload, response)

        mock_generate.assert_called_once()
        assert result.status == 200
        assert result.message == "Here is a great match"
        assert len(result.sources) == 1
        assert result.sources[0].title == "Senior Backend Engineer"
        assert response.status_code == 200

    def test_builds_rag_context_from_ranked_jobs(self):
        """The chat messages passed to generate_text should include the query and job context."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=1)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", return_value="ok") as mock_generate,
        ):
            query_job_board(payload, response)

        (messages,), _ = mock_generate.call_args
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert SAMPLE_QUERY in messages[1]["content"]
        assert "Job context" in messages[1]["content"]

    def test_returns_503_when_model_not_loaded(self):
        """When no model is loaded, the request is rejected before jobs are loaded or generation attempted."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=False),
            patch("app.api.ai._load_job_descriptions_cached") as mock_load,
            patch("app.api.ai.model_service.generate_text") as mock_generate,
        ):
            result = query_job_board(payload, response)

        mock_load.assert_not_called()
        mock_generate.assert_not_called()
        assert result == QueryJobBoardResponse(status=503, message="Model not loaded", sources=[])
        assert response.status_code == 503

    def test_returns_500_when_job_descriptions_fail_to_load(self):
        """A FileNotFoundError while loading job descriptions is translated into a 500 response."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", side_effect=FileNotFoundError("missing")),
            patch("app.api.ai.model_service.generate_text") as mock_generate,
        ):
            result = query_job_board(payload, response)

        mock_generate.assert_not_called()
        assert result == QueryJobBoardResponse(status=500, message="Unable to load job descriptions", sources=[])
        assert response.status_code == 500

    def test_returns_500_when_generate_text_raises_runtime_error(self):
        """A RuntimeError from generation is translated into a 500 response with empty sources."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", side_effect=RuntimeError("boom")),
        ):
            result = query_job_board(payload, response)

        assert result == QueryJobBoardResponse(status=500, message="Unable to answer job board query", sources=[])
        assert response.status_code == 500

    def test_returns_empty_sources_when_no_jobs_available(self):
        """An empty job catalogue should still succeed, with an empty sources list."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=()),
            patch("app.api.ai.model_service.generate_text", return_value="No jobs found"),
        ):
            result = query_job_board(payload, response)

        assert result.status == 200
        assert result.sources == []

    def test_respects_top_k_limit_on_returned_sources(self):
        """The number of returned sources should never exceed the requested top_k."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=1)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", return_value="ok"),
        ):
            result = query_job_board(payload, response)

        assert len(result.sources) == 1

    def test_does_not_suppress_unexpected_exception_types(self):
        """Exceptions outside the caught set (e.g. ZeroDivisionError) propagate to the caller."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", side_effect=ZeroDivisionError("unexpected")),
        ):
            with pytest.raises(ZeroDivisionError):
                query_job_board(payload, response)

    def test_return_type_is_query_job_board_response(self):
        """Return value must be a QueryJobBoardResponse instance as annotated."""
        response = Response()
        payload = QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=3)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", return_value="ok"),
        ):
            result = query_job_board(payload, response)

        assert isinstance(result, QueryJobBoardResponse)


class TestQueryJobBoardRequestValidation:
    """Payload-level validation tests for ``QueryJobBoardRequest``."""

    def test_rejects_query_shorter_than_min_length(self):
        """A query shorter than the minimum length fails validation."""
        with pytest.raises(ValueError):
            QueryJobBoardRequest(query="ab")

    def test_rejects_top_k_above_maximum(self):
        """A top_k value above the allowed maximum fails validation."""
        with pytest.raises(ValueError):
            QueryJobBoardRequest(query=SAMPLE_QUERY, top_k=6)


class TestQueryJobBoardEndpoint:
    """HTTP-level tests exercising the route (no admin auth required)."""

    def test_post_with_valid_query_returns_generated_answer(self, client: TestClient):
        """A well-formed request against a loaded model returns 200 with the answer and matching sources."""
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
            patch("app.api.ai.model_service.generate_text", return_value="Great match found"),
        ):
            response = client.post("/ai/query_job_board", json={"query": SAMPLE_QUERY, "top_k": 2})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == 200
        assert body["message"] == "Great match found"
        assert len(body["sources"]) == 1

    def test_post_returns_503_when_model_not_loaded(self, client: TestClient):
        """When the model service reports not loaded, the endpoint responds with 503."""
        with patch("app.api.ai.model_service.is_loaded", return_value=False):
            response = client.post("/ai/query_job_board", json={"query": SAMPLE_QUERY})

        assert response.status_code == 503
        assert response.json() == {"status": 503, "message": "Model not loaded", "sources": []}

    def test_post_with_missing_query_field_returns_422(self, client: TestClient):
        """Payload missing the required 'query' field fails validation."""
        response = client.post("/ai/query_job_board", json={})

        assert response.status_code == 422

    def test_post_with_top_k_out_of_range_returns_422(self, client: TestClient):
        """A top_k value outside the allowed range fails validation."""
        response = client.post("/ai/query_job_board", json={"query": SAMPLE_QUERY, "top_k": 100})

        assert response.status_code == 422
