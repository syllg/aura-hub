from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid_str() -> str:
    return str(uuid4())


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    document_version: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    chunks: Mapped[list[DocumentChunkModel]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        UniqueConstraint("document_id", "content_hash", "chunk_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_type: Mapped[str] = mapped_column(String(20))
    heading_path_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    token_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped[DocumentModel] = relationship(back_populates="chunks")


class AnalyticsDatasetModel(Base):
    __tablename__ = "analytics_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    filename: Mapped[str] = mapped_column(String(255))
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    row_count_input: Mapped[int] = mapped_column(Integer, default=0)
    row_count_processed: Mapped[int] = mapped_column(Integer, default=0)
    date_min: Mapped[date | None] = mapped_column(Date)
    date_max: Mapped[date | None] = mapped_column(Date)
    anomaly_detection_status: Mapped[str] = mapped_column(String(30), default="completed")
    anomaly_method: Mapped[str] = mapped_column(String(50))
    anomaly_threshold: Mapped[float] = mapped_column(Float)
    median_revenue: Mapped[float | None] = mapped_column(Float)
    mad_revenue: Mapped[float | None] = mapped_column(Float)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_dates_merged: Mapped[int] = mapped_column(Integer, default=0)
    imputed_value_count: Mapped[int] = mapped_column(Integer, default=0)
    imputed_cells_json: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    extra_columns_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    total_revenue_raw: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue_clean: Mapped[int] = mapped_column(Integer, default=0)
    total_visitors: Mapped[int] = mapped_column(Integer, default=0)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    rows: Mapped[list[AnalyticsDailyRowModel]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class AnalyticsDailyRowModel(Base):
    __tablename__ = "analytics_daily_rows"
    __table_args__ = (
        UniqueConstraint("dataset_id", "date"),
        Index("ix_analytics_dataset_anomaly", "dataset_id", "is_anomaly"),
        Index("ix_analytics_dataset_date", "dataset_id", "date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("analytics_datasets.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    total_revenue: Mapped[int] = mapped_column(Integer)
    visitor_count: Mapped[int] = mapped_column(Integer)
    revenue_was_imputed: Mapped[bool] = mapped_column(Boolean, default=False)
    visitor_was_imputed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_direction: Mapped[str | None] = mapped_column(String(10))
    anomaly_method: Mapped[str] = mapped_column(String(50))
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float)
    upper_bound: Mapped[float | None] = mapped_column(Float)
    dataset: Mapped[AnalyticsDatasetModel] = relationship(back_populates="rows")
