from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class LiveResponse(BaseModel):
    status: str = "ok"


class ReadyDependencies(BaseModel):
    database: str
    qdrant: str
    openai: str
    llm_model: str
    embedding_model: str


class ReadyResponse(BaseModel):
    status: str
    dependencies: ReadyDependencies
