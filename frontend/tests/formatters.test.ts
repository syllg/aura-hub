import { describe, expect, it } from "vitest";
import { formatDate, formatRupiah } from "@/app/lib/formatters";

describe("formatters Indonesia", () => {
  it("memformat Rupiah tanpa desimal", () => {
    expect(formatRupiah(103_150_000)).toBe("Rp 103.150.000");
  });

  it("memformat tanggal dalam bahasa Indonesia", () => {
    expect(formatDate("2026-06-03")).toBe("3 Juni 2026");
  });
});
