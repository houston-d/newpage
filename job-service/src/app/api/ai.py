import json
import logging
import math
import os
import re
import secrets
import sys
import threading
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from transformers import GenerationConfig, pipeline

from .schemas import (
    AnalyseJobRequest,
    ApiResponse,
    LoadModelRequest,
    QueryJobBoardRequest,
    QueryJobBoardResponse,
    QuerySource,
)

logger = logging.getLogger(__name__)

logger.debug("=== runtime diag ===")
logger.debug("python:", sys.executable)
logger.debug("torch:", torch.__version__)
logger.debug("torch cuda runtime:", torch.version.cuda)
logger.debug("cuda available:", torch.cuda.is_available())
logger.debug("device count:", torch.cuda.device_count())
logger.debug("CUDA_VISIBLE_DEVICES:", os.getenv("CUDA_VISIBLE_DEVICES"))
if torch.cuda.is_available():
    logger.debug("device 0:", torch.cuda.get_device_name(0))
logger.debug("====================")

router = APIRouter(prefix="/ai", tags=["ai"])
ADMIN_API_KEY_ENV = "JOB_SERVICE_ADMIN_API_KEY"

prompts_path = os.path.join(os.path.dirname(__file__), os.pardir, "resources", "prompts.json")
with open(prompts_path, encoding="utf-8") as f:
    prompts = json.load(f)

generation_config = GenerationConfig(
    max_new_tokens=4096,
    do_sample=True,
    temperature=0.7,
    top_k=50,
    top_p=0.95,
)

ALLOWED_MODELS = {"TinyLlama/TinyLlama-1.1B-Chat-v1.0"}


class ModelService:
    def __init__(self) -> None:
        self._pipe: Any | None = None
        self._lock = threading.RLock()

    def is_loaded(self) -> bool:
        with self._lock:
            return self._pipe is not None

    def load_model(self, model: str) -> None:
        use_cuda = torch.cuda.is_available()
        model_pipe = pipeline(
            "text-generation",
            model=model,
            dtype=torch.bfloat16 if use_cuda else torch.float32,
            device_map="auto" if use_cuda else None,
        )
        with self._lock:
            self._pipe = model_pipe

    def generate_text(self, messages: list[dict[str, str]]) -> str:
        with self._lock:
            if self._pipe is None:
                raise RuntimeError("Model not loaded")

            prompt = self._pipe.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            outputs = self._pipe(
                prompt,
                generation_config=generation_config,
                return_full_text=False,
            )

        return outputs[0]["generated_text"]


def _job_descriptions_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "job-descriptions"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _normalize_job(raw_job: dict, source_file: str) -> dict[str, str]:
    return {
        "title": str(raw_job.get("title", "")).strip(),
        "location": str(raw_job.get("location", "")).strip(),
        "company": str(raw_job.get("company", "")).strip(),
        "salary": str(raw_job.get("salary", "")).strip(),
        "jd": str(raw_job.get("jd", "")).strip(),
        "source_file": source_file,
    }


def _load_job_descriptions() -> list[dict[str, str]]:
    job_dir = _job_descriptions_dir()
    if not job_dir.exists():
        raise FileNotFoundError(f"Job descriptions directory not found: {job_dir}")

    job_files = sorted(job_dir.glob("*.json"))
    if not job_files:
        raise ValueError(f"No job description files found in: {job_dir}")

    jobs: list[dict[str, str]] = []
    for job_file in job_files:
        with job_file.open(encoding="utf-8") as f:
            raw_job = json.load(f)
            jobs.append(_normalize_job(raw_job, job_file.name))

    return jobs


@lru_cache(maxsize=1)
def _load_job_descriptions_cached() -> tuple[dict[str, str], ...]:
    return tuple(_load_job_descriptions())


def _job_to_search_text(job: dict[str, str]) -> str:
    return " ".join([job["title"], job["location"], job["company"], job["salary"], job["jd"]])


@lru_cache(maxsize=1)
def _build_job_index() -> tuple[tuple[Counter[str], ...], Counter[str]]:
    jobs = _load_job_descriptions_cached()
    doc_term_frequencies: list[Counter[str]] = []
    doc_frequencies: Counter[str] = Counter()
    for job in jobs:
        term_frequency = Counter(_tokenize(_job_to_search_text(job)))
        doc_term_frequencies.append(term_frequency)
        for term in term_frequency:
            doc_frequencies[term] += 1

    return tuple(doc_term_frequencies), doc_frequencies


def _rank_relevant_jobs(query: str, jobs: list[dict[str, str]], top_k: int) -> list[dict[str, str]]:
    query_terms = Counter(_tokenize(query))
    if not query_terms:
        return jobs[:top_k]

    doc_term_frequencies, doc_frequencies = _build_job_index()

    total_docs = len(jobs)
    scored_jobs: list[tuple[float, int]] = []
    for idx, term_frequency in enumerate(doc_term_frequencies):
        score = 0.0
        for term, query_term_frequency in query_terms.items():
            doc_term_frequency = term_frequency.get(term, 0)
            if doc_term_frequency == 0:
                continue
            idf = math.log((total_docs + 1) / (doc_frequencies[term] + 1)) + 1.0
            score += query_term_frequency * doc_term_frequency * idf * idf
        if score > 0:
            scored_jobs.append((score, idx))

    if not scored_jobs:
        return jobs[:top_k]

    scored_jobs.sort(key=lambda item: item[0], reverse=True)
    return [jobs[idx] for _, idx in scored_jobs[:top_k]]


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def _build_rag_context(jobs: list[dict[str, str]]) -> str:
    context_chunks = []
    for index, job in enumerate(jobs, start=1):
        salary = job["salary"] if job["salary"] else "Not specified"
        context_chunks.append(
            (
                f"Job {index}\n"
                f"Title: {job['title']}\n"
                f"Company: {job['company']}\n"
                f"Location: {job['location']}\n"
                f"Salary: {salary}\n"
                f"Source: {job['source_file']}\n"
                f"Description: {_truncate(job['jd'], 2500)}"
            )
        )
    return "\n\n".join(context_chunks)


