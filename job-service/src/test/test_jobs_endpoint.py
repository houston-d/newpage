"""Unit tests for the ``get_jobs`` and ``get_job`` endpoints in ``app.api.jobs``.

``get_jobs`` backs ``GET /jobs``. It loads every job description JSON file
from the resources directory, normalizes them, and returns them:

    @router.get("")
    def get_jobs(response: Response) -> JobsResponse:
        try:
            jobs = _load_jobs()
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
            return JobsResponse(status=500, message="Unable to load job descriptions", jobs=[])
        return JobsResponse(status=200, message="ok", jobs=jobs)

``get_job`` backs ``GET /jobs/{id}``. It loads every job description the same
way, then returns the single job matching ``id``:

    @router.get("/{id}")
    def get_job(id: str, response: Response) -> JobResponse:
        try:
            jobs = _load_jobs()
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
            return JobResponse(status=500, message="Unable to load job descriptions", job=None)
        job = next((j for j in jobs if j.id == id), None)
        if job is None:
            return JobResponse(status=404, message=f"Job '{id}' not found", job=None)
        return JobResponse(status=200, message="ok", job=job)
"""

import json
from unittest.mock import patch

import pytest
from app.api.jobs import _load_jobs, _normalize_job, get_job, get_jobs
from app.api.main import app
from app.api.schemas import Job, JobResponse, JobsResponse
from fastapi import Response
from fastapi.testclient import TestClient

SAMPLE_RAW_JOB = {
    "id": "1",
    "title": "Graduate Software Engineer",
    "location": "Bristol, UK",
    "company": "Grapple",
    "salary": "£30,000-35,000",
    "jd": "About the role...",
}


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to the real FastAPI app, exercised through HTTP."""
    return TestClient(app)


class TestNormalizeJob:
    """Tests for _normalize_job."""

    def test_normalizes_complete_raw_job(self):
        """Core behaviour: a fully populated raw job dict maps to a Job model."""
        result = _normalize_job(SAMPLE_RAW_JOB, "1.json")

        assert result == Job(
            id="1",
            title="Graduate Software Engineer",
            location="Bristol, UK",
            company="Grapple",
            salary="£30,000-35,000",
            jd="About the role...",
            source_file="1.json",
        )

    def test_missing_fields_default_to_empty_strings(self):
        """Fields absent from the raw job should default to empty strings, not raise."""
        result = _normalize_job({}, "2.json")

        assert result.title == ""
        assert result.location == ""
        assert result.company == ""
        assert result.salary == ""
        assert result.jd == ""
        assert result.source_file == "2.json"

    def test_missing_id_falls_back_to_filename_stem(self):
        """When 'id' is absent, the source file's stem is used instead."""
        result = _normalize_job({}, "3.json")

        assert result.id == "3"

    def test_strips_surrounding_whitespace(self):
        """Leading/trailing whitespace in string fields should be stripped."""
        raw_job = {"title": "  Data Scientist  ", "location": "\tRemote\n"}

        result = _normalize_job(raw_job, "4.json")

        assert result.title == "Data Scientist"
        assert result.location == "Remote"


class TestLoadJobs:
    """Tests for _load_jobs."""

    def test_loads_all_json_files_in_directory(self, tmp_path):
        """All *.json files in the job descriptions directory are loaded."""
        (tmp_path / "1.json").write_text(json.dumps(SAMPLE_RAW_JOB), encoding="utf-8")
        (tmp_path / "2.json").write_text(
            json.dumps({**SAMPLE_RAW_JOB, "id": "2", "title": "Other"}), encoding="utf-8"
        )

        with patch("app.api.jobs._job_descriptions_dir", return_value=tmp_path):
            jobs = _load_jobs()

        assert len(jobs) == 2
        assert {job.id for job in jobs} == {"1", "2"}

    def test_raises_file_not_found_when_directory_missing(self, tmp_path):
        """A missing job descriptions directory raises FileNotFoundError."""
        missing_dir = tmp_path / "does-not-exist"

        with patch("app.api.jobs._job_descriptions_dir", return_value=missing_dir):
            with pytest.raises(FileNotFoundError):
                _load_jobs()

    def test_returns_empty_list_when_no_json_files_present(self, tmp_path):
        """An existing but empty directory yields an empty list, not an error."""
        with patch("app.api.jobs._job_descriptions_dir", return_value=tmp_path):
            jobs = _load_jobs()

        assert jobs == []


class TestGetJobsFunction:
    """Direct, unit-level tests calling the handler function itself."""

    def test_returns_success_with_loaded_jobs(self):
        """Core behaviour: successfully loaded jobs are returned with status 200."""
        response = Response()
        sample_jobs = [_normalize_job(SAMPLE_RAW_JOB, "1.json")]
        with patch("app.api.jobs._load_jobs", return_value=sample_jobs):
            result = get_jobs(response)

        assert result == JobsResponse(status=200, message="ok", jobs=sample_jobs)
        assert response.status_code == 200

    def test_returns_500_when_loading_fails(self):
        """A FileNotFoundError while loading job descriptions is translated into a 500 response."""
        response = Response()
        with patch("app.api.jobs._load_jobs", side_effect=FileNotFoundError("missing")):
            result = get_jobs(response)

        assert result == JobsResponse(status=500, message="Unable to load job descriptions", jobs=[])
        assert response.status_code == 500

    def test_returns_empty_jobs_list_when_none_available(self):
        """An empty job catalogue should still succeed, with an empty jobs list."""
        response = Response()
        with patch("app.api.jobs._load_jobs", return_value=[]):
            result = get_jobs(response)

        assert result.status == 200
        assert result.jobs == []

    def test_return_type_is_jobs_response(self):
        """Return value must be a JobsResponse instance as annotated."""
        response = Response()
        with patch("app.api.jobs._load_jobs", return_value=[]):
            result = get_jobs(response)

        assert isinstance(result, JobsResponse)


