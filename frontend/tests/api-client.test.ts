import { afterEach, describe, expect, it, vi } from "vitest";
import { queryRag, apiRequest } from "@/app/lib/api-client";

afterEach(() => vi.unstubAllGlobals());

describe("RAG API client", () => {
  it("menormalkan response query sukses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      answer: "SPG wajib absen pukul 08.00 WIB.",
      generation_status: "completed",
      contexts: [{ rank: 1, chunk_id: "chunk-1", content: "Absensi pukul 08.00 WIB", metadata: { filename: "SOP.md", heading_path: ["Absensi"] }, scores: { final: 0.92 } }],
    }), { status: 200, headers: { "Content-Type": "application/json" } })));

    const result = await queryRag("Jam berapa SPG absen?");
    expect(result.answer).toContain("08.00");
    expect(result.contexts[0]).toMatchObject({ source: "SOP.md", score: 0.92 });
  });

  it("menormalkan error backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "INVALID_QUESTION", message: "Pertanyaan tidak valid." } }), { status: 422 })));
    await expect(queryRag("bad")).rejects.toMatchObject({ code: "INVALID_QUESTION", message: "Pertanyaan tidak valid." });
  });

  it("mengembalikan top-3 context dari response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      answer: "Jawaban.",
      generation_status: "completed",
      contexts: [
        { rank: 1, chunk_id: "a", content: "Context 1", metadata: { filename: "A.md" }, scores: { final: 0.95 } },
        { rank: 2, chunk_id: "b", content: "Context 2", metadata: { filename: "A.md" }, scores: { final: 0.88 } },
        { rank: 3, chunk_id: "c", content: "Context 3", metadata: { filename: "A.md" }, scores: { final: 0.76 } },
      ],
    }), { status: 200 })));

    const result = await queryRag("test");
    expect(result.contexts).toHaveLength(3);
    expect(result.contexts[0].rank).toBe(1);
    expect(result.contexts[2].rank).toBe(3);
  });
});

describe("backend unavailable state", () => {
  it("melempar NETWORK_ERROR saat fetch gagal", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiRequest("/health/live")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
});
