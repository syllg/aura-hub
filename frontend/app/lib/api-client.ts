/* eslint-disable @typescript-eslint/no-explicit-any -- the API boundary intentionally accepts variant JSON contracts before normalization */

import {
  normalizeAnalyticsSummary,
  normalizeAnalyticsUpload,
  normalizeChatQuery,
  normalizeRagIngest,
  normalizeRagQuery,
} from "./normalizers";
import { mockAnalyticsSummary, mockRagAnswer } from "./mock-data";
import type {
  AnalyticsSummary,
  AnalyticsUploadResult,
  ChatQueryRequest,
  ChatQueryResult,
  RagIngestResult,
  RagQueryResult,
} from "./types";

export const USE_MOCK_DATA = (process.env.NEXT_PUBLIC_USE_MOCK_DATA || process.env.VITE_USE_MOCK_DATA) === "true";
const DEFAULT_TIMEOUT = 15_000;

/**
 * Pilih base URL API berdasarkan environment:
 * - Server-side (SSR / RSC): gunakan internal Docker URL agar tidak keluar container.
 * - Browser: gunakan public URL yang bisa diakses dari host.
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return (process.env.API_INTERNAL_URL || "http://api:8000").replace(/\/$/, "");
  }
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002").replace(/\/$/, "");
}

export class ApiError extends Error {
  status?: number;
  code?: string;
  requestId?: string;

  constructor(message: string, options: { status?: number; code?: string; requestId?: string } = {}) {
    super(message);
    this.name = "ApiError";
    Object.assign(this, options);
  }
}

async function parseResponse(response: Response): Promise<Record<string, any>> {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    if (!response.ok) throw new ApiError(`Server mengembalikan respons yang tidak dapat dibaca (${response.status}). Coba lagi atau periksa log API.`, { status: response.status });
    throw new ApiError("Respons API bukan JSON yang valid. Periksa konfigurasi backend.");
  }
}

export async function apiRequest(
  path: string,
  options: RequestInit & { timeoutMs?: number } = {},
): Promise<Record<string, any>> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort("timeout"), options.timeoutMs ?? DEFAULT_TIMEOUT);
  const onAbort = () => controller.abort("cancelled");
  options.signal?.addEventListener("abort", onAbort, { once: true });

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, { ...options, signal: controller.signal });
    const data = await parseResponse(response);
    if (!response.ok) {
      const error = data.error ?? data.detail ?? data;
      const message = typeof error === "string" ? error : error.message;
      throw new ApiError(message || `Permintaan gagal dengan status ${response.status}.`, {
        status: response.status,
        code: error.code,
        requestId: error.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
      });
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      if (options.signal?.aborted) throw error;
      throw new ApiError("Permintaan melewati batas waktu. Pastikan backend aktif lalu coba lagi.", { code: "REQUEST_TIMEOUT" });
    }
    throw new ApiError("Tidak dapat terhubung ke backend. Jalankan FastAPI dan periksa alamat API.", { code: "NETWORK_ERROR" });
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", onAbort);
  }
}

export async function checkApi(signal?: AbortSignal): Promise<boolean> {
  if (USE_MOCK_DATA) return true;
  await apiRequest("/health/ready", { signal, timeoutMs: 4_000 });
  return true;
}

export async function getAnalyticsSummary(signal?: AbortSignal, datasetId?: string): Promise<AnalyticsSummary> {
  if (USE_MOCK_DATA) return structuredClone(mockAnalyticsSummary);
  const query = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
  return normalizeAnalyticsSummary(await apiRequest(`/api/v1/analytics/summary${query}`, { signal }));
}

export async function uploadAnalytics(file: File): Promise<AnalyticsUploadResult> {
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => window.setTimeout(resolve, 450));
    return {
      datasetId: "demo-upload",
      filename: file.name,
      duplicate: false,
      status: "completed",
      totalRows: 14,
      validRows: 14,
      missingValueRows: 0,
      anomalyCount: 3,
      imputation: null,
      warnings: [],
      createdAt: new Date().toISOString(),
    };
  }
  const body = new FormData();
  body.append("file", file);
  return normalizeAnalyticsUpload(await apiRequest("/api/v1/analytics/upload", { method: "POST", body, timeoutMs: 30_000 }), file.name);
}

export async function ingestDocument(file: File): Promise<RagIngestResult> {
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    return { documentId: "demo-document", filename: file.name, status: "completed", duplicate: false, chunkCount: 3, createdAt: new Date().toISOString() };
  }
  const body = new FormData();
  body.append("file", file);
  return normalizeRagIngest(await apiRequest("/api/v1/rag/ingest", { method: "POST", body, timeoutMs: 45_000 }), file.name);
}

export async function queryRag(question: string, signal?: AbortSignal): Promise<RagQueryResult> {
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    return structuredClone(mockRagAnswer);
  }
  return normalizeRagQuery(await apiRequest("/api/v1/rag/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: 3, generate_answer: true }),
    signal,
    timeoutMs: 30_000,
  }));
}

export async function queryChat(payload: ChatQueryRequest, signal?: AbortSignal): Promise<ChatQueryResult> {
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    return {
      answer: `Ini jawaban mock untuk: ${payload.message}`,
      intent: "combined",
      toolsUsed: ["mock"],
      sources: [],
      warnings: [],
    };
  }
  return normalizeChatQuery(await apiRequest("/api/v1/assistant/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: payload.message,
      dataset_id: payload.datasetId,
      document_ids: payload.documentIds,
      conversation_id: payload.conversationId,
    }),
    signal,
    timeoutMs: 30_000,
  }));
}
