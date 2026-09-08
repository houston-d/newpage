import json
import os
import sys

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import GenerationConfig, pipeline
import logging
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

app = FastAPI(title="NewPage API", version="0.1.0")

pipe = None

prompts_path = os.path.join(os.path.dirname(__file__), os.pardir, "resources", "prompts.json")
with open(prompts_path) as f:
    prompts = json.load(f)

generation_config = GenerationConfig(
    max_new_tokens=2048,
    do_sample=True,
    temperature=0.7,
    top_k=50,
    top_p=0.95,
)

ALLOWED_MODELS = {"TinyLlama/TinyLlama-1.1B-Chat-v1.0"}


class AnalyseJobRequest(BaseModel):
    jd: str = Field(..., min_length=10, max_length=20000)

class ApiResponse(BaseModel):
    status: int
    message: str


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
    if pipe is None:
        return ApiResponse(status=500, message="Model not loaded")

    return ApiResponse(status=200, message="ok")


@app.get("/load_model")
def load_model(model: str) -> ApiResponse:
    """Load a text-generation model into the global pipeline.

    Validates that the requested model is in the allowed set, then loads it
    using the `transformers` pipeline, selecting CUDA with bfloat16 if
    available, otherwise CPU with float32.

    Args:
        model: The identifier of the model to load (e.g. a HuggingFace
            model name). Must be one of ALLOWED_MODELS.

    Returns:
        ApiResponse with status 200 on success, 400 if the model is not
        permitted, or 500 if loading fails.
    """
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


@app.post("/analyse_job")
def analyse_job(payload: AnalyseJobRequest) -> ApiResponse:
    """Analyse a job description using the currently loaded model.

    Builds a chat prompt from the configured system/user prompts and the
    provided job description, runs generation, and returns the model's output.

    Args:
        payload: Request body containing the job description text (`jd`).

    Returns:
        ApiResponse with status 200 and the generated analysis in `message`
        on success, or status 500 if no model is loaded or generation fails.
    """
    global generation_config
    if pipe is None:
        logger.exception("Model not set")

        return ApiResponse(status=500, message="Unable to load model")

    try:
        messages = [
            {
                "role": "system",
                "content": prompts["analyse_job"]["system"]
            },
            {
                "role": "user",
                "content": f'{prompts["analyse_job"]["user"]} {payload.jd}'},
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

    except Exception as e:
        logger.exception("Failed to analyse job")
        return ApiResponse(status=500, message="Unable to analyse job")
