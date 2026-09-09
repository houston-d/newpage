from fastapi import FastAPI, Response, status

from .ai import is_model_loaded, router as ai_router
from .schemas import ApiResponse

app = FastAPI(title="NewPage API", version="0.1.0")


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
