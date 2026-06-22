import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import AnomalyTable, { AnomalyTypeBadge } from "@/app/components/data/AnomalyTable";
import type { AnomalyItem } from "@/app/lib/types";

const spikeItem: AnomalyItem = {
  date: "2026-06-03",
  totalRevenue: 25_000_000,
  visitorCount: 600,
  type: "spike",
  method: "Modified Z-Score",
  lowerBound: 5_000_000,
  upperBound: 15_000_000,
  reason: "Revenue berada jauh di atas pola harian.",
  status: "requires_review",
  score: 3.8,
};

const dropItem: AnomalyItem = {
  date: "2026-06-06",
  totalRevenue: 100_000,
  visitorCount: 10,
  type: "drop",
  method: "IQR",
  lowerBound: 500_000,
  upperBound: 5_000_000,
  reason: "Revenue berada jauh di bawah pola harian.",
  status: "requires_review",
};

describe("AnomalyTable spike rendering", () => {
  it("menampilkan badge spike dengan ikon trendUp", () => {
    render(<AnomalyTable items={[spikeItem]} />);
    expect(screen.getAllByText("Spike").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rp 25.000.000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("3 Juni 2026").length).toBeGreaterThan(0);
  });
});

describe("AnomalyTable drop rendering", () => {
  it("menampilkan badge drop dengan ikon trendDown", () => {
    render(<AnomalyTable items={[dropItem]} />);
    expect(screen.getAllByText("Drop").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rp 100.000").length).toBeGreaterThan(0);
  });
});

describe("AnomalyTypeBadge", () => {
  it("spike menggunakan tone warning", () => {
    render(<AnomalyTypeBadge type="spike" />);
    expect(screen.getAllByText(/Spike/i).length).toBeGreaterThan(0);
  });

  it("drop menggunakan tone danger", () => {
    render(<AnomalyTypeBadge type="drop" />);
    expect(screen.getAllByText(/Drop/i).length).toBeGreaterThan(0);
  });
});
