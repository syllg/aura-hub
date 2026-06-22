const rupiahFormatter = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("id-ID");
const percentFormatter = new Intl.NumberFormat("id-ID", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Jakarta",
});

export function formatRupiah(value: number): string {
  return rupiahFormatter.format(Number.isFinite(value) ? value : 0).replace(/\u00a0/g, " ");
}

export function formatCompactRupiah(value: number): string {
  if (Math.abs(value) >= 1_000_000_000) return `Rp ${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(value / 1_000_000_000)} M`;
  if (Math.abs(value) >= 1_000_000) return `Rp ${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(value / 1_000_000)} jt`;
  return formatRupiah(value);
}

export function formatNumber(value: number): string {
  return numberFormatter.format(Number.isFinite(value) ? value : 0);
}

export function formatPercent(value: number): string {
  return percentFormatter.format(Math.max(0, Math.min(1, value)));
}

export function formatDate(value?: string): string {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? "—" : dateFormatter.format(parsed);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
