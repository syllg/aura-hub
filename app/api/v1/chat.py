from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import ORJSONResponse

from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/assistant", tags=["AuraHub Assistant"])


@router.post("/query", response_model=ChatQueryResponse)
async def chat_query(
    body: ChatQueryRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ORJSONResponse:
    result = await service.query(body)
    return ORJSONResponse(
        content=result.model_dump(mode="json", exclude_none=True),
    )
