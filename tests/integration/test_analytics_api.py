from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_upload_summary_duplicate_and_latest_completed(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'analytics.db').as_posix()}",
    )
    app = create_app(settings)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
        assert live.json() == {"status": "ok"}
        assert ready.status_code == 200
        assert ready.json()["dependencies"]["database"] == "up"
        assert ready.json()["dependencies"]["qdrant"] == "up"

        source = Path("tests/fixtures/sales_mock.csv").read_bytes()
        upload = await client.post(
            "/api/v1/analytics/upload",
            files={"file": ("sales_mock.csv", source, "text/csv")},
        )
        assert upload.status_code == 201
        first = upload.json()
        assert first["anomaly_detection"]["method"] == "modified_z_score"
        assert first["anomaly_detection"]["anomaly_count"] == 3

        summary = await client.get("/api/v1/analytics/summary")
        assert summary.status_code == 200
        body = summary.json()
        assert body["metrics"]["total_revenue_raw"] == 103_150_000
        assert body["metrics"]["total_revenue_clean"] == 56_050_000
        assert [item["date"] for item in body["anomalies"]] == [
            "2026-06-03",
            "2026-06-06",
            "2026-06-13",
        ]
        assert body["weekly_trend"][0]["clean_revenue"] == 25_400_000
        assert body["weekly_trend"][1]["clean_revenue"] == 30_650_000
        assert all(a["status"] == "requires_review" for a in body["anomalies"])
        assert any(a["lower_bound"] is not None for a in body["anomalies"])
        assert any(a["upper_bound"] is not None for a in body["anomalies"])

        duplicate = await client.post(
            "/api/v1/analytics/upload",
            files={"file": ("copy.csv", source, "text/csv")},
        )
        assert duplicate.status_code == 200
        dup_body = duplicate.json()
        assert dup_body["dataset_id"] == first["dataset_id"]
        assert dup_body["duplicate"] is True
        assert dup_body["filename"] == first["filename"]
        assert dup_body["processing_report"] is not None
        assert dup_body["anomaly_detection"] is not None

        newer_csv = (
            b"date,total_revenue,visitor_count\n"
            b"2026-07-01,100,1\n"
            b"2026-07-02,100,1\n"
            b"2026-07-03,100,1\n"
            b"2026-07-04,100,1\n"
            b"2026-07-05,100,1\n"
        )
        newer = await client.post(
            "/api/v1/analytics/upload",
            files={"file": ("newer.csv", newer_csv, "text/csv")},
        )
        assert newer.status_code == 201
        latest = await client.get("/api/v1/analytics/summary")
        assert latest.json()["dataset"]["dataset_id"] == newer.json()["dataset_id"]


@pytest.mark.asyncio
async def test_negative_metric_returns_contract_error(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'negative.db').as_posix()}",
    )
    app = create_app(settings)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/v1/analytics/upload",
            files={
                "file": (
                    "negative.csv",
                    b"date,total_revenue,visitor_count\n2026-01-01,-10,2\n",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NEGATIVE_METRIC_VALUES"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_upload_with_missing_values_imputed(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'missing.db').as_posix()}",
    )
    app = create_app(settings)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        source = Path("tests/fixtures/sales_with_missing.csv").read_bytes()
        upload = await client.post(
            "/api/v1/analytics/upload",
            files={"file": ("sales_with_missing.csv", source, "text/csv")},
        )
        assert upload.status_code == 201
        body = upload.json()
        assert body["processing_report"]["imputed_cells"]["total_revenue"] > 0
        assert body["processing_report"]["imputed_cells"]["visitor_count"] > 0
        assert body["processing_report"]["invalid_rows"] == 0
        assert body["imputation"] is not None
        assert body["imputation"]["method"] == "linear_interpolation"
        total_cells = (
            body["processing_report"]["imputed_cells"]["total_revenue"]
            + body["processing_report"]["imputed_cells"]["visitor_count"]
        )
        assert body["imputation"]["total_cells"] == total_cells
        assert any("berhasil diimputasi" in w for w in body["processing_report"]["warnings"])

        summary = await client.get("/api/v1/analytics/summary")
        assert summary.status_code == 200
        s = summary.json()
        assert s["dataset"]["row_count"] == 14
        assert s["data_quality"]["imputed_value_count"] > 0
        assert len(s["daily_records"]) == 14
