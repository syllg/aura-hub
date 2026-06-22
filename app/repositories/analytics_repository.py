from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models import AnalyticsDailyRowModel, AnalyticsDatasetModel
from app.domain.analytics import ProcessedAnalytics


class AnalyticsRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_checksum(self, checksum: str) -> AnalyticsDatasetModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AnalyticsDatasetModel).where(
                    AnalyticsDatasetModel.checksum_sha256 == checksum
                )
            )
            return result.scalar_one_or_none()

    async def save_completed(
        self, *, filename: str, checksum: str, processed: ProcessedAnalytics
    ) -> AnalyticsDatasetModel:
        anomaly = processed.anomaly
        dataset = AnalyticsDatasetModel(
            filename=filename,
            checksum_sha256=checksum,
            status="processing",
            row_count_input=processed.rows_received,
            row_count_processed=len(processed.rows),
            date_min=processed.date_start,
            date_max=processed.date_end,
            anomaly_detection_status=anomaly.status,
            anomaly_method=anomaly.method,
            anomaly_threshold=anomaly.threshold,
            median_revenue=anomaly.median,
            mad_revenue=anomaly.mad,
            anomaly_count=sum(row.is_anomaly for row in processed.rows),
            duplicate_dates_merged=processed.duplicate_dates_merged,
            imputed_value_count=sum(processed.imputed_cells.values()),
            imputed_cells_json=processed.imputed_cells,
            extra_columns_json=processed.extra_columns_ignored,
            total_revenue_raw=processed.total_revenue_raw,
            total_revenue_clean=processed.total_revenue_clean,
            total_visitors=processed.total_visitors,
            warnings_json=processed.warnings,
        )
        dataset.rows = [
            AnalyticsDailyRowModel(
                date=row.date,
                total_revenue=row.total_revenue,
                visitor_count=row.visitor_count,
                revenue_was_imputed=row.revenue_was_imputed,
                visitor_was_imputed=row.visitor_was_imputed,
                is_anomaly=row.is_anomaly,
                anomaly_direction=row.anomaly_direction,
                anomaly_method=row.anomaly_method,
                anomaly_score=row.anomaly_score,
                lower_bound=row.lower_bound,
                upper_bound=row.upper_bound,
            )
            for row in processed.rows
        ]
        async with self._session_factory() as session:
            session.add(dataset)
            dataset.status = "completed"
            await session.commit()
            await session.refresh(dataset)
            return dataset

    async def get_with_rows(self, dataset_id: str | None = None) -> AnalyticsDatasetModel | None:
        async with self._session_factory() as session:
            statement = select(AnalyticsDatasetModel).options(
                selectinload(AnalyticsDatasetModel.rows)
            )
            if dataset_id:
                statement = statement.where(AnalyticsDatasetModel.id == dataset_id)
            else:
                statement = (
                    statement.where(AnalyticsDatasetModel.status == "completed")
                    .order_by(AnalyticsDatasetModel.created_at.desc())
                    .limit(1)
                )
            result = await session.execute(statement)
            return result.scalar_one_or_none()
