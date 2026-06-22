import { describe, expect, it } from "vitest";
import { validateFile } from "@/app/components/upload/FileDropzone";

const rule = { extensions: [".csv"], label: "CSV", maxBytes: 1024 };

describe("invalid file upload", () => {
  it("menolak format yang tidak didukung", () => {
    const file = new File(["hello"], "sales.xlsx", { type: "application/vnd.ms-excel" });
    expect(validateFile(file, rule)).toContain("tidak didukung");
  });

  it("menolak file kosong", () => {
    expect(validateFile(new File([], "sales.csv"), rule)).toContain("File kosong");
  });
});
