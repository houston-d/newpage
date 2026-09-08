import json
import os
import sys

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import GenerationConfig, pipeline

# Temporary output to confirm CUDA is enabled
print("=== runtime diag ===")
print("python:", sys.executable)
print("torch:", torch.__version__)
print("torch cuda runtime:", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())
print("device count:", torch.cuda.device_count())
print("CUDA_VISIBLE_DEVICES:", os.getenv("CUDA_VISIBLE_DEVICES"))
if torch.cuda.is_available():
    print("device 0:", torch.cuda.get_device_name(0))
print("====================")

app = FastAPI(title="NewPage API", version="0.1.0")

pipe = None

prompts_path = os.path.join(os.path.dirname(__file__), os.pardir, "resources", "prompts.json")
with open(prompts_path) as f:
    prompts = json.load(f)


class AnalyseJobRequest(BaseModel):
    jd: str


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "NewPage API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": 200, "message": "ok"}


@app.get("/load_model")
def load_model(model: str) -> dict[str, str | int]:
    global pipe
    try:
        use_cuda = torch.cuda.is_available()

        pipe = pipeline(
            "text-generation",
            model=model,
            dtype=torch.bfloat16 if use_cuda else torch.float32,
            device_map="auto" if use_cuda else None,
        )

        return {"status": 200, "message": "Model successfully loaded"}

    except Exception as e:
        print(e)
        pipe = None

        return {"status": 500, "message": "Unable to load model"}


@app.post("/analyse_job")
def analyse_job(payload: AnalyseJobRequest) -> dict[str, str | int]:
    if pipe is None:
        return {"status": 500, "message": "Unable to load model"}

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

        generation_config = GenerationConfig(
            max_new_tokens=2048,
            do_sample=True,
            temperature=0.7,
            top_k=50,
            top_p=0.95,
        )

        outputs = pipe(
            prompt,
            generation_config=generation_config,
            return_full_text=False,
        )

        output = outputs[0]["generated_text"]

        return {"status": 200, "message": output}

    except Exception as e:
        print(f"Error analysing job: {e}")
        return {"status": 500, "message": "Unable to analyse job"}
