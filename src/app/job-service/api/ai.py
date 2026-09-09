import json
import logging
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

import torch
from fastapi import APIRouter
from pydantic import BaseModel, Field
from transformers import GenerationConfig, pipeline

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

pipe = None

prompts_path = os.path.join(os.path.dirname(__file__), os.pardir, "resources", "prompts.json")
with open(prompts_path) as f:
    prompts = json.load(f)

generation_config = GenerationConfig(
    max_new_tokens=4096,
    do_sample=True,
    temperature=0.7,
    top_k=50,
    top_p=0.95,
)

ALLOWED_MODELS = {"TinyLlama/TinyLlama-1.1B-Chat-v1.0"}


class AnalyseJobRequest(BaseModel):
    jd: str = Field(..., min_length=10, max_length=20000)


class QueryJobBoardRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)


class QuerySource(BaseModel):
    title: str
    location: str
    company: str
    salary: str
    source_file: str


class ApiResponse(BaseModel):
    status: int
    message: str


class QueryJobBoardResponse(ApiResponse):
    sources: list[QuerySource] = Field(default_factory=list)


def is_model_loaded() -> bool:
    return pipe is not None


def _job_descriptions_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "job-descriptions"


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


def _job_to_search_text(job: dict[str, str]) -> str:
    return " ".join([job["title"], job["location"], job["company"], job["salary"], job["jd"]])


def _rank_relevant_jobs(query: str, jobs: list[dict[str, str]], top_k: int) -> list[dict[str, str]]:
    query_terms = Counter(_tokenize(query))
    if not query_terms:
        return jobs[:top_k]

    doc_term_frequencies: list[Counter[str]] = []
    doc_frequencies: Counter[str] = Counter()
    for job in jobs:
        term_frequency = Counter(_tokenize(_job_to_search_text(job)))
        doc_term_frequencies.append(term_frequency)
        for term in term_frequency:
            doc_frequencies[term] += 1

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


@router.get("/load_model")
def load_model(model: str) -> ApiResponse:
    global pipe

    if model not in ALLOWED_MODELS:
        logger.warning(f"Model not recognized: {model}")

        return ApiResponse(status=400, message="Model not permitted")

    try:
        use_cuda = torch.cuda.is_available()

        pipe = pipeline(
            "text-generation",
            model=model,
            dtype=torch.bfloat16 if use_cuda else torch.float32,
            device_map="auto" if use_cuda else None,
        )

        return ApiResponse(status=200, message="Model successfully loaded")

    except Exception:
        logger.exception("Failed to load model")

        return ApiResponse(status=500, message="Unable to load model")


@router.post("/analyse_job")
def analyse_job(payload: AnalyseJobRequest) -> ApiResponse:
    global generation_config
    if pipe is None:
        logger.exception("Model not set")

        return ApiResponse(status=500, message="Unable to load model")

    try:
        messages = [
            {"role": "system", "content": prompts["analyse_job"]["system"]},
            {"role": "user", "content": f'{prompts["analyse_job"]["user"]} {payload.jd}'},
        ]

        prompt = pipe.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        outputs = pipe(
            prompt,
            generation_config=generation_config,
            return_full_text=False,
        )

        output = outputs[0]["generated_text"]

        return ApiResponse(status=200, message=output)

    except Exception:
        logger.exception("Failed to analyse job")
        return ApiResponse(status=500, message="Unable to analyse job")


@router.post("/query_job_board")
def query_job_board(payload: QueryJobBoardRequest) -> QueryJobBoardResponse:
    global generation_config
    if pipe is None:
        logger.error("Model not set")
        return QueryJobBoardResponse(status=500, message="Unable to load model", sources=[])

    try:
        jobs = _load_job_descriptions()
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        logger.exception("Failed to load job descriptions")
        return QueryJobBoardResponse(status=500, message=str(exc), sources=[])

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
        prompt = pipe.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        outputs = pipe(
            prompt,
            generation_config=generation_config,
            return_full_text=False,
        )
        output = outputs[0]["generated_text"]
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        logger.exception("Failed to answer job board query")
        return QueryJobBoardResponse(status=500, message=str(exc), sources=[])

    response_sources = [
        QuerySource(
            title=job["title"],
            location=job["location"],
            company=job["company"],
            salary=job["salary"],
            source_file=job["source_file"],
        )
        for job in relevant_jobs
    ]
    return QueryJobBoardResponse(status=200, message=output, sources=response_sources)
