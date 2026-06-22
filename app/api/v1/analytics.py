from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import ORJSONResponse

from app.api.dependencies import get_analytics_service
from app.schemas.analytics import AnalyticsSummaryResponse, AnalyticsUploadResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post(
    "/upload",
    response_model=AnalyticsUploadResponse,
    status_code=201,
    responses={200: {"model": AnalyticsUploadResponse}},
)
async def upload_analytics(
    file: Annotated[UploadFile, File()],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> ORJSONResponse:
    response, status_code = await service.upload(file)
    return ORJSONResponse(
        status_code=status_code, content=response.model_dump(mode="json", exclude_none=True)
    )


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def analytics_summary(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    dataset_id: Annotated[str | None, Query()] = None,
) -> AnalyticsSummaryResponse:
    result = await service.summary(dataset_id)
    return AnalyticsSummaryResponse.model_validate(result)
