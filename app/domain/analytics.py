from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from app.domain.anomaly import AnomalyResult, detect_revenue_anomalies


class AnalyticsDataError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(slots=True)
class ProcessedRow:
    date: date
    total_revenue: int
    visitor_count: int
    revenue_was_imputed: bool
    visitor_was_imputed: bool
    is_anomaly: bool
    anomaly_direction: str | None
    anomaly_method: str
    anomaly_score: float | None
    lower_bound: float | None
    upper_bound: float | None


@dataclass(slots=True)
class ProcessedAnalytics:
    rows_received: int
    rows: list[ProcessedRow]
    duplicate_dates_merged: int
    imputed_cells: dict[str, int]
    extra_columns_ignored: list[str]
    warnings: list[str]
    anomaly: AnomalyResult
    total_revenue_raw: int
    total_revenue_clean: int
    total_visitors: int

    @property
    def date_start(self) -> date:
        return self.rows[0].date

    @property
    def date_end(self) -> date:
        return self.rows[-1].date


REQUIRED_COLUMNS = {"date", "total_revenue", "visitor_count"}


def _csv_row_numbers(mask: pd.Series) -> list[int]:
    return [int(index) + 2 for index in mask[mask].index.tolist()]


def process_analytics_csv(
    path: Path,
    *,
    modified_z_threshold: float,
    iqr_multiplier: float,
    minimum_rows: int,
) -> ProcessedAnalytics:
    try:
        frame = pd.read_csv(path)
    except EmptyDataError as exc:
        raise AnalyticsDataError("EMPTY_CSV", "CSV tidak memiliki data.") from exc
    except (ParserError, UnicodeDecodeError) as exc:
        raise AnalyticsDataError("INVALID_CSV", "CSV tidak dapat dibaca.") from exc
    if frame.empty:
        raise AnalyticsDataError("EMPTY_CSV", "CSV tidak memiliki baris data.")

    normalized = [str(column).strip().lower() for column in frame.columns]
    if len(normalized) != len(set(normalized)):
        raise AnalyticsDataError(
            "INVALID_CSV_SCHEMA", "Nama kolom menjadi duplikat setelah normalisasi."
        )
    frame.columns = normalized
    missing_columns = sorted(REQUIRED_COLUMNS - set(normalized))
    if missing_columns:
        raise AnalyticsDataError(
            "INVALID_CSV_SCHEMA",
            "CSV tidak memiliki seluruh kolom wajib.",
            {
                "required_columns": sorted(REQUIRED_COLUMNS),
                "missing_columns": missing_columns,
                "received_columns": normalized,
            },
        )
    extra_columns = sorted(set(normalized) - REQUIRED_COLUMNS)
    frame = frame[["date", "total_revenue", "visitor_count"]].copy()
    rows_received = len(frame)

    parsed_dates = pd.to_datetime(frame["date"], errors="coerce")
    invalid_dates = parsed_dates.isna()
    if invalid_dates.any():
        raise AnalyticsDataError(
            "INVALID_DATE_VALUES",
            "Terdapat nilai tanggal yang tidak valid.",
            {"row_numbers": _csv_row_numbers(invalid_dates)},
        )
    frame["date"] = parsed_dates.dt.normalize()

    for column in ("total_revenue", "visitor_count"):
        raw = frame[column]
        original_missing = raw.isna() | raw.astype(str).str.strip().eq("")
        parsed = pd.to_numeric(raw, errors="coerce")
        invalid_numeric = parsed.isna() & ~original_missing
        if invalid_numeric.any():
            raise AnalyticsDataError(
                "INVALID_NUMERIC_VALUES",
                f"Kolom {column} memiliki nilai non-numeric.",
                {"column": column, "row_numbers": _csv_row_numbers(invalid_numeric)},
            )
        negative = parsed < 0
        if negative.any():
            raise AnalyticsDataError(
                "NEGATIVE_METRIC_VALUES",
                "Revenue dan visitor tidak boleh bernilai negatif.",
                {"column": column, "row_numbers": _csv_row_numbers(negative)},
            )
        if parsed.isna().all():
            raise AnalyticsDataError(
                "NUMERIC_COLUMN_ALL_MISSING",
                f"Seluruh nilai kolom {column} kosong.",
                {"column": column},
            )
        frame[column] = parsed

    frame = frame.sort_values("date", kind="stable")
    grouped = (
        frame.groupby("date", as_index=False)
        .agg(
            total_revenue=("total_revenue", lambda values: values.sum(min_count=1)),
            visitor_count=("visitor_count", lambda values: values.sum(min_count=1)),
        )
        .sort_values("date")
    )
    duplicate_dates_merged = rows_received - len(grouped)

    grouped = grouped.set_index("date")
    imputation_flags: dict[str, pd.Series] = {}
    imputed_cells: dict[str, int] = {}
    for column in ("total_revenue", "visitor_count"):
        missing = grouped[column].isna()
        imputation_flags[column] = missing.copy()
        imputed_cells[column] = int(missing.sum())
        interpolated = grouped[column].interpolate(method="time", limit_area="inside")
        median = interpolated.median(skipna=True)
        grouped[column] = interpolated.fillna(median)

    grouped["total_revenue"] = grouped["total_revenue"].round().astype("int64")
    grouped["visitor_count"] = grouped["visitor_count"].round().astype("int64")
    if (grouped[["total_revenue", "visitor_count"]] < 0).any().any():
        raise AnalyticsDataError(
            "NEGATIVE_METRIC_VALUES",
            "Hasil preprocessing tidak boleh bernilai negatif.",
        )

    anomaly = detect_revenue_anomalies(
        grouped["total_revenue"].to_numpy(dtype=float),
        modified_z_threshold=modified_z_threshold,
        iqr_multiplier=iqr_multiplier,
        minimum_rows=minimum_rows,
    )
    warnings: list[str] = []
    if extra_columns:
        warnings.append("Kolom tambahan diabaikan: " + ", ".join(extra_columns))
    if anomaly.status == "insufficient_data":
        warnings.append(f"Deteksi anomali membutuhkan minimal {minimum_rows} baris terproses.")

    rows: list[ProcessedRow] = []
    for position, (timestamp, values) in enumerate(grouped.iterrows()):
        rows.append(
            ProcessedRow(
                date=timestamp.date(),
                total_revenue=int(values["total_revenue"]),
                visitor_count=int(values["visitor_count"]),
                revenue_was_imputed=bool(imputation_flags["total_revenue"].iloc[position]),
                visitor_was_imputed=bool(imputation_flags["visitor_count"].iloc[position]),
                is_anomaly=bool(anomaly.is_anomaly[position]),
                anomaly_direction=anomaly.direction[position],
                anomaly_method=anomaly.method,
                anomaly_score=anomaly.scores[position],
                lower_bound=anomaly.lower_bound,
                upper_bound=anomaly.upper_bound,
            )
        )

    total_raw = sum(row.total_revenue for row in rows)
    total_clean = sum(row.total_revenue for row in rows if not row.is_anomaly)
    return ProcessedAnalytics(
        rows_received=rows_received,
        rows=rows,
        duplicate_dates_merged=duplicate_dates_merged,
        imputed_cells=imputed_cells,
        extra_columns_ignored=extra_columns,
        warnings=warnings,
        anomaly=anomaly,
        total_revenue_raw=total_raw,
        total_revenue_clean=total_clean,
        total_visitors=sum(row.visitor_count for row in rows),
    )
