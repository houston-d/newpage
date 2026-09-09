import json
import logging
from pathlib import Path

from fastapi import APIRouter, Response, status

from .schemas import Job, JobResponse, JobsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_descriptions_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "job-descriptions"


def _normalize_job(raw_job: dict, source_file: str) -> Job:
    return Job(
        id=str(raw_job.get("id", Path(source_file).stem)).strip(),
        title=str(raw_job.get("title", "")).strip(),
        location=str(raw_job.get("location", "")).strip(),
        company=str(raw_job.get("company", "")).strip(),
        salary=str(raw_job.get("salary", "")).strip(),
        jd=str(raw_job.get("jd", "")).strip(),
        source_file=source_file,
    )


def _load_jobs() -> list[Job]:
    job_dir = _job_descriptions_dir()
    if not job_dir.exists():
        raise FileNotFoundError(f"Job descriptions directory not found: {job_dir}")

    jobs: list[Job] = []
    for job_file in sorted(job_dir.glob("*.json")):
        with job_file.open(encoding="utf-8") as f:
            raw_job = json.load(f)
        jobs.append(_normalize_job(raw_job, job_file.name))

    return jobs


@router.get("")
def get_jobs(response: Response) -> JobsResponse:
    """Retrieve all job postings from the job descriptions resource directory.

    Reads every job description JSON file from the resources directory and
    returns them as a normalized list.

    Args:
        response: FastAPI response object, whose ``status_code`` is set to reflect
            the outcome of the request.

    Returns:
        JobsResponse: ``status=200`` with all normalized jobs in ``jobs`` on
        success; ``status=500`` if the job descriptions cannot be loaded.
    """
    try:
        jobs = _load_jobs()
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        logger.exception("Failed to load job descriptions")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return JobsResponse(status=500, message="Unable to load job descriptions", jobs=[])

    response.status_code = status.HTTP_200_OK
    return JobsResponse(status=200, message="ok", jobs=jobs)


@router.get("/{id}")
def get_job(id: str, response: Response) -> JobResponse:
    """Retrieve a single job posting by its id.

    Args:
        id: The job identifier to look up.
        response: FastAPI response object, whose ``status_code`` is set to reflect
            the outcome of the request.

    Returns:
        JobResponse: ``status=200`` with the matching job on success;
        ``status=404`` if no job with the given id exists; ``status=500`` if
        the job descriptions cannot be loaded.
    """
    try:
        jobs = _load_jobs()
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        logger.exception("Failed to load job descriptions")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return JobResponse(status=500, message="Unable to load job descriptions", job=None)

    job = next((j for j in jobs if j.id == id), None)
    if job is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return JobResponse(status=404, message=f"Job '{id}' not found", job=None)

    response.status_code = status.HTTP_200_OK
    return JobResponse(status=200, message="ok", job=job)
