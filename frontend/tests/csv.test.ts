import { describe, expect, it } from "vitest";
import { validateCsvHeaders } from "@/app/lib/csv";

describe("CSV validation", () => {
  it("menerima seluruh header wajib", () => {
    expect(validateCsvHeaders(["date", "total_revenue", "visitor_count"])).toEqual({ valid: true, missing: [] });
  });

  it("menjelaskan header yang hilang", () => {
    expect(validateCsvHeaders(["date", "total_revenue"]).missing).toEqual(["visitor_count"]);
  });
});
