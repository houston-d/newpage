"""Unit tests for the ``read_root`` endpoint in ``app.api.main``.

``read_root`` backs ``GET /`` and returns a simple static status payload:

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"message": "NewPage API is running"}
"""

import pytest
from app.api.main import app, read_root, health
from fastapi.testclient import TestClient
from unittest.mock import patch
from fastapi import Response
from app.api.schemas import ApiResponse


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to the real FastAPI app, exercised through HTTP."""
    return TestClient(app)


class TestReadRootFunction:
    """Direct, unit-level tests calling the handler function itself."""

    def test_returns_expected_message(self):
        """Core behaviour: the handler returns the running status message."""
        result = read_root()
        assert result == {"message": "NewPage API is running"}

    def test_return_type_is_dict_of_str(self):
        """Return value must be a plain dict[str, str] as annotated."""
        result = read_root()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in result.items())

    def test_returns_single_key(self):
        """No extra/unexpected keys should be present in the payload."""
        result = read_root()
        assert list(result.keys()) == ["message"]

    def test_is_idempotent_across_repeated_calls(self):
        """Calling repeatedly (no state/side effects) yields identical output."""
        assert read_root() == read_root() == {"message": "NewPage API is running"}

    def test_does_not_require_any_arguments(self):
        """The handler takes no parameters and needs no request context."""
        # Should not raise TypeError for missing arguments.
        read_root()


class TestReadRootEndpoint:
    """HTTP-level tests exercising the route as FastAPI would invoke it."""

    def test_get_root_returns_200(self, client: TestClient):
        """GET / should succeed with a 200 status code."""
        response = client.get("/")
        assert response.status_code == 200

    def test_get_root_returns_expected_json_body(self, client: TestClient):
        """The JSON body should exactly match the handler's return value."""
        response = client.get("/")
        assert response.json() == {"message": "NewPage API is running"}

    def test_post_root_is_not_allowed(self, client: TestClient):
        """Only GET is registered for '/'; other methods should 405."""
        response = client.post("/")
        assert response.status_code == 405


"""Unit tests for the ``health`` endpoint in ``app.api.main``.

``health`` backs ``GET /health`` and reports whether the API is ready to
serve model requests:

    @app.get("/health")
    def health(response: Response) -> ApiResponse:
        if not is_model_loaded():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ApiResponse(status=503, message="Model not loaded")

        response.status_code = status.HTTP_200_OK
        return ApiResponse(status=200, message="ok")
"""


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to the real FastAPI app, exercised through HTTP."""
    return TestClient(app)


class TestHealthFunction:
    """Direct, unit-level tests calling the handler function itself."""

    def test_returns_ok_when_model_is_loaded(self):
        """Core behaviour: reports 200/ok when a model pipeline is loaded."""
        response = Response()
        with patch("app.api.main.is_model_loaded", return_value=True):
            result = health(response)

        assert result == ApiResponse(status=200, message="ok")
        assert response.status_code == 200

    def test_returns_unavailable_when_model_not_loaded(self):
        """Reports 503/Model not loaded when no pipeline has been loaded."""
        response = Response()
        with patch("app.api.main.is_model_loaded", return_value=False):
            result = health(response)

        assert result == ApiResponse(status=503, message="Model not loaded")
        assert response.status_code == 503

    def test_return_type_is_api_response(self):
        """Return value must be an ApiResponse instance as annotated."""
        response = Response()
        with patch("app.api.main.is_model_loaded", return_value=True):
            result = health(response)

        assert isinstance(result, ApiResponse)

    def test_is_idempotent_across_repeated_calls(self):
        """Calling repeatedly with the same model state yields identical output."""
        with patch("app.api.main.is_model_loaded", return_value=True):
            first = health(Response())
            second = health(Response())

        assert first == second == ApiResponse(status=200, message="ok")

    def test_mutates_passed_in_response_object(self):
        """The handler sets status_code on the Response it is given (side effect)."""
        response = Response(status_code=999)
        with patch("app.api.main.is_model_loaded", return_value=False):
            health(response)

        assert response.status_code == 503


class TestHealthEndpoint:
    """HTTP-level tests exercising the route as FastAPI would invoke it."""

    def test_get_health_returns_200_when_model_loaded(self, client: TestClient):
        """GET /health should succeed with 200 when a model is loaded."""
        with patch("app.api.main.is_model_loaded", return_value=True):
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": 200, "message": "ok"}

    def test_get_health_returns_503_when_model_not_loaded(self, client: TestClient):
        """GET /health should return 503 when no model is loaded."""
        with patch("app.api.main.is_model_loaded", return_value=False):
            response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {"status": 503, "message": "Model not loaded"}

    def test_post_health_is_not_allowed(self, client: TestClient):
        """Only GET is registered for '/health'; other methods should 405."""
        response = client.post("/health")
        assert response.status_code == 405
