from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class ChunkTypeCounts(BaseModel):
    paragraph: int = 0
    table: int = 0
    list: int = 0


class IngestionProcessing(BaseModel):
    pages_extracted: int
    characters_extracted: int
    embedding_model: str
    duration_ms: int


class RAGIngestResponse(BaseModel):
    document_id: str
    filename: str
    checksum_sha256: str
    status: str
    duplicate: bool
    chunk_count: int
    chunk_type_counts: ChunkTypeCounts | None = None
    detected_document_version: str | None = None
    processing: IngestionProcessing | None = None
    created_at: datetime | None = None
    message: str | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        return _utc_iso(value)


class RAGQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[str] | None = None
    top_k: int = Field(default=3, ge=1, le=3)
    generate_answer: bool = True
    conversation_history: str | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("question terlalu pendek")
        return value


class ContextMetadata(BaseModel):
    filename: str
    chunk_type: Literal["paragraph", "table", "list"]
    heading_path: list[str]
    document_version: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class ContextScores(BaseModel):
    dense: float
    lexical: float
    heading_bonus: float
    final: float


class RAGContext(BaseModel):
    rank: int
    chunk_id: str
    document_id: str
    content: str
    metadata: ContextMetadata
    scores: ContextScores
    meets_minimum_score: bool = False
    used_for_generation: bool = False


class RetrievalScoreWeights(BaseModel):
    dense: float
    lexical: float
    heading_bonus: float


class RetrievalMetadata(BaseModel):
    candidate_count: int
    returned_count: int
    generation_context_count: int = 0
    embedding_model: str | None = None
    strategy: str | None = None
    reranker: str | None = None
    score_weights: RetrievalScoreWeights | None = None
    duration_ms: int | None = None
    minimum_score_applied: float | None = None


class GenerationMetadata(BaseModel):
    provider: str
    model: str
    duration_ms: int


class RAGQueryResponse(BaseModel):
    question: str
    answer: str | None
    generation_status: Literal["completed", "failed", "skipped", "skipped_no_relevant_context"]
    contexts: list[RAGContext]
    retrieval: RetrievalMetadata
    generation: GenerationMetadata | None = None
    warnings: list[str] = Field(default_factory=list)
