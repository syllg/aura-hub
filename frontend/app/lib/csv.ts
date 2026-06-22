import Papa from "papaparse";

export const REQUIRED_CSV_HEADERS = ["date", "total_revenue", "visitor_count"] as const;

export interface CsvPreview {
  headers: string[];
  rows: Record<string, string>[];
}

export function validateCsvHeaders(headers: string[]): { valid: boolean; missing: string[] } {
  const normalized = new Set(headers.map((header) => header.trim().toLowerCase()));
  const missing = REQUIRED_CSV_HEADERS.filter((header) => !normalized.has(header));
  return { valid: missing.length === 0, missing };
}

export function parseCsvPreview(file: File): Promise<CsvPreview> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      preview: 5,
      complete: (results) => {
        const headers = results.meta.fields ?? [];
        const validation = validateCsvHeaders(headers);
        if (!validation.valid) {
          reject(new Error(`Header CSV belum lengkap. Tambahkan: ${validation.missing.join(", ")}.`));
          return;
        }
        if (!results.data.length) {
          reject(new Error("CSV tidak memiliki baris data. Tambahkan minimal 1 transaksi."));
          return;
        }
        resolve({ headers, rows: results.data });
      },
      error: () => reject(new Error("CSV tidak dapat dibaca. Simpan ulang file sebagai CSV UTF-8 lalu coba lagi.")),
    });
  });
}
