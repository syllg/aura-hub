from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class AnomalyResult:
    status: str
    method: str
    threshold: float
    median: float | None
    mad: float | None
    is_anomaly: np.ndarray
    direction: list[str | None]
    scores: list[float | None]
    lower_bound: float | None = None
    upper_bound: float | None = None


def detect_revenue_anomalies(
    values: np.ndarray,
    *,
    modified_z_threshold: float = 3.5,
    iqr_multiplier: float = 1.5,
    minimum_rows: int = 5,
) -> AnomalyResult:
    values = np.asarray(values, dtype=float)
    size = len(values)
    empty_flags = np.zeros(size, dtype=bool)
    if size < minimum_rows:
        return AnomalyResult(
            status="insufficient_data",
            method="modified_z_score",
            threshold=modified_z_threshold,
            median=float(np.median(values)) if size else None,
            mad=None,
            is_anomaly=empty_flags,
            direction=[None] * size,
            scores=[None] * size,
        )

    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad > 0:
        raw_scores = 0.6745 * (values - median) / mad
        flags = np.abs(raw_scores) > modified_z_threshold
        directions = [
            "high" if flag and score > 0 else "low" if flag else None
            for flag, score in zip(flags, raw_scores, strict=True)
        ]
        bound_offset = modified_z_threshold * mad / 0.6745
        return AnomalyResult(
            status="completed",
            method="modified_z_score",
            threshold=modified_z_threshold,
            median=median,
            mad=mad,
            is_anomaly=flags,
            direction=directions,
            scores=[float(score) for score in raw_scores],
            lower_bound=median - bound_offset,
            upper_bound=median + bound_offset,
        )

    q1, q3 = (float(value) for value in np.quantile(values, [0.25, 0.75]))
    iqr = q3 - q1
    if iqr > 0:
        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr
        flags = (values < lower) | (values > upper)
        directions = [
            "high" if flag and value > median else "low" if flag else None
            for flag, value in zip(flags, values, strict=True)
        ]
        return AnomalyResult(
            status="completed",
            method="iqr",
            threshold=iqr_multiplier,
            median=median,
            mad=mad,
            is_anomaly=flags,
            direction=directions,
            scores=[None] * size,
            lower_bound=lower,
            upper_bound=upper,
        )

    flags = values != median
    directions = [
        "high" if flag and value > median else "low" if flag else None
        for flag, value in zip(flags, values, strict=True)
    ]
    method = "median_deviation_fallback" if bool(flags.any()) else "iqr"
    return AnomalyResult(
        status="completed",
        method=method,
        threshold=iqr_multiplier,
        median=median,
        mad=mad,
        is_anomaly=flags,
        direction=directions,
        scores=[None] * size,
        lower_bound=median,
        upper_bound=median,
    )
