from unittest.mock import patch

from app.api.ai import chat
from app.api.main import app
from app.api.schemas import ApiResponse, ChatRequest
from fastapi import Response
from fastapi.testclient import TestClient

SAMPLE_CHAT_PAYLOAD = {
    "cv": "Senior engineer with Python and React experience.",
    "message_history": [
        {"role": "user", "content": "Can you summarize my fit?"},
        {"role": "assistant", "content": "Sure, please share your CV."},
        {"role": "user", "content": "I have uploaded it now."},
    ],
}

SAMPLE_JOBS: tuple[dict[str, str], ...] = (
    {
        "id": "acme_backend",
        "title": "Senior Backend Engineer",
        "location": "London",
        "company": "Acme Corp",
        "salary": "£70,000 - £90,000",
        "source_file": "acme_backend.json",
        "jd": "We are looking for a Senior Backend Engineer with strong Python experience.",
    },
    {
        "id": "widgets_frontend",
        "title": "Frontend Developer",
        "location": "Manchester",
        "company": "Widgets Ltd",
        "salary": "",
        "source_file": "widgets_frontend.json",
        "jd": "React developer needed for our growing frontend team.",
    },
)


def test_chat_returns_generated_message_using_cv_and_history():
    response = Response()
    payload = ChatRequest(**SAMPLE_CHAT_PAYLOAD)

    with (
        patch("app.api.ai.model_service.is_loaded", return_value=True),
        patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
        patch("app.api.ai.model_service.generate_text", return_value="You match backend roles in London.") as mock_generate,
    ):
        result = chat(payload, response)

    assert result == ApiResponse(status=200, message="You match backend roles in London.")
    assert response.status_code == 200
    (messages,), _ = mock_generate.call_args
    assert messages[0]["role"] == "system"
    assert "Senior engineer with Python and React experience." in messages[0]["content"]
    assert "Relevant jobs from the job board:" in messages[0]["content"]
    assert "Senior Backend Engineer" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "I have uploaded it now."}


def test_chat_returns_503_when_model_not_loaded():
    response = Response()
    payload = ChatRequest(**SAMPLE_CHAT_PAYLOAD)

    with (
        patch("app.api.ai.model_service.is_loaded", return_value=False),
        patch("app.api.ai._load_job_descriptions_cached") as mock_load_jobs,
        patch("app.api.ai.model_service.generate_text") as mock_generate,
    ):
        result = chat(payload, response)

    mock_load_jobs.assert_not_called()
    mock_generate.assert_not_called()
    assert result == ApiResponse(status=503, message="Model not loaded")
    assert response.status_code == 503


def test_chat_returns_500_when_jobs_fail_to_load():
    response = Response()
    payload = ChatRequest(**SAMPLE_CHAT_PAYLOAD)

    with (
        patch("app.api.ai.model_service.is_loaded", return_value=True),
        patch("app.api.ai._load_job_descriptions_cached", side_effect=FileNotFoundError("missing")),
        patch("app.api.ai.model_service.generate_text") as mock_generate,
    ):
        result = chat(payload, response)

    mock_generate.assert_not_called()
    assert result == ApiResponse(status=500, message="Unable to load job descriptions")
    assert response.status_code == 500


def test_chat_returns_500_when_generation_fails():
    response = Response()
    payload = ChatRequest(**SAMPLE_CHAT_PAYLOAD)

    with (
        patch("app.api.ai.model_service.is_loaded", return_value=True),
        patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
        patch("app.api.ai.model_service.generate_text", side_effect=RuntimeError("boom")),
    ):
        result = chat(payload, response)

    assert result == ApiResponse(status=500, message="Unable to answer chat request")
    assert response.status_code == 500


def test_chat_endpoint_accepts_cv_and_message_history():
    client = TestClient(app)

    with (
        patch("app.api.ai.model_service.is_loaded", return_value=True),
        patch("app.api.ai._load_job_descriptions_cached", return_value=SAMPLE_JOBS),
        patch("app.api.ai.model_service.generate_text", return_value="Chat reply"),
    ):
        response = client.post("/ai/chat", json=SAMPLE_CHAT_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"status": 200, "message": "Chat reply"}


def test_chat_endpoint_rejects_missing_cv_field():
    client = TestClient(app)

    response = client.post(
        "/ai/chat",
        json={"message_history": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 422


def test_chat_endpoint_rejects_invalid_message_role():
    client = TestClient(app)

    response = client.post(
        "/ai/chat",
        json={
            "cv": "cv text",
            "message_history": [{"role": "system", "content": "Not allowed"}],
        },
    )

    assert response.status_code == 422
