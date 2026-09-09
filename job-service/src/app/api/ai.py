import json
import logging
import os
import re
import secrets
import sys
import threading
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from urllib import error as urlerror
from urllib import request as urlrequest

import torch
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from .schemas import (
    AnalyseJobRequest,
    ApiResponse,
    ChatRequest,
    LoadModelRequest,
    QueryJobBoardRequest,
    QueryJobBoardResponse,
    QuerySource,
)

logger = logging.getLogger(__name__)


def _resolve_dotenv_path() -> str | None:
    module_path = Path(__file__).resolve()
    project_root = module_path.parents[3]

    configured_path = os.getenv("JOB_SERVICE_DOTENV_PATH")
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        if candidate.exists():
            return str(candidate)
        logger.warning("Configured dotenv path does not exist: %s", candidate)

    candidates = (
        project_root / ".env",
        project_root.parent / ".env",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


dotenv_path = _resolve_dotenv_path()
if dotenv_path:
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

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

ALLOWED_MODELS = {"openai.gpt-oss-120b-1:0"}
JOB_VECTOR_COLLECTION = "jobs"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.95
DEFAULT_TOP_K = 50
DEFAULT_CHAT_COMPLETIONS_URL_TEMPLATE = "https://bedrock-runtime.{region}.amazonaws.com/openai/v1/chat/completions"
DEFAULT_BEDROCK_REGION = "eu-west-1"


def _qdrant_storage_path() -> Path:
    return _job_descriptions_dir().parent / "vector-db"


@lru_cache(maxsize=1)
def _load_embedding_model() -> SentenceTransformer:
    model_name = os.getenv("JOB_SERVICE_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return SentenceTransformer(model_name)


class QdrantJobVectorDatabase:
    """Local Qdrant vector store for job descriptions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._client: QdrantClient | None = None
        self._embedder: SentenceTransformer | None = None
        self._jobs_by_point_id: dict[int, dict[str, str]] = {}

    def _get_client(self) -> QdrantClient:
        if self._client is not None:
            return self._client

        storage_path = str(_qdrant_storage_path())
        try:
            self._client = QdrantClient(path=storage_path)
        except RuntimeError as exc:
            if "already accessed by another instance" not in str(exc):
                raise
            logger.warning(
                "Qdrant local storage is locked at %s; falling back to in-memory store for this process",
                storage_path,
            )
            self._client = QdrantClient(path=":memory:")
        return self._client

    def is_loaded(self) -> bool:
        with self._lock:
            return bool(self._jobs_by_point_id)

    def _collection_exists(self) -> bool:
        client = self._get_client()
        existing_collections = client.get_collections()
        return any(collection.name == JOB_VECTOR_COLLECTION for collection in existing_collections.collections)

    def load_jobs(self, jobs: tuple[dict[str, str], ...]) -> None:
        if not jobs:
            with self._lock:
                self._jobs_by_point_id = {}
            return

        with self._lock:
            if self._embedder is None:
                self._embedder = _load_embedding_model()

            job_texts = [_job_to_search_text(job) for job in jobs]
            embeddings = self._embedder.encode(job_texts, normalize_embeddings=True)
            vector_size = len(embeddings[0])
            client = self._get_client()

            if self._collection_exists():
                client.delete_collection(collection_name=JOB_VECTOR_COLLECTION)
            client.create_collection(
                collection_name=JOB_VECTOR_COLLECTION,
                vectors_config=qdrant_models.VectorParams(
                    size=vector_size,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

            points: list[qdrant_models.PointStruct] = []
            jobs_by_point_id: dict[int, dict[str, str]] = {}
            for idx, job in enumerate(jobs):
                points.append(
                    qdrant_models.PointStruct(
                        id=idx,
                        vector=embeddings[idx].tolist(),
                        payload=job,
                    )
                )
                jobs_by_point_id[idx] = job

            client.upsert(collection_name=JOB_VECTOR_COLLECTION, points=points, wait=True)
            self._jobs_by_point_id = jobs_by_point_id

    def jobs(self) -> tuple[dict[str, str], ...]:
        with self._lock:
            if not self._jobs_by_point_id:
                raise RuntimeError("Job vector database is not loaded")
            return tuple(self._jobs_by_point_id[idx] for idx in sorted(self._jobs_by_point_id))

    def search(self, query: str, top_k: int) -> list[dict[str, str]]:
        with self._lock:
            if not self._jobs_by_point_id:
                raise RuntimeError("Job vector database is not loaded")
            if self._embedder is None:
                self._embedder = _load_embedding_model()
            client = self._get_client()

            query_vector = self._embedder.encode(query, normalize_embeddings=True).tolist()
            if hasattr(client, "query_points"):
                query_response = client.query_points(
                    collection_name=JOB_VECTOR_COLLECTION,
                    query=query_vector,
                    limit=top_k,
                    with_payload=True,
                )
                search_results = query_response.points
            else:
                search_results = client.search(
                    collection_name=JOB_VECTOR_COLLECTION,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True,
                )

            matched_jobs: list[dict[str, str]] = []
            for result in search_results:
                point_id = result.id
                if isinstance(point_id, int) and point_id in self._jobs_by_point_id:
                    matched_jobs.append(self._jobs_by_point_id[point_id])
                    continue

                payload = result.payload or {}
                matched_jobs.append(
                    {
                        "id": str(payload.get("id", "")).strip(),
                        "title": str(payload.get("title", "")).strip(),
                        "location": str(payload.get("location", "")).strip(),
                        "company": str(payload.get("company", "")).strip(),
                        "salary": str(payload.get("salary", "")).strip(),
                        "jd": str(payload.get("jd", "")).strip(),
                        "source_file": str(payload.get("source_file", "")).strip(),
                    }
                )
            return matched_jobs


class ModelService:
    def __init__(self) -> None:
        self._model_id: str | None = None
        self._api_key: str | None = None
        self._api_url: str | None = None
        self._lock = threading.RLock()

    def is_loaded(self) -> bool:
        with self._lock:
            return self._model_id is not None and self._api_key is not None and self._api_url is not None

    def load_model(self, model: str) -> None:
        api_key = os.getenv("BEDROCK_API_KEY")
        if not api_key:
            raise RuntimeError("BEDROCK_API_KEY is not configured")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or DEFAULT_BEDROCK_REGION
        default_api_url = DEFAULT_CHAT_COMPLETIONS_URL_TEMPLATE.format(region=region)
        api_url = os.getenv("BEDROCK_API_URL", default_api_url)

        with self._lock:
            self._model_id = model
            self._api_key = api_key
            self._api_url = api_url

    def generate_text(self, messages: list[dict[str, str]]) -> str:
        with self._lock:
            if self._model_id is None or self._api_key is None or self._api_url is None:
                raise RuntimeError("Model not loaded")
            model_id = self._model_id
            api_key = self._api_key
            api_url = self._api_url

        chat_messages: list[dict[str, str]] = []

        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role in ("system", "user", "assistant"):
                chat_messages.append({"role": role, "content": content})
                continue
            raise ValueError(f"Unsupported role: {role}")

        if not chat_messages:
            chat_messages = [{"role": "user", "content": ""}]

        request_payload: dict[str, Any] = {
            "model": model_id,
            "messages": chat_messages,
            "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
            "top_p": DEFAULT_TOP_P,
        }
        if DEFAULT_TOP_K > 0:
            request_payload["top_k"] = DEFAULT_TOP_K

        request_data = json.dumps(request_payload).encode("utf-8")
        request = urlrequest.Request(
            api_url,
            data=request_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=60) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            error_text = ""
            if exc.fp is not None:
                error_text = exc.fp.read().decode("utf-8", errors="replace")
            if exc.code == 401:
                raise RuntimeError(
                    "Unauthorized by upstream chat endpoint. Verify BEDROCK_API_KEY and BEDROCK_API_URL/region."
                ) from exc
            raise RuntimeError(f"Upstream chat endpoint error ({exc.code}): {error_text}") from exc

        output_text: str | None = None
        choices = response_payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        output_text = content
                    elif isinstance(content, list):
                        output_text = "".join(
                            chunk.get("text", "")
                            for chunk in content
                            if isinstance(chunk, dict) and isinstance(chunk.get("text"), str)
                        )
        if not output_text:
            raise ValueError("Chat completions response did not include generated text")

        return _strip_reasoning_tags(output_text)


def _job_descriptions_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "job-descriptions"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _strip_reasoning_tags(text: str) -> str:
    return re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _normalize_job(raw_job: dict, source_file: str) -> dict[str, str]:
    return {
        "id": str(raw_job.get("id", Path(source_file).stem)).strip(),
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
    if job_vector_database.is_loaded():
        return job_vector_database.jobs()

    jobs = tuple(_load_job_descriptions())
    try:
        job_vector_database.load_jobs(jobs)
    except (RuntimeError, ValueError, OSError):
        logger.exception("Failed to populate local Qdrant job vectors")
    return jobs


def _job_to_search_text(job: dict[str, str]) -> str:
    return " ".join([job["title"], job["location"], job["company"], job["salary"], job["jd"]])


def _build_job_index_from_jobs(jobs: tuple[dict[str, str], ...]) -> tuple[tuple[Counter[str], ...], Counter[str]]:
    doc_term_frequencies: list[Counter[str]] = []
    doc_frequencies: Counter[str] = Counter()
    for job in jobs:
        term_frequency = Counter(_tokenize(_job_to_search_text(job)))
        doc_term_frequencies.append(term_frequency)
        for term in term_frequency:
            doc_frequencies[term] += 1
    return tuple(doc_term_frequencies), doc_frequencies


job_vector_database = QdrantJobVectorDatabase()


def initialize_job_vector_database() -> None:
    """Load all job descriptions into the local Qdrant vector database."""
    try:
        jobs = tuple(_load_job_descriptions())
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError, RuntimeError):
        logger.exception("Failed to initialize local job vector database")
        return

    job_vector_database.load_jobs(jobs)
    _load_job_descriptions_cached.cache_clear()
    _build_job_index.cache_clear()


@lru_cache(maxsize=1)
def _build_job_index() -> tuple[tuple[Counter[str], ...], Counter[str]]:
    jobs = _load_job_descriptions_cached()
    return _build_job_index_from_jobs(jobs)


def _rank_relevant_jobs(query: str, jobs: list[dict[str, str]], top_k: int) -> list[dict[str, str]]:
    if top_k <= 0:
        return []

    query_terms = Counter(_tokenize(query))
    if not query_terms:
        return jobs[:top_k]

    try:
        vector_results = job_vector_database.search(query, top_k)
    except (RuntimeError, ValueError, OSError):
        logger.exception("Vector search failed, falling back to default ordering")
        return jobs[:top_k]

    if not vector_results:
        return jobs[:top_k]

    return vector_results[:top_k]


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


def _build_chat_retrieval_query(cv: str, message_history: list[dict[str, str]]) -> str:
    formatted_history = "\n".join(
        f"{message['role']}: {message['content']}" for message in message_history if message.get("content")
    )
    return f"CV:\n{cv}\n\nConversation:\n{formatted_history}"


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
            id=str(job.get("id", Path(str(job.get("source_file", ""))).stem)).strip(),
            title=str(job.get("title", "")).strip(),
            location=str(job.get("location", "")).strip(),
            company=str(job.get("company", "")).strip(),
            salary=str(job.get("salary", "")).strip(),
            source_file=str(job.get("source_file", "")).strip(),
        )
        for job in relevant_jobs
    ]
    response.status_code = status.HTTP_200_OK
    return QueryJobBoardResponse(status=200, message=output, sources=response_sources)


@router.post("/chat")
def chat(payload: ChatRequest, response: Response) -> ApiResponse:
    if not model_service.is_loaded():
        logger.error("Model not set")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(status=503, message="Model not loaded")

    try:
        jobs = list(_load_job_descriptions_cached())
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        logger.exception("Failed to load job descriptions")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiResponse(status=500, message="Unable to load job descriptions")

    message_history = [message.model_dump() for message in payload.message_history]
    retrieval_query = _build_chat_retrieval_query(payload.cv, message_history)
    relevant_jobs = _rank_relevant_jobs(retrieval_query, jobs, top_k=3)
    rag_context = _build_rag_context(relevant_jobs) if relevant_jobs else "No relevant jobs were found."
    chat_prompt = prompts.get("chat", {})

    system_prompt = chat_prompt.get(
        "system",
        (
            "You are a job recruitment specialist. Use the CV and relevant jobs to guide your answer. "
            "If information is missing, say so clearly."
        ),
    )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                f"{system_prompt}{payload.cv}\n\n"
                f"Relevant jobs from the job board:\n{rag_context}\n\n"
                "Use the conversation history and this context to answer the user."
            ),
        }
    ]
    preface_prompt = chat_prompt.get("user", "").strip()
    if preface_prompt:
        messages.append({"role": "user", "content": preface_prompt})
    messages.extend(message_history)

    try:
        output = model_service.generate_text(messages)
    except (ValueError, RuntimeError, KeyError, TypeError):
        logger.exception("Failed to answer chat request")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiResponse(status=500, message="Unable to answer chat request")

    response.status_code = status.HTTP_200_OK
    return ApiResponse(status=200, message=output)
