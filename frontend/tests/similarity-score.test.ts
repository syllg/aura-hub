import { describe, expect, it } from "vitest";
import { formatPercent } from "@/app/lib/formatters";

describe("similarity score formatting", () => {
  it("memformat score 0.9246 menjadi 92,46%", () => {
    expect(formatPercent(0.9246)).toBe("92,46%");
  });

  it("memformat score 0 menjadi 0,00%", () => {
    expect(formatPercent(0)).toBe("0,00%");
  });

  it("memformat score 1 menjadi 100,00%", () => {
    expect(formatPercent(1)).toBe("100,00%");
  });
});