def require_admin_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    configured_api_key = os.getenv(ADMIN_API_KEY_ENV)
    if not configured_api_key:
        logger.error("Admin API key is not configured in %s", ADMIN_API_KEY_ENV)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )
    if x_api_key is None or not secrets.compare_digest(x_api_key, configured_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


model_service = ModelService()


def is_model_loaded() -> bool:
    return model_service.is_loaded()


@router.post("/load_model")
def load_model(payload: LoadModelRequest, response: Response, _: None = Depends(require_admin_api_key)) -> ApiResponse:
    """Load a model into the shared model service for subsequent AI requests.

    Requires a valid admin API key. Validates that the requested model is in the
    allowed list before attempting to load it via ``model_service``.

    Args:
        payload: Request body containing the name of the ``model`` to load.
        response: FastAPI response object, whose ``status_code`` is set to reflect
            the outcome of the request.
        _: Dependency that enforces admin API key authentication; unused otherwise.

    Returns:
        ApiResponse: ``status=200`` if the model loads successfully; ``status=400``
        if the requested model is not permitted; ``status=500`` if loading fails.
    """
    model = payload.model

    if model not in ALLOWED_MODELS:
        logger.warning("Model not recognized: %s", model)
        response.status_code = status.HTTP_400_BAD_REQUEST

        return ApiResponse(status=400, message="Model not permitted")

    try:
        model_service.load_model(model)
        response.status_code = status.HTTP_200_OK
        return ApiResponse(status=200, message="Model successfully loaded")

    except (RuntimeError, ValueError, OSError):
        logger.exception("Failed to load model")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiResponse(status=500, message="Unable to load model")


@router.post("/analyse_job")
def analyse_job(payload: AnalyseJobRequest, response: Response) -> ApiResponse:
    """Analyse a job description using the currently loaded model.

    Builds a system/user prompt pair from the "analyse_job" prompt template and the
    job description supplied in ``payload.jd``, then generates a response via
    ``model_service``.

    Args:
        payload: Request body containing the job description text (``jd``) to analyse.
        response: FastAPI response object, whose ``status_code`` is set to reflect
            the outcome of the request.

    Returns:
        ApiResponse: ``status=200`` with the generated analysis in ``message`` on
        success; ``status=503`` if no model is loaded; ``status=500`` if generation
        fails.
    """
    if not model_service.is_loaded():
        logger.warning("Model not set")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(status=503, message="Model not loaded")

    try:
        messages = [
            {"role": "system", "content": prompts["analyse_job"]["system"]},
            {"role": "user", "content": f'{prompts["analyse_job"]["user"]} {payload.jd}'},
        ]
        output = model_service.generate_text(messages)
        response.status_code = status.HTTP_200_OK
        return ApiResponse(status=200, message=output)

    except (RuntimeError, ValueError, TypeError, KeyError):
        logger.exception("Failed to analyse job")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiResponse(status=500, message="Unable to analyse job")


@router.post("/query_job_board")
def query_job_board(payload: QueryJobBoardRequest, response: Response) -> QueryJobBoardResponse:
    """Answer a natural-language query against the job board using retrieval-augmented generation.

    Loads cached job descriptions, ranks them for relevance to ``payload.query``,
    builds a RAG context from the top matches, and prompts the currently loaded
    model to answer the query using only that context.

    Args:
        payload: Request body containing the user's ``query`` and ``top_k`` number
            of relevant jobs to retrieve.
        response: FastAPI response object, whose ``status_code`` is set to reflect
            the outcome of the request.

    Returns:
        QueryJobBoardResponse: ``status=200`` with the generated answer in
        ``message`` and the matched jobs in ``sources`` on success; ``status=503``
        if no model is loaded; ``status=500`` if loading job descriptions or
        generating the answer fails.
    """
    if not model_service.is_loaded():
        logger.error("Model not set")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return QueryJobBoardResponse(status=503, message="Model not loaded", sources=[])

    try:
        jobs = list(_load_job_descriptions_cached())
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        logger.exception("Failed to load job descriptions")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return QueryJobBoardResponse(status=500, message="Unable to load job descriptions", sources=[])

    relevant_jobs = _rank_relevant_jobs(payload.query, jobs, payload.top_k)
    rag_context = _build_rag_context(relevant_jobs)
    query_prompt = prompts.get("query_job_board", {})

    messages = [
        {
            "role": "system",
            "content": query_prompt.get(
                "system",
                (
                    "You are a job board assistant. Use only the provided job context. "
                    "If the context does not contain the answer, clearly say that."
                ),
            ),
        },
        {
            "role": "user",
            "content": (
                f"{query_prompt.get('user', 'Answer the user query using the provided job context.')}\n\n"
                f"User query: {payload.query}\n\n"
                f"Job context:\n{rag_context}"
            ),
        },
    ]

    try:
        output = model_service.generate_text(messages)
    except (ValueError, RuntimeError, KeyError, TypeError):
        logger.exception("Failed to answer job board query")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return QueryJobBoardResponse(status=500, message="Unable to answer job board query", sources=[])

    response_sources = [
        QuerySource(
            id=job["id"],
            title=job["title"],
            location=job["location"],
            company=job["company"],
            salary=job["salary"],
            source_file=job["source_file"],
        )
        for job in relevant_jobs
    ]
    response.status_code = status.HTTP_200_OK
    return QueryJobBoardResponse(status=200, message=output, sources=response_sources)
