"""Unit tests for the ``load_model`` endpoint in ``app.api.ai``.

``load_model`` backs ``POST /ai/load_model`` and is guarded by an admin
API key dependency. It validates the requested model against an allow-list
before delegating to ``model_service.load_model``:

    @router.post("/load_model")
    def load_model(payload: LoadModelRequest, response: Response,
                    _: None = Depends(require_admin_api_key)) -> ApiResponse:
        if model not in ALLOWED_MODELS:
            return ApiResponse(status=400, message="Model not permitted")
        try:
            model_service.load_model(model)
            return ApiResponse(status=200, message="Model successfully loaded")
        except (RuntimeError, ValueError, OSError):
            return ApiResponse(status=500, message="Unable to load model")
"""

from unittest.mock import patch

import pytest
from app.api.ai import ALLOWED_MODELS, load_model
from app.api.main import app
from app.api.schemas import ApiResponse, LoadModelRequest
from fastapi import Response
from fastapi.testclient import TestClient

ALLOWED_MODEL = next(iter(ALLOWED_MODELS))
ADMIN_HEADER = {"X-API-Key": "test-admin-key"}


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to the real FastAPI app, exercised through HTTP."""
    return TestClient(app)


class TestLoadModelFunction:
    """Direct, unit-level tests calling the handler function itself."""

    def test_returns_success_when_model_loads(self):
        """Core behaviour: an allowed model loads and returns 200/success."""
        response = Response()
        payload = LoadModelRequest(model=ALLOWED_MODEL)
        with patch("app.api.ai.model_service.load_model") as mock_load:
            result = load_model(payload, response)

        mock_load.assert_called_once_with(ALLOWED_MODEL)
        assert result == ApiResponse(status=200, message="Model successfully loaded")
        assert response.status_code == 200

    def test_rejects_model_not_in_allow_list(self):
        """A model outside ALLOWED_MODELS is rejected before loading is attempted."""
        response = Response()
        payload = LoadModelRequest(model="totally/unrecognized-model")
        with patch("app.api.ai.model_service.load_model") as mock_load:
            result = load_model(payload, response)

        mock_load.assert_not_called()
        assert result == ApiResponse(status=400, message="Model not permitted")
        assert response.status_code == 400

    def test_returns_500_when_load_model_raises_runtime_error(self):
        """A RuntimeError from the service is translated into a 500 response."""
        response = Response()
        payload = LoadModelRequest(model=ALLOWED_MODEL)
        with patch("app.api.ai.model_service.load_model", side_effect=RuntimeError("boom")):
            result = load_model(payload, response)

        assert result == ApiResponse(status=500, message="Unable to load model")
        assert response.status_code == 500

    def test_returns_500_when_load_model_raises_os_error(self):
        """An OSError (e.g. failing to fetch weights) also yields a 500 response."""
        response = Response()
        payload = LoadModelRequest(model=ALLOWED_MODEL)
        with patch("app.api.ai.model_service.load_model", side_effect=OSError("disk full")):
            result = load_model(payload, response)

        assert result == ApiResponse(status=500, message="Unable to load model")
        assert response.status_code == 500

    def test_does_not_suppress_unexpected_exception_types(self):
        """Exceptions outside the caught set (e.g. KeyError) propagate to the caller."""
        response = Response()
        payload = LoadModelRequest(model=ALLOWED_MODEL)
        with patch("app.api.ai.model_service.load_model", side_effect=KeyError("unexpected")):
            with pytest.raises(KeyError):
                load_model(payload, response)

    def test_return_type_is_api_response(self):
        """Return value must be an ApiResponse instance as annotated."""
        response = Response()
        payload = LoadModelRequest(model=ALLOWED_MODEL)
        with patch("app.api.ai.model_service.load_model"):
            result = load_model(payload, response)

        assert isinstance(result, ApiResponse)


class TestLoadModelEndpoint:
    """HTTP-level tests exercising the route (including auth) as FastAPI would."""

    @staticmethod
    def _getenv_side_effect(service_key: str | None, legacy_key: str | None):
        values = {
            "SERVICE_KEY": service_key,
            "JOB_SERVICE_ADMIN_API_KEY": legacy_key,
        }
        return lambda key, default=None: values.get(key, default)

    def test_post_without_api_key_is_unauthorized(self, client: TestClient):
        """Missing X-API-Key header should be rejected with 401."""
        with patch(
            "app.api.ai.os.getenv",
            side_effect=self._getenv_side_effect(service_key="test-admin-key", legacy_key=None),
        ):
            response = client.post("/ai/load_model", json={"model": ALLOWED_MODEL})

        assert response.status_code == 401

    def test_post_with_wrong_api_key_is_unauthorized(self, client: TestClient):
        """An incorrect X-API-Key header should be rejected with 401."""
        with patch(
            "app.api.ai.os.getenv",
            side_effect=self._getenv_side_effect(service_key="test-admin-key", legacy_key=None),
        ):
            response = client.post(
                "/ai/load_model",
                json={"model": ALLOWED_MODEL},
                headers={"X-API-Key": "wrong-key"},
            )

        assert response.status_code == 401

    def test_post_with_valid_api_key_loads_allowed_model(self, client: TestClient):
        """A correct admin key and allowed model should succeed with 200."""
        with (
            patch(
                "app.api.ai.os.getenv",
                side_effect=self._getenv_side_effect(service_key="test-admin-key", legacy_key=None),
            ),
            patch("app.api.ai.model_service.load_model") as mock_load,
        ):
            response = client.post(
                "/ai/load_model",
                json={"model": ALLOWED_MODEL},
                headers=ADMIN_HEADER,
            )

        mock_load.assert_called_once_with(ALLOWED_MODEL)
        assert response.status_code == 200
        assert response.json() == {"status": 200, "message": "Model successfully loaded"}

    def test_post_with_missing_body_field_returns_422(self, client: TestClient):
        """Payload missing the required 'model' field fails validation."""
        with patch(
            "app.api.ai.os.getenv",
            side_effect=self._getenv_side_effect(service_key="test-admin-key", legacy_key=None),
        ):
            response = client.post("/ai/load_model", json={}, headers=ADMIN_HEADER)

        assert response.status_code == 422

    def test_post_returns_503_when_admin_key_not_configured(self, client: TestClient):
        """If the server has no admin key configured, auth is unavailable (503)."""
        with patch(
            "app.api.ai.os.getenv",
            side_effect=self._getenv_side_effect(service_key=None, legacy_key=None),
        ):
            response = client.post(
                "/ai/load_model",
                json={"model": ALLOWED_MODEL},
                headers=ADMIN_HEADER,
            )

        assert response.status_code == 503

    def test_post_uses_legacy_admin_key_when_service_key_missing(self, client: TestClient):
        """Legacy admin key still authenticates when SERVICE_KEY is absent."""
        with (
            patch(
                "app.api.ai.os.getenv",
                side_effect=self._getenv_side_effect(service_key=None, legacy_key="test-admin-key"),
            ),
            patch("app.api.ai.model_service.load_model") as mock_load,
        ):
            response = client.post(
                "/ai/load_model",
                json={"model": ALLOWED_MODEL},
                headers=ADMIN_HEADER,
            )

        mock_load.assert_called_once_with(ALLOWED_MODEL)
        assert response.status_code == 200
