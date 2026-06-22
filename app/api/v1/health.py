from __future__ import annotations

from fastapi import APIRouter, Request
from qdrant_client import AsyncQdrantClient
from sqlalchemy import text

from app.schemas.common import LiveResponse, ReadyResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse()


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> ReadyResponse:
    settings = request.app.state.settings
    database_status = "down"
    qdrant_status = "down"
    async with request.app.state.session_factory() as session:
        await session.execute(text("SELECT 1"))
        database_status = "up"
    client: AsyncQdrantClient = request.app.state.qdrant_client
    if await client.collection_exists(settings.qdrant_collection):
        qdrant_status = "up"
    configured = "configured" if settings.openai_api_key else "missing"
    return ReadyResponse(
        status="ready" if database_status == qdrant_status == "up" else "not_ready",
        dependencies={
            "database": database_status,
            "qdrant": qdrant_status,
            "openai": configured,
            "llm_model": settings.llm_model,
            "embedding_model": settings.embedding_model,
        },
    )
