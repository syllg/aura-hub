import { describe, expect, it } from "vitest";
import { normalizeAnalyticsSummary } from "@/app/lib/normalizers";

describe("analytics normalizer", () => {
  it("menormalkan kontrak backend ke bentuk internal", () => {
    const result = normalizeAnalyticsSummary({
      dataset: { dataset_id: "abc", filename: "sales.csv", date_start: "2026-06-01", date_end: "2026-06-14", row_count: 14 },
      metrics: { total_revenue_raw: 100, total_revenue_clean: 80, total_visitors: 50, anomaly_count: 1, anomaly_rate: 1 / 14 },
      weekly_trend: [{ week_start: "2026-06-01", week_end: "2026-06-07", raw_revenue: 100, clean_revenue: 80 }],
      anomalies: [{ date: "2026-06-03", total_revenue: 25, direction: "high", method: "modified_z_score" }],
      data_quality: { duplicate_dates_merged: 0, imputed_value_count: 0, warnings: [] },
    });
    expect(result.metrics.cleanedRevenue).toBe(80);
    expect(result.anomalies[0].type).toBe("spike");
    expect(result.forecastingReady).toBe(false);
  });
});