class TestGetJobsEndpoint:
    """HTTP-level tests exercising the route as FastAPI would invoke it."""

    def test_get_jobs_returns_200_with_jobs(self, client: TestClient):
        """GET /jobs should succeed with 200 and the normalized jobs list."""
        sample_jobs = [_normalize_job(SAMPLE_RAW_JOB, "1.json")]
        with patch("app.api.jobs._load_jobs", return_value=sample_jobs):
            response = client.get("/jobs")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == 200
        assert len(body["jobs"]) == 1
        assert body["jobs"][0]["id"] == "1"

    def test_get_jobs_returns_500_when_loading_fails(self, client: TestClient):
        """GET /jobs should return 500 when job descriptions fail to load."""
        with patch("app.api.jobs._load_jobs", side_effect=OSError("disk error")):
            response = client.get("/jobs")

        assert response.status_code == 500
        assert response.json() == {"status": 500, "message": "Unable to load job descriptions", "jobs": []}

    def test_post_jobs_is_not_allowed(self, client: TestClient):
        """Only GET is registered for '/jobs'; other methods should 405."""
        response = client.post("/jobs")
        assert response.status_code == 405


class TestGetJobFunction:
    """Direct, unit-level tests calling the single-job handler function itself."""

    def test_returns_success_when_job_found(self):
        """Core behaviour: an existing job id returns status 200 with the job."""
        response = Response()
        sample_job = _normalize_job(SAMPLE_RAW_JOB, "1.json")
        with patch("app.api.jobs._load_jobs", return_value=[sample_job]):
            result = get_job("1", response)

        assert result == JobResponse(status=200, message="ok", job=sample_job)
        assert response.status_code == 200

    def test_returns_404_when_job_not_found(self):
        """An id that doesn't match any loaded job should yield a 404 response."""
        response = Response()
        sample_job = _normalize_job(SAMPLE_RAW_JOB, "1.json")
        with patch("app.api.jobs._load_jobs", return_value=[sample_job]):
            result = get_job("missing", response)

        assert result == JobResponse(status=404, message="Job 'missing' not found", job=None)
        assert response.status_code == 404

    def test_returns_500_when_loading_fails(self):
        """A FileNotFoundError while loading job descriptions is translated into a 500 response."""
        response = Response()
        with patch("app.api.jobs._load_jobs", side_effect=FileNotFoundError("missing")):
            result = get_job("1", response)

        assert result == JobResponse(status=500, message="Unable to load job descriptions", job=None)
        assert response.status_code == 500

    def test_return_type_is_job_response(self):
        """Return value must be a JobResponse instance as annotated."""
        response = Response()
        with patch("app.api.jobs._load_jobs", return_value=[]):
            result = get_job("1", response)

        assert isinstance(result, JobResponse)


class TestGetJobEndpoint:
    """HTTP-level tests exercising the '/jobs/{id}' route as FastAPI would invoke it."""

    def test_get_job_returns_200_with_matching_job(self, client: TestClient):
        """GET /jobs/{id} should succeed with 200 and the matching job."""
        sample_jobs = [_normalize_job(SAMPLE_RAW_JOB, "1.json")]
        with patch("app.api.jobs._load_jobs", return_value=sample_jobs):
            response = client.get("/jobs/1")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == 200
        assert body["job"]["id"] == "1"
        assert body["job"]["title"] == "Graduate Software Engineer"

    def test_get_job_returns_404_when_not_found(self, client: TestClient):
        """GET /jobs/{id} should return 404 when no job matches the given id."""
        sample_jobs = [_normalize_job(SAMPLE_RAW_JOB, "1.json")]
        with patch("app.api.jobs._load_jobs", return_value=sample_jobs):
            response = client.get("/jobs/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {
            "status": 404,
            "message": "Job 'does-not-exist' not found",
            "job": None,
        }

    def test_get_job_returns_500_when_loading_fails(self, client: TestClient):
        """GET /jobs/{id} should return 500 when job descriptions fail to load."""
        with patch("app.api.jobs._load_jobs", side_effect=OSError("disk error")):
            response = client.get("/jobs/1")

        assert response.status_code == 500
        assert response.json() == {
            "status": 500,
            "message": "Unable to load job descriptions",
            "job": None,
        }

    def test_post_job_is_not_allowed(self, client: TestClient):
        """Only GET is registered for '/jobs/{id}'; other methods should 405."""
        response = client.post("/jobs/1")
        assert response.status_code == 405
