import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import WeeklyTrendTable from "@/app/components/data/WeeklyTrendTable";
import type { WeeklyTrendItem } from "@/app/lib/types";

const items: WeeklyTrendItem[] = [
  { weekStart: "2026-06-01", weekEnd: "2026-06-07", rawRevenue: 50_500_000, cleanRevenue: 25_400_000, averageDailyRevenue: 7_214_286, cleanedAverageDailyRevenue: 3_628_571, rawVisitors: 1240, visitorsExcludingRevenueAnomalies: 630, anomalyCount: 2 },
  { weekStart: "2026-06-08", weekEnd: "2026-06-14", rawRevenue: 52_650_000, cleanRevenue: 30_650_000, averageDailyRevenue: 7_521_429, cleanedAverageDailyRevenue: 4_378_571, rawVisitors: 1307, visitorsExcludingRevenueAnomalies: 757, anomalyCount: 1 },
];

describe("WeeklyTrendTable", () => {
  it("menampilkan dua periode mingguan", () => {
    render(<WeeklyTrendTable items={items} />);
    expect(screen.getAllByText(/1 Juni 2026/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/7 Juni 2026/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rp 50.500.000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rp 52.650.000").length).toBeGreaterThan(0);
  });

  it("menampilkan jumlah anomali per periode", () => {
    render(<WeeklyTrendTable items={items} />);
    expect(screen.getAllByText(/2 terdeteksi|2 anomali/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/1 terdeteksi|1 anomali/).length).toBeGreaterThan(0);
  });
});
