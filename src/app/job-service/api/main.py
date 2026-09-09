from fastapi import FastAPI

from .ai import ApiResponse, is_model_loaded, router as ai_router

app = FastAPI(title="NewPage API", version="0.1.0")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "NewPage API is running"}


@app.get("/health")
def health() -> ApiResponse:
    """Report whether the API is ready to serve model requests.

    Returns:
        ApiResponse with status 200 if a model pipeline is loaded, or
        status 500 if no model has been loaded yet.
    """
    if not is_model_loaded():
        return ApiResponse(status=500, message="Model not loaded")

    return ApiResponse(status=200, message="ok")


app.include_router(ai_router)
