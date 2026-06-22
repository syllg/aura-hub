from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.chat_intent import ChatIntent


class ChatQueryRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Berapa total revenue dataset ini?",
            }
        }
    )

    message: str = Field(min_length=2, max_length=2000)
    dataset_id: UUID | None = None
    document_ids: list[UUID] | None = None
    conversation_id: UUID | None = None


class ChatSource(BaseModel):
    type: Literal["document", "analytics"]
    label: str
    document_id: UUID | None = None
    dataset_id: UUID | None = None
    filename: str | None = None
    heading: str | None = None
    chunk_id: UUID | None = None
    relevance_score: float | None = None


class ChatQueryResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Dataset ini memiliki 3 anomali yang perlu ditinjau.",
                "intent": "analytics_anomaly",
                "tools_used": ["get_analytics_anomalies"],
                "sources": [
                    {
                        "type": "analytics",
                        "label": "sales_mock.csv",
                        "filename": "sales_mock.csv",
                    }
                ],
                "conversation_id": None,
                "warnings": [
                    "Anomali perlu direview dan tidak otomatis dianggap sebagai data salah."
                ],
            }
        }
    )

    answer: str
    intent: ChatIntent
    tools_used: list[str]
    sources: list[ChatSource]
    conversation_id: UUID | None = None
    warnings: list[str] = Field(default_factory=list)
