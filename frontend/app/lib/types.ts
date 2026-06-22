export type ApiConnectionState = "connected" | "connecting" | "disconnected";
export type AnomalyType = "spike" | "drop";

export interface AnalyticsDataset {
  id: string;
  filename: string;
  dateStart: string;
  dateEnd: string;
  rowCount: number;
  createdAt?: string;
}

export interface AnalyticsMetrics {
  totalRevenue: number;
  cleanedRevenue: number;
  totalVisitorsRaw: number;
  totalVisitorsExcludingRevenueAnomalies: number;
  visitorsOnAnomalyRows: number;
  averageDailyVisitorsRaw: number;
  averageDailyVisitorsExcludingRevenueAnomalies: number;
  anomalyCount: number;
  anomalyRate: number;
}

export interface WeeklyTrendItem {
  weekStart: string;
  weekEnd: string;
  rawRevenue: number;
  cleanRevenue: number;
  averageDailyRevenue: number;
  cleanedAverageDailyRevenue: number;
  rawVisitors: number;
  visitorsExcludingRevenueAnomalies: number;
  anomalyCount: number;
}

export interface DailyRecordItem {
  date: string;
  totalRevenue: number;
  visitorCount: number;
  isAnomaly: boolean;
  anomalyDirection?: string | null;
}

export interface AnomalyItem {
  date: string;
  totalRevenue: number;
  visitorCount?: number;
  type: AnomalyType;
  method: string;
  lowerBound?: number;
  upperBound?: number;
  reason: string;
  status: "requires_review" | "reviewed";
  score?: number;
}

export interface AnalyticsSummary {
  dataset: AnalyticsDataset;
  metrics: AnalyticsMetrics;
  dailyRecords: DailyRecordItem[];
  weeklyTrend: WeeklyTrendItem[];
  anomalies: AnomalyItem[];
  dataQuality: {
    duplicateDatesMerged: number;
    imputedValueCount: number;
    warnings: string[];
  };
  forecastingReady: boolean;
}

export interface AnalyticsUploadResult {
  datasetId: string;
  filename: string;
  duplicate: boolean;
  status: string;
  totalRows: number;
  validRows: number;
  missingValueRows: number;
  anomalyCount: number;
  imputation?: { method: string; totalCells: number } | null;
  warnings: string[];
  createdAt?: string;
}

export interface RagContext {
  rank: number;
  id: string;
  content: string;
  score: number;
  source?: string;
  section?: string;
}

export interface RagQueryResult {
  answer: string | null;
  generationStatus: "completed" | "failed" | "skipped";
  contexts: RagContext[];
  warnings: string[];
}

export interface RagIngestResult {
  documentId: string;
  filename: string;
  status: string;
  duplicate: boolean;
  chunkCount?: number;
  createdAt?: string;
  message?: string;
}

export interface KnowledgeStatus {
  documentCount: number;
  lastDocument?: string;
  lastIngestionStatus?: string;
}

export type ChatIntent =
  | "sop_question"
  | "analytics_summary"
  | "analytics_anomaly"
  | "analytics_trend"
  | "combined"
  | "greeting"
  | "unsupported";

export interface ChatSource {
  type: "document" | "analytics";
  label: string;
  documentId?: string | null;
  datasetId?: string | null;
  filename?: string | null;
  heading?: string | null;
  chunkId?: string | null;
  relevanceScore?: number | null;
}

export interface ChatQueryRequest {
  message: string;
  datasetId?: string | null;
  documentIds?: string[] | null;
  conversationId?: string | null;
}

export interface ChatQueryResult {
  answer: string;
  intent: ChatIntent;
  toolsUsed: string[];
  sources: ChatSource[];
  conversationId?: string | null;
  warnings: string[];
}
