from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import ORJSONResponse

from app.api.dependencies import get_rag_service
from app.schemas.rag import RAGIngestResponse, RAGQueryRequest, RAGQueryResponse
from app.services.rag_service import RAGService

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/ingest",
    response_model=RAGIngestResponse,
    status_code=201,
    responses={200: {"model": RAGIngestResponse}},
)
async def ingest_document(
    file: Annotated[UploadFile, File()],
    service: Annotated[RAGService, Depends(get_rag_service)],
    replace_existing: Annotated[bool, Form()] = False,
) -> ORJSONResponse:
    del replace_existing  # Reserved by the public contract; checksum remains authoritative.
    response, status_code = await service.ingest(file)
    return ORJSONResponse(
        status_code=status_code, content=response.model_dump(mode="json", exclude_none=True)
    )


@router.post("/query", response_model=RAGQueryResponse)
async def query_documents(
    body: RAGQueryRequest,
    service: Annotated[RAGService, Depends(get_rag_service)],
) -> RAGQueryResponse:
    return await service.query(body)
