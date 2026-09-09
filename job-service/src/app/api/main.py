from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .ai import initialize_job_vector_database, is_model_loaded, router as ai_router
from .jobs import router as jobs_router
from .schemas import ApiResponse

app = FastAPI(title="NewPage API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def load_job_vectors_on_startup() -> None:
    initialize_job_vector_database()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "NewPage API is running"}


@app.get("/health")
def health(response: Response) -> ApiResponse:
    """Report whether the API is ready to serve model requests.

    Returns:
        ApiResponse with status 200 if a model pipeline is loaded, or
        status 503 if no model has been loaded yet.
    """
    if not is_model_loaded():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(status=503, message="Model not loaded")

    response.status_code = status.HTTP_200_OK
    return ApiResponse(status=200, message="ok")


app.include_router(ai_router)
app.include_router(jobs_router)
