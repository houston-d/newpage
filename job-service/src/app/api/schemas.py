"""Request and response models shared across the API routers."""

from pydantic import BaseModel, Field


class AnalyseJobRequest(BaseModel):
    jd: str = Field(..., min_length=10, max_length=20000)


class LoadModelRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)


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
