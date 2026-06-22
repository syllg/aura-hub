from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field, field_serializer


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class DateRange(BaseModel):
    start: date
    end: date


class ImputedCells(BaseModel):
    total_revenue: int = 0
    visitor_count: int = 0


class ProcessingReport(BaseModel):
    rows_received: int
    rows_processed: int
    invalid_rows: int = 0
    duplicate_dates_merged: int
    imputed_cells: ImputedCells
    extra_columns_ignored: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnomalyDetectionReport(BaseModel):
    status: str
    method: str
    threshold: float
    median_revenue: float | None
    mad_revenue: float | None
    anomaly_count: int


class ImputationReport(BaseModel):
    method: str = "linear_interpolation"
    total_cells: int = 0


class AnalyticsUploadResponse(BaseModel):
    dataset_id: str
    filename: str | None = None
    checksum_sha256: str | None = None
    status: str
    duplicate: bool
    date_range: DateRange | None = None
    processing_report: ProcessingReport | None = None
    anomaly_detection: AnomalyDetectionReport | None = None
    imputation: ImputationReport | None = None
    created_at: datetime | None = None
    message: str | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        return _utc_iso(value)


class SummaryDataset(BaseModel):
    dataset_id: str
    filename: str
    date_start: date
    date_end: date
    row_count: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return _utc_iso(value)  # type: ignore[return-value]


class SummaryMetrics(BaseModel):
    total_revenue_raw: int
    total_revenue_clean: int
    revenue_excluded_as_anomaly: int
    total_visitors_raw: int
    total_visitors_excluding_revenue_anomalies: int
    visitors_on_anomaly_rows: int
    average_daily_visitors_raw: float
    average_daily_visitors_excluding_revenue_anomalies: float
    average_daily_revenue_raw: float
    average_daily_revenue_clean: float
    anomaly_count: int
    anomaly_rate: float


class WeeklyTrendItem(BaseModel):
    week_start: date
    week_end: date
    observed_days: int
    clean_days: int
    raw_revenue: int
    clean_revenue: int
    raw_average_daily_revenue: float
    clean_average_daily_revenue: float
    raw_visitors: int
    visitors_excluding_revenue_anomalies: int
    anomaly_count: int


class AnomalyItem(BaseModel):
    date: date
    total_revenue: int
    visitor_count: int
    direction: str
    method: str
    score: float | None
    lower_bound: float | None = None
    upper_bound: float | None = None
    status: str = "requires_review"


class DailyRecordItem(BaseModel):
    date: date
    total_revenue: int
    visitor_count: int
    is_anomaly: bool
    anomaly_direction: str | None = None


class DataQuality(BaseModel):
    duplicate_dates_merged: int
    imputed_value_count: int
    warnings: list[str]


class AnalyticsSummaryResponse(BaseModel):
    dataset: SummaryDataset
    metrics: SummaryMetrics
    daily_records: list[DailyRecordItem]
    weekly_trend: list[WeeklyTrendItem]
    anomalies: list[AnomalyItem]
    data_quality: DataQuality
