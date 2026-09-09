"""Request and response models shared across the API routers."""

from typing import Literal

from pydantic import BaseModel, Field


class AnalyseJobRequest(BaseModel):
    jd: str = Field(..., min_length=10, max_length=20000)


class LoadModelRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)


class QueryJobBoardRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)


class QuerySource(BaseModel):
    id: str
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


class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str = Field(..., min_length=1, max_length=5000)


class ChatRequest(BaseModel):
    cv: str = Field(..., min_length=1, max_length=200000)
    message_history: list[ChatMessage] = Field(..., min_length=1, max_length=100)


class Job(BaseModel):
    id: str
    title: str
    location: str
    company: str
    salary: str
    jd: str
    source_file: str


class JobsResponse(ApiResponse):
    jobs: list[Job] = Field(default_factory=list)


class JobResponse(ApiResponse):
    job: Job | None = None
