"""Unit tests for the ``analyse_job`` endpoint in ``app.api.ai``.

``analyse_job`` backs ``POST /ai/analyse_job``. It requires a model to be
loaded, builds a chat-style prompt from the configured ``prompts.json``
templates and the submitted job description, and delegates generation to
``model_service.generate_text``:

    @router.post("/analyse_job")
    def analyse_job(payload: AnalyseJobRequest, response: Response) -> ApiResponse:
        if not model_service.is_loaded():
            return ApiResponse(status=503, message="Model not loaded")
        try:
            messages = [...]
            output = model_service.generate_text(messages)
            return ApiResponse(status=200, message=output)
        except (RuntimeError, ValueError, TypeError, KeyError):
            return ApiResponse(status=500, message="Unable to analyse job")
"""

from unittest.mock import patch

import pytest
from app.api.ai import analyse_job, prompts
from app.api.main import app
from app.api.schemas import AnalyseJobRequest, ApiResponse
from fastapi import Response
from fastapi.testclient import TestClient

SAMPLE_JD = "We are looking for a Senior Backend Engineer with 5+ years of Python experience."


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to the real FastAPI app, exercised through HTTP."""
    return TestClient(app)


class TestAnalyseJobFunction:
    """Direct, unit-level tests calling the handler function itself."""

    def test_returns_success_with_generated_analysis(self):
        """Core behaviour: a loaded model returns 200 with the generated message."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", return_value="Analysis result") as mock_generate,
        ):
            result = analyse_job(payload, response)

        mock_generate.assert_called_once()
        assert result == ApiResponse(status=200, message="Analysis result")
        assert response.status_code == 200

    def test_builds_messages_from_prompts_and_payload(self):
        """The chat messages passed to generate_text should use the configured prompts and the JD."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", return_value="ok") as mock_generate,
        ):
            analyse_job(payload, response)

        (messages,), _ = mock_generate.call_args
        assert messages[0] == {"role": "system", "content": prompts["analyse_job"]["system"]}
        assert messages[1]["role"] == "user"
        assert SAMPLE_JD in messages[1]["content"]
        assert prompts["analyse_job"]["user"] in messages[1]["content"]

    def test_returns_503_when_model_not_loaded(self):
        """When no model is loaded, the request is rejected before generation is attempted."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=False),
            patch("app.api.ai.model_service.generate_text") as mock_generate,
        ):
            result = analyse_job(payload, response)

        mock_generate.assert_not_called()
        assert result == ApiResponse(status=503, message="Model not loaded")
        assert response.status_code == 503

    def test_returns_500_when_generate_text_raises_runtime_error(self):
        """A RuntimeError from generation is translated into a 500 response."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", side_effect=RuntimeError("boom")),
        ):
            result = analyse_job(payload, response)

        assert result == ApiResponse(status=500, message="Unable to analyse job")
        assert response.status_code == 500

    def test_returns_500_when_generate_text_raises_key_error(self):
        """A KeyError (e.g. malformed prompt template) also yields a 500 response."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", side_effect=KeyError("analyse_job")),
        ):
            result = analyse_job(payload, response)

        assert result == ApiResponse(status=500, message="Unable to analyse job")
        assert response.status_code == 500

    def test_does_not_suppress_unexpected_exception_types(self):
        """Exceptions outside the caught set (e.g. ZeroDivisionError) propagate to the caller."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", side_effect=ZeroDivisionError("unexpected")),
        ):
            with pytest.raises(ZeroDivisionError):
                analyse_job(payload, response)

    def test_return_type_is_api_response(self):
        """Return value must be an ApiResponse instance as annotated."""
        response = Response()
        payload = AnalyseJobRequest(jd=SAMPLE_JD)
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", return_value="ok"),
        ):
            result = analyse_job(payload, response)

        assert isinstance(result, ApiResponse)


class TestAnalyseJobRequestValidation:
    """Payload-level validation tests for ``AnalyseJobRequest``."""

    def test_rejects_jd_shorter_than_min_length(self):
        """A job description shorter than the minimum length fails validation."""
        with pytest.raises(ValueError):
            AnalyseJobRequest(jd="too short")

    def test_rejects_missing_jd_field(self):
        """A missing 'jd' field fails validation."""
        with pytest.raises(ValueError):
            AnalyseJobRequest()


class TestAnalyseJobEndpoint:
    """HTTP-level tests exercising the route (no admin auth required)."""

    def test_post_with_valid_jd_returns_generated_analysis(self, client: TestClient):
        """A well-formed request against a loaded model returns 200 with the analysis text."""
        with (
            patch("app.api.ai.model_service.is_loaded", return_value=True),
            patch("app.api.ai.model_service.generate_text", return_value="Great candidate fit"),
        ):
            response = client.post("/ai/analyse_job", json={"jd": SAMPLE_JD})

        assert response.status_code == 200
        assert response.json() == {"status": 200, "message": "Great candidate fit"}

    def test_post_returns_503_when_model_not_loaded(self, client: TestClient):
        """When the model service reports not loaded, the endpoint responds with 503."""
        with patch("app.api.ai.model_service.is_loaded", return_value=False):
            response = client.post("/ai/analyse_job", json={"jd": SAMPLE_JD})

        assert response.status_code == 503
        assert response.json() == {"status": 503, "message": "Model not loaded"}

    def test_post_with_missing_body_field_returns_422(self, client: TestClient):
        """Payload missing the required 'jd' field fails validation."""
        response = client.post("/ai/analyse_job", json={})

        assert response.status_code == 422

    def test_post_with_jd_too_long_returns_422(self, client: TestClient):
        """A job description exceeding the maximum length fails validation."""
        response = client.post("/ai/analyse_job", json={"jd": "x" * 20001})

        assert response.status_code == 422
