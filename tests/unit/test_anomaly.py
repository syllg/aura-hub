import numpy as np

from app.domain.anomaly import detect_revenue_anomalies


def test_modified_z_score_is_primary_and_matches_fixture() -> None:
    values = np.array(
        [
            5_000_000,
            5_200_000,
            25_000_000,
            4_800_000,
            5_100_000,
            100_000,
            5_300_000,
            4_900_000,
            5_050_000,
            5_150_000,
            4_850_000,
            5_300_000,
            22_000_000,
            5_400_000,
        ]
    )

    result = detect_revenue_anomalies(values)

    assert result.method == "modified_z_score"
    assert result.median == 5_125_000
    assert result.mad == 200_000
    assert np.flatnonzero(result.is_anomaly).tolist() == [2, 5, 12]
    assert result.scores[2] == 67.0284375
    assert result.scores[5] == -16.9468125


def test_iqr_is_only_used_when_mad_is_zero() -> None:
    iqr_result = detect_revenue_anomalies(np.array([0, 0, 0, 0, 10, 10, 10]))

    assert iqr_result.mad == 0
    assert iqr_result.method == "iqr"

    result = detect_revenue_anomalies(np.array([10, 10, 10, 10, 100]))

    assert result.mad == 0
    assert result.method == "median_deviation_fallback"
    assert result.is_anomaly.tolist() == [False, False, False, False, True]


def test_small_dataset_is_stored_without_anomaly_flags() -> None:
    result = detect_revenue_anomalies(np.array([1, 100, 2, 3]), minimum_rows=5)

    assert result.status == "insufficient_data"
    assert not result.is_anomaly.any()
