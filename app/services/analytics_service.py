from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import AppError
from app.domain.analytics import AnalyticsDataError, process_analytics_csv
from app.domain.summary import build_analytics_summary
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import AnalyticsUploadResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    @staticmethod
    def _build_imputation(
        imputed_cells: dict[str, int],
    ) -> tuple[dict[str, Any] | None, str | None]:
        total = sum(imputed_cells.values())
        if total == 0:
            return None, None
        parts = []
        for column, count in imputed_cells.items():
            if count > 0:
                parts.append(f"{count} nilai {column}")
        warning = f"{' dan '.join(parts)} berhasil diimputasi."
        return {"method": "linear_interpolation", "total_cells": total}, warning

    async def upload(self, upload: UploadFile) -> tuple[AnalyticsUploadResponse, int]:
        filename = Path(upload.filename or "upload.csv").name
        extension = Path(filename).suffix.lower()
        if extension != ".csv":
            raise AppError(
                "UNSUPPORTED_ANALYTICS_FILE",
                "File analytics harus berformat CSV.",
                status_code=415,
            )
        if upload.content_type not in {
            "text/csv",
            "application/csv",
            "application/vnd.ms-excel",
            "application/octet-stream",
        }:
            raise AppError(
                "UNSUPPORTED_ANALYTICS_FILE",
                "MIME type file analytics tidak didukung.",
                status_code=415,
            )

        temporary_path: Path | None = None
        checksum = hashlib.sha256()
        size = 0
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as handle:
                temporary_path = Path(handle.name)
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_csv_size_mb * 1024 * 1024:
                        raise AppError(
                            "FILE_TOO_LARGE",
                            "Ukuran CSV melebihi batas yang diizinkan.",
                            status_code=413,
                        )
                    checksum.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
            if size == 0:
                raise AppError("EMPTY_CSV", "CSV kosong.", status_code=422)
            digest = checksum.hexdigest()
            existing = await self.repository.get_by_checksum(digest)
            if existing and existing.status == "completed":
                logger.info(
                    "analytics_duplicate dataset_id=%s checksum=%s",
                    existing.id,
                    digest[:12],
                )
                imputation, imputation_warning = self._build_imputation(existing.imputed_cells_json)
                warnings = list(existing.warnings_json)
                if imputation_warning:
                    warnings.append(imputation_warning)
                return (
                    AnalyticsUploadResponse(
                        dataset_id=existing.id,
                        filename=existing.filename,
                        checksum_sha256=existing.checksum_sha256,
                        status=existing.status,
                        duplicate=True,
                        date_range={"start": existing.date_min, "end": existing.date_max},
                        processing_report={
                            "rows_received": existing.row_count_input,
                            "rows_processed": existing.row_count_processed,
                            "invalid_rows": 0,
                            "duplicate_dates_merged": existing.duplicate_dates_merged,
                            "imputed_cells": existing.imputed_cells_json,
                            "extra_columns_ignored": existing.extra_columns_json,
                            "warnings": warnings,
                        },
                        anomaly_detection={
                            "status": existing.anomaly_detection_status,
                            "method": existing.anomaly_method,
                            "threshold": existing.anomaly_threshold,
                            "median_revenue": existing.median_revenue,
                            "mad_revenue": existing.mad_revenue,
                            "anomaly_count": existing.anomaly_count,
                        },
                        imputation=imputation,
                        created_at=existing.created_at,
                        message="Dataset dengan isi yang sama sudah pernah diproses.",
                    ),
                    200,
                )

            try:
                processed = await asyncio.to_thread(
                    process_analytics_csv,
                    temporary_path,
                    modified_z_threshold=self.settings.anomaly_modified_z_threshold,
                    iqr_multiplier=self.settings.anomaly_iqr_multiplier,
                    minimum_rows=self.settings.anomaly_min_rows,
                )
            except AnalyticsDataError as exc:
                raise AppError(exc.code, exc.message, status_code=422, details=exc.details) from exc
            dataset = await self.repository.save_completed(
                filename=filename, checksum=digest, processed=processed
            )
            logger.info(
                "analytics_completed dataset_id=%s checksum=%s rows=%s anomalies=%s",
                dataset.id,
                digest[:12],
                dataset.row_count_processed,
                dataset.anomaly_count,
            )
            imputation, imputation_warning = self._build_imputation(dataset.imputed_cells_json)
            warnings = list(dataset.warnings_json)
            if imputation_warning:
                warnings.append(imputation_warning)
            response = AnalyticsUploadResponse(
                dataset_id=dataset.id,
                filename=dataset.filename,
                checksum_sha256=dataset.checksum_sha256,
                status=dataset.status,
                duplicate=False,
                date_range={"start": dataset.date_min, "end": dataset.date_max},
                processing_report={
                    "rows_received": dataset.row_count_input,
                    "rows_processed": dataset.row_count_processed,
                    "invalid_rows": 0,
                    "duplicate_dates_merged": dataset.duplicate_dates_merged,
                    "imputed_cells": dataset.imputed_cells_json,
                    "extra_columns_ignored": dataset.extra_columns_json,
                    "warnings": warnings,
                },
                anomaly_detection={
                    "status": dataset.anomaly_detection_status,
                    "method": dataset.anomaly_method,
                    "threshold": dataset.anomaly_threshold,
                    "median_revenue": dataset.median_revenue,
                    "mad_revenue": dataset.mad_revenue,
                    "anomaly_count": dataset.anomaly_count,
                },
                imputation=imputation,
                created_at=dataset.created_at,
            )
            return response, 201
        finally:
            await upload.close()
            if temporary_path is not None:
                await asyncio.to_thread(os.unlink, temporary_path)

    async def summary(self, dataset_id: str | None = None) -> dict:
        dataset = await self.repository.get_with_rows(dataset_id)
        if dataset is None:
            raise AppError(
                "ANALYTICS_DATASET_NOT_FOUND",
                "Dataset analytics tidak ditemukan.",
                status_code=404,
            )
        if dataset.status != "completed":
            raise AppError(
                "ANALYTICS_DATASET_NOT_READY",
                "Dataset belum selesai diproses.",
                status_code=409,
            )
        return build_analytics_summary(dataset)
