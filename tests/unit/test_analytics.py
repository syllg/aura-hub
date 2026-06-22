from pathlib import Path

import pytest

from app.domain.analytics import AnalyticsDataError, process_analytics_csv


def process(path: Path):
    return process_analytics_csv(path, modified_z_threshold=3.5, iqr_multiplier=1.5, minimum_rows=5)


def test_sales_fixture_matches_contract() -> None:
    result = process(Path("tests/fixtures/sales_mock.csv"))

    assert result.total_revenue_raw == 103_150_000
    assert result.total_revenue_clean == 56_050_000
    assert result.total_visitors == 2_547
    assert [row.date.isoformat() for row in result.rows if row.is_anomaly] == [
        "2026-06-03",
        "2026-06-06",
        "2026-06-13",
    ]


def test_negative_values_are_rejected_not_imputed(tmp_path: Path) -> None:
    csv = tmp_path / "negative.csv"
    csv.write_text(
        "date,total_revenue,visitor_count\n2026-01-01,-1,10\n",
        encoding="utf-8",
    )

    with pytest.raises(AnalyticsDataError) as caught:
        process(csv)

    assert caught.value.code == "NEGATIVE_METRIC_VALUES"


def test_duplicate_dates_and_missing_values_are_processed(tmp_path: Path) -> None:
    csv = tmp_path / "quality.csv"
    csv.write_text(
        "date,total_revenue,visitor_count,ignored\n"
        "2026-01-01,100,10,x\n"
        "2026-01-01,200,20,x\n"
        "2026-01-02,,,x\n"
        "2026-01-03,500,40,x\n"
        "2026-01-04,600,50,x\n"
        "2026-01-05,700,60,x\n",
        encoding="utf-8",
    )

    result = process(csv)

    assert result.duplicate_dates_merged == 1
    assert result.imputed_cells == {"total_revenue": 1, "visitor_count": 1}
    assert result.rows[1].revenue_was_imputed is True
    assert result.rows[1].total_revenue == 400
    assert result.rows[1].visitor_count == 35
    assert result.extra_columns_ignored == ["ignored"]
