/* eslint-disable @typescript-eslint/no-explicit-any -- normalizers intentionally accept minor backend response variations */

import type {
  AnalyticsSummary,
  AnalyticsUploadResult,
  ChatQueryResult,
  RagIngestResult,
  RagQueryResult,
} from "./types";

type JsonObject = Record<string, any>;
const asArray = (value: unknown): JsonObject[] => (Array.isArray(value) ? value : []);
const asNumber = (value: unknown, fallback = 0): number => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

export function normalizeAnalyticsSummary(payload: JsonObject): AnalyticsSummary {
  const dataset = payload.dataset ?? payload.data?.dataset ?? {};
  const metrics = payload.metrics ?? payload.summary ?? payload.data?.metrics ?? {};
  const trends = payload.weekly_trend ?? payload.weeklyTrend ?? payload.trends ?? [];
  const anomalies = payload.anomalies ?? payload.data?.anomalies ?? [];
  const quality = payload.data_quality ?? payload.dataQuality ?? {};
  const dailyRecords = payload.daily_records ?? payload.dailyRecords ?? [];

  const normalizedAnomalies = asArray(anomalies).map((item) => {
    const direction = item.direction ?? item.anomaly_type ?? item.type;
    const type = direction === "low" || direction === "drop" ? "drop" : "spike";
    return {
      date: String(item.date ?? ""),
      totalRevenue: asNumber(item.total_revenue ?? item.revenue),
      visitorCount: item.visitor_count == null ? undefined : asNumber(item.visitor_count),
      type,
      method: String(item.method ?? item.detection_method ?? "Modified Z-Score"),
      lowerBound: item.lower_bound == null ? undefined : asNumber(item.lower_bound),
      upperBound: item.upper_bound == null ? undefined : asNumber(item.upper_bound),
      reason: String(item.reason ?? (type === "spike" ? "Revenue berada jauh di atas pola harian." : "Revenue berada jauh di bawah pola harian.")),
      status: item.status === "reviewed" ? "reviewed" : "requires_review",
      score: item.score == null ? undefined : asNumber(item.score),
    } as const;
  });

  const anomalyCount = asNumber(metrics.anomaly_count ?? normalizedAnomalies.length);

  return {
    dataset: {
      id: String(dataset.dataset_id ?? dataset.id ?? "latest"),
      filename: String(dataset.filename ?? "Dataset penjualan"),
      dateStart: String(dataset.date_start ?? dataset.dateRange?.start ?? dataset.date_range?.start ?? ""),
      dateEnd: String(dataset.date_end ?? dataset.dateRange?.end ?? dataset.date_range?.end ?? ""),
      rowCount: asNumber(dataset.row_count ?? dataset.total_rows),
      createdAt: dataset.created_at,
    },
    metrics: {
      totalRevenue: asNumber(metrics.total_revenue_raw ?? metrics.total_revenue),
      cleanedRevenue: asNumber(metrics.total_revenue_clean ?? metrics.cleaned_total_revenue),
      totalVisitorsRaw: asNumber(
        metrics.total_visitors_raw ?? metrics.total_visitors ?? metrics.visitor_count,
      ),
      totalVisitorsExcludingRevenueAnomalies: asNumber(
        metrics.total_visitors_excluding_revenue_anomalies ?? metrics.total_visitors ?? metrics.visitor_count,
      ),
      visitorsOnAnomalyRows: asNumber(
        metrics.visitors_on_anomaly_rows ??
          (asNumber(metrics.total_visitors_raw ?? metrics.total_visitors) -
            asNumber(metrics.total_visitors_excluding_revenue_anomalies ?? metrics.total_visitors)),
      ),
      averageDailyVisitorsRaw: asNumber(
        metrics.average_daily_visitors_raw ??
          (dataset.row_count
            ? asNumber(metrics.total_visitors_raw ?? metrics.total_visitors) / asNumber(dataset.row_count)
            : 0),
      ),
      averageDailyVisitorsExcludingRevenueAnomalies: asNumber(
        metrics.average_daily_visitors_excluding_revenue_anomalies ??
          (asNumber(metrics.total_visitors_excluding_revenue_anomalies ?? metrics.total_visitors) /
            Math.max(1, asNumber(dataset.row_count) - anomalyCount)),
      ),
      anomalyCount,
      anomalyRate: asNumber(
        metrics.anomaly_rate,
        dataset.row_count ? anomalyCount / asNumber(dataset.row_count) : 0,
      ),
    },
    dailyRecords: asArray(dailyRecords).map((item) => ({
      date: String(item.date ?? ""),
      totalRevenue: asNumber(item.total_revenue ?? item.revenue),
      visitorCount: asNumber(item.visitor_count ?? item.visitorCount),
      isAnomaly: Boolean(item.is_anomaly ?? item.isAnomaly),
      anomalyDirection: item.anomaly_direction ?? item.anomalyDirection ?? null,
    })),
    weeklyTrend: asArray(trends).map((item) => ({
      weekStart: String(item.week_start ?? item.start ?? item.week ?? ""),
      weekEnd: String(item.week_end ?? item.end ?? item.week ?? ""),
      rawRevenue: asNumber(item.raw_revenue ?? item.total_revenue),
      cleanRevenue: asNumber(item.clean_revenue ?? item.cleaned_total_revenue),
      averageDailyRevenue: asNumber(
        item.raw_average_daily_revenue ?? item.average_daily_revenue,
      ),
      cleanedAverageDailyRevenue: asNumber(
        item.clean_average_daily_revenue ?? item.cleaned_average_daily_revenue,
      ),
      rawVisitors: asNumber(item.raw_visitors ?? item.total_visitors),
      visitorsExcludingRevenueAnomalies: asNumber(
        item.visitors_excluding_revenue_anomalies ?? item.total_visitors,
      ),
      anomalyCount: asNumber(item.anomaly_count),
    })),
    anomalies: normalizedAnomalies,
    dataQuality: {
      duplicateDatesMerged: asNumber(quality.duplicate_dates_merged),
      imputedValueCount: asNumber(quality.imputed_value_count),
      warnings: Array.isArray(quality.warnings) ? quality.warnings.map(String) : [],
    },
    forecastingReady: Boolean(payload.forecasting_ready ?? anomalyCount === 0),
  };
}

