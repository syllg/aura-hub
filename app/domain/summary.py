from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any


def build_analytics_summary(dataset: Any) -> dict[str, Any]:
    rows = sorted(dataset.rows, key=lambda row: row.date)
    clean_rows = [row for row in rows if not row.is_anomaly]
    week_groups: dict[Any, list[Any]] = defaultdict(list)
    for row in rows:
        week_start = row.date - timedelta(days=row.date.weekday())
        week_groups[week_start].append(row)

    weekly_trend: list[dict[str, Any]] = []
    for week_start in sorted(week_groups):
        weekly_rows = week_groups[week_start]
        weekly_clean = [row for row in weekly_rows if not row.is_anomaly]
        raw_revenue = sum(row.total_revenue for row in weekly_rows)
        clean_revenue = sum(row.total_revenue for row in weekly_clean)
        raw_visitors = sum(row.visitor_count for row in weekly_rows)
        clean_visitors = sum(row.visitor_count for row in weekly_clean)
        weekly_trend.append(
            {
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
                "observed_days": len(weekly_rows),
                "clean_days": len(weekly_clean),
                "raw_revenue": raw_revenue,
                "clean_revenue": clean_revenue,
                "raw_average_daily_revenue": round(raw_revenue / len(weekly_rows), 2),
                "clean_average_daily_revenue": (
                    round(clean_revenue / len(weekly_clean), 2) if weekly_clean else 0.0
                ),
                "raw_visitors": raw_visitors,
                "visitors_excluding_revenue_anomalies": clean_visitors,
                "anomaly_count": sum(row.is_anomaly for row in weekly_rows),
            }
        )

    anomaly_rows = [row for row in rows if row.is_anomaly]
    total_visitors_raw = sum(row.visitor_count for row in rows)
    total_visitors_clean = sum(row.visitor_count for row in clean_rows)
    return {
        "dataset": {
            "dataset_id": dataset.id,
            "filename": dataset.filename,
            "date_start": dataset.date_min,
            "date_end": dataset.date_max,
            "row_count": dataset.row_count_processed,
            "created_at": dataset.created_at,
        },
        "metrics": {
            "total_revenue_raw": dataset.total_revenue_raw,
            "total_revenue_clean": dataset.total_revenue_clean,
            "revenue_excluded_as_anomaly": (
                dataset.total_revenue_raw - dataset.total_revenue_clean
            ),
            "total_visitors_raw": total_visitors_raw,
            "total_visitors_excluding_revenue_anomalies": total_visitors_clean,
            "visitors_on_anomaly_rows": total_visitors_raw - total_visitors_clean,
            "average_daily_visitors_raw": (
                round(total_visitors_raw / len(rows), 2) if rows else 0.0
            ),
            "average_daily_visitors_excluding_revenue_anomalies": (
                round(total_visitors_clean / len(clean_rows), 2) if clean_rows else 0.0
            ),
            "average_daily_revenue_raw": (
                round(dataset.total_revenue_raw / len(rows), 2) if rows else 0.0
            ),
            "average_daily_revenue_clean": (
                round(dataset.total_revenue_clean / len(clean_rows), 2) if clean_rows else 0.0
            ),
            "anomaly_count": dataset.anomaly_count,
            "anomaly_rate": (round(dataset.anomaly_count / len(rows), 6) if rows else 0.0),
        },
        "daily_records": [
            {
                "date": row.date,
                "total_revenue": row.total_revenue,
                "visitor_count": row.visitor_count,
                "is_anomaly": row.is_anomaly,
                "anomaly_direction": row.anomaly_direction if row.is_anomaly else None,
            }
            for row in rows
        ],
        "weekly_trend": weekly_trend,
        "anomalies": [
            {
                "date": row.date,
                "total_revenue": row.total_revenue,
                "visitor_count": row.visitor_count,
                "direction": row.anomaly_direction,
                "method": row.anomaly_method,
                "score": (round(row.anomaly_score, 6) if row.anomaly_score is not None else None),
                "lower_bound": row.lower_bound,
                "upper_bound": row.upper_bound,
                "status": "requires_review",
            }
            for row in anomaly_rows
        ],
        "data_quality": {
            "duplicate_dates_merged": dataset.duplicate_dates_merged,
            "imputed_value_count": dataset.imputed_value_count,
            "warnings": dataset.warnings_json,
        },
    }