export function normalizeAnalyticsUpload(payload: JsonObject, fallbackName = "dataset.csv"): AnalyticsUploadResult {
  const report = payload.processing_report ?? payload.processing ?? {};
  const anomaly = payload.anomaly_detection ?? {};
  const imputed = report.imputed_cells ?? {};
  const imputation = payload.imputation ?? null;
  const warnings = Array.isArray(report.warnings) ? report.warnings.map(String) : [];
  return {
    datasetId: String(payload.dataset_id ?? payload.id ?? ""),
    filename: String(payload.filename ?? fallbackName),
    duplicate: Boolean(payload.duplicate),
    status: String(payload.status ?? "completed"),
    totalRows: asNumber(report.rows_received ?? report.total_rows),
    validRows: asNumber(report.rows_processed ?? report.valid_rows),
    missingValueRows: asNumber(report.missing_value_rows, asNumber(imputed.total_revenue) + asNumber(imputed.visitor_count)),
    anomalyCount: asNumber(anomaly.anomaly_count ?? payload.anomaly_count),
    imputation: imputation
      ? {
          method: String(imputation.method ?? "median"),
          totalCells: asNumber(imputation.total_cells),
        }
      : null,
    warnings,
    createdAt: payload.created_at,
  };
}

export function normalizeRagQuery(payload: JsonObject): RagQueryResult {
  const rawContexts = payload.contexts ?? payload.sources ?? payload.data?.contexts ?? [];
  const contexts = asArray(rawContexts).slice(0, 3).map((context, index) => {
    const metadata = context.metadata ?? {};
    const scores = context.scores ?? {};
    const heading = metadata.heading_path ?? context.heading_path;
    return {
      rank: asNumber(context.rank, index + 1),
      id: String(context.chunk_id ?? context.id ?? `context-${index + 1}`),
      content: String(context.content ?? context.text ?? ""),
      score: asNumber(scores.final ?? context.score ?? context.similarity_score),
      source: context.source ?? metadata.filename ?? context.filename,
      section: context.section ?? (Array.isArray(heading) ? heading.at(-1) : heading),
    };
  });
  return {
    answer: payload.answer == null ? null : String(payload.answer),
    generationStatus: payload.generation_status ?? (payload.answer ? "completed" : "failed"),
    contexts,
    warnings: Array.isArray(payload.warnings) ? payload.warnings.map(String) : [],
  };
}

export function normalizeRagIngest(payload: JsonObject, fallbackName = "Dokumen SOP"): RagIngestResult {
  return {
    documentId: String(payload.document_id ?? payload.id ?? ""),
    filename: String(payload.filename ?? fallbackName),
    status: String(payload.status ?? "completed"),
    duplicate: Boolean(payload.duplicate),
    chunkCount: payload.chunk_count == null ? undefined : asNumber(payload.chunk_count),
    createdAt: payload.created_at,
    message: payload.message,
  };
}

export function normalizeChatQuery(payload: JsonObject): ChatQueryResult {
  const rawSources = payload.sources ?? payload.contexts ?? [];
  const sources = asArray(rawSources).map((item) => ({
    type: String(item.type ?? "document") as "document" | "analytics",
    label: String(item.label ?? item.filename ?? "Sumber"),
    documentId: item.document_id ?? null,
    datasetId: item.dataset_id ?? null,
    filename: item.filename ?? null,
    heading: item.heading ?? null,
    chunkId: item.chunk_id ?? null,
    relevanceScore: item.relevance_score == null ? null : asNumber(item.relevance_score),
  }));
  return {
    answer: String(payload.answer ?? ""),
    intent: String(payload.intent ?? "unsupported") as ChatQueryResult["intent"],
    toolsUsed: Array.isArray(payload.tools_used) ? payload.tools_used.map(String) : [],
    sources,
    conversationId: payload.conversation_id ?? null,
    warnings: Array.isArray(payload.warnings) ? payload.warnings.map(String) : [],
  };
}
