"use client";

import { useMutation } from "@tanstack/react-query";
import { useState, useRef, useEffect } from "react";
import AppShell from "../components/layout/AppShell";
import FileDropzone, { validateFile } from "../components/upload/FileDropzone";
import Icon from "../components/Icon";
import StatusBadge from "../components/feedback/StatusBadge";
import { queryChat, ingestDocument } from "../lib/api-client";
import type { ChatQueryRequest, ChatQueryResult, RagIngestResult } from "../lib/types";

const SOP_SUGGESTIONS = [
  "Apa aturan bonus SPG?",
  "Jam berapa SPG harus absensi?",
  "Apa sanksi jika SPG terlambat?",
];

const SALES_SUGGESTIONS = [
  "Berapa total revenue dataset ini?",
  "Tanggal mana yang terdeteksi anomali?",
  "Bagaimana tren revenue mingguannya?",
];

const documentRule = { extensions: [".pdf", ".md", ".markdown", ".txt"], label: "PDF, Markdown, atau TXT", maxBytes: 10 * 1024 * 1024 };

const GREETING_MESSAGE: { id: string; isUser: boolean; data: ChatQueryResult } = {
  id: "greeting",
  isUser: false,
  data: {
    answer: "Halo! Saya AuraHub Assistant. Apa ada yang bisa saya bantu? Silakan ajukan pertanyaan terkait SOP outlet atau analisis data performa.",
    intent: "greeting",
    toolsUsed: [],
    sources: [],
    warnings: [],
  },
};

const INTENT_BADGES: Record<string, { label: string; tone: "info" | "success" | "warning" | "neutral" }> = {
  sop_question: { label: "SOP", tone: "info" },
  analytics_summary: { label: "Analytics", tone: "success" },
  analytics_anomaly: { label: "Analytics", tone: "warning" },
  analytics_trend: { label: "Analytics", tone: "success" },
  combined: { label: "SOP + Analytics", tone: "neutral" },
  greeting: { label: "AuraHub", tone: "info" },
  unsupported: { label: "Unsupported", tone: "neutral" },
};

function SourceDetail({ source }: { source: ChatQueryResult["sources"][0] }) {
  return (
    <div className="source-item">
      <span className={`source-type ${source.type}`}>{source.type === "document" ? "Dokumen" : "Analytics"}</span>
      <strong>{source.label}</strong>
      {source.filename ? <span>{source.filename}</span> : null}
      {source.heading ? <span>{source.heading}</span> : null}
      {source.relevanceScore ? <span>Relevance: {source.relevanceScore.toFixed(3)}</span> : null}
    </div>
  );
}

function cleanChunkTags(text: string): string {
  return text.replace(/\s*\[chunk:[^\]]+\]/g, "");
}

function ChatMessage({ message, isUser }: { message: ChatQueryResult; isUser: boolean }) {
  const [showSources, setShowSources] = useState(false);
  if (isUser) {
    return (
      <div className="user-question chat-bubble">
        <div>
          <small>Anda</small>
          <p>{message.answer}</p>
        </div>
      </div>
    );
  }
  const badge = INTENT_BADGES[message.intent] || INTENT_BADGES.unsupported;
  return (
    <div className="assistant-answer chat-bubble">
      <span className="assistant-icon"><Icon name="bot" size={24} /></span>
      <div className="answer-content">
        <small>AuraHub Assistant</small>
        <p>{cleanChunkTags(message.answer)}</p>
        <div className="chat-meta">
          <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
          {message.toolsUsed.length > 0 ? <span className="tools-used">{message.toolsUsed.join(", ")}</span> : null}
        </div>
        {message.warnings.length > 0 ? (
          <div className="chat-warnings">
            {message.warnings.map((w, i) => (
              <p key={i}><Icon name="alert" size={14} /> {w}</p>
            ))}
          </div>
        ) : null}
        {message.sources.length > 0 ? (
          <details className="source-details" open={showSources} onToggle={(e) => setShowSources((e.target as HTMLDetailsElement).open)}>
            <summary>Lihat sumber</summary>
            <div className="source-list">
              {message.sources.map((s, i) => <SourceDetail key={i} source={s} />)}
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}

function useInMemoryHistory<T>() {
  const [history, setHistory] = useState<T[]>([]);
  function append(items: T[]) {
    setHistory((prev) => [...prev, ...items].slice(-20));
  }
  function clear() {
    setHistory([]);
  }
  return { history, append, clear };
}

function SopUploadPanel() {
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [phase, setPhase] = useState<"empty" | "uploading" | "success" | "failed">("empty");
  const [results, setResults] = useState<RagIngestResult[]>([]);
  const { history, append } = useInMemoryHistory<{ filename: string; date: string; status: string }>();
  const mutation = useMutation({
    mutationFn: async (fileList: File[]) => {
      const responses: RagIngestResult[] = [];
      for (const file of fileList) {
        const res = await ingestDocument(file);
        responses.push(res);
      }
      return responses;
    },
    onMutate: () => setPhase("uploading"),
    onSuccess: (data) => {
      setResults(data);
      setPhase("success");
      append(data.map((r) => ({ filename: r.filename, date: new Date().toISOString(), status: r.status })));
    },
    onError: (cause: Error) => {
      setErrors([cause.message]);
      setPhase("failed");
    },
  });

  function selectFiles(incoming: File[]) {
    const valid: File[] = [];
    const newErrors: string[] = [];
    incoming.forEach((f) => {
      const err = validateFile(f, documentRule);
      if (err) newErrors.push(`${f.name}: ${err}`);
      else valid.push(f);
    });
    if (valid.length) {
      setFiles((prev) => [...prev, ...valid]);
      setErrors([]);
    }
    if (newErrors.length) setErrors(newErrors);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function reset() { setFiles([]); setErrors([]); setResults([]); setPhase("empty"); mutation.reset(); }

  return (
    <section className="panel ingestion-panel" aria-labelledby="sop-ingestion-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Document ingestion</p>
          <h2 id="sop-ingestion-title">Upload SOP</h2>
        </div>
        <StatusBadge tone={phase === "success" ? "success" : phase === "failed" ? "danger" : phase === "uploading" ? "info" : "neutral"}>
          {phase === "empty" ? "Belum Ada File" : phase === "uploading" ? "Uploading" : phase === "success" ? "Indexed" : "Failed"}
        </StatusBadge>
      </div>
      <p className="panel-description">Upload dokumen SOP agar AuraHub Assistant dapat menjawab pertanyaan terkait kebijakan dan prosedur.</p>
      {phase === "success" && results.length > 0 ? (
        <div className="upload-success" role="status">
          <span className="success-mark"><Icon name="checkCircle" size={26} /></span>
          <div>
            <strong>{results.length} dokumen diproses</strong>
            <p>{results.filter((r) => !r.duplicate && r.status !== "failed").length} dokumen baru diindeks.</p>
          </div>
          <button className="button button-secondary" type="button" onClick={reset}>Upload Lain</button>
        </div>
      ) : (
        <>
          <FileDropzone files={files} rule={documentRule} onFiles={selectFiles} onRemove={removeFile} disabled={mutation.isPending} error={errors[0] ?? null} multiple />
          <div className="file-requirements">
            <span><Icon name="check" size={15} /> PDF, MD, TXT</span>
            <span><Icon name="check" size={15} /> Maks. 10 MB per file</span>
            <span><Icon name="check" size={15} /> Beberapa file</span>
          </div>
          {phase === "uploading" ? (
            <div className="progress-message" aria-live="polite">
              <Icon name="loader" className="spin" size={18} />
              <div>
                <strong>Mengunggah dokumen…</strong>
                <span>Jangan tutup halaman sampai proses selesai.</span>
              </div>
            </div>
          ) : null}
          <button className="button button-primary button-full" type="button" disabled={files.length === 0 || mutation.isPending} onClick={() => files.length > 0 && mutation.mutate(files)}>
            <Icon name="upload" size={18} />{mutation.isPending ? "Memproses…" : `Ingest ${files.length} Dokumen`}
          </button>
        </>
      )}
      {history.length > 0 && (
        <div className="upload-history" style={{ marginTop: 12 }}>
          <p className="eyebrow" style={{ marginBottom: 6 }}>Dokumen terupload</p>
          <ul className="upload-history-list">
            {history.slice().reverse().map((h, i) => (
              <li key={i} className="upload-history-item">
                <Icon name="file" size={14} />
                <span className="upload-history-name">{h.filename}</span>
                <StatusBadge tone={h.status === "Indexed" ? "success" : "neutral"}>{h.status}</StatusBadge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Array<{ id: string; isUser: boolean; data: ChatQueryResult }>>([GREETING_MESSAGE]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: (payload: ChatQueryRequest) => queryChat(payload),
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function send(text: string) {
    if (!text.trim() || mutation.isPending) return;
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), isUser: true, data: { answer: text, intent: "unsupported", toolsUsed: [], sources: [], warnings: [] } }]);
    mutation.mutate(
      { message: text.trim(), conversationId },
      {
        onSuccess: (data) => {
          if (data.conversationId) setConversationId(data.conversationId);
          setMessages((prev) => [...prev, { id: crypto.randomUUID(), isUser: false, data }]);
        },
        onError: (error) => {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              isUser: false,
              data: {
                answer: error instanceof Error ? error.message : "Terjadi kesalahan. Silakan coba lagi.",
                intent: "unsupported",
                toolsUsed: [],
                sources: [],
                warnings: ["AuraHub Assistant sedang tidak tersedia. Silakan coba kembali."],
              },
            },
          ]);
        },
      }
    );
    setInput("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  function startNewChat() {
    setMessages([GREETING_MESSAGE]);
    setConversationId(null);
  }

  return (
    <AppShell title="AuraHub Assistant" description="Tanya SOP dan data performa outlet.">
      <div className="chat-layout">
        <aside className="chat-upload-panel">
          <SopUploadPanel />
        </aside>
        <section className="chat-page" aria-label="AuraHub Assistant">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <span className="state-icon"><Icon name="bot" size={32} /></span>
              <div>
                <strong>Tanyakan sesuatu kepada AuraHub Assistant</strong>
                <div className="suggestion-chips">
                  {[...SOP_SUGGESTIONS, ...SALES_SUGGESTIONS].map((s) => (
                    <button key={s} type="button" className="suggestion-chip" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="chat-history" role="log" aria-live="polite" aria-label="Riwayat percakapan">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg.data} isUser={msg.isUser} />
              ))}
              {mutation.isPending ? (
                <div className="assistant-answer chat-bubble">
                  <span className="assistant-icon"><Icon name="bot" size={24} /></span>
                  <div className="answer-content">
                    <small>AuraHub Assistant</small>
                    <div className="ai-typing"><div><span><i /><i /><i /></span></div></div>
                  </div>
                </div>
              ) : null}
              <div ref={bottomRef} />
            </div>
          )}

          <div className="chat-input-bar">
            <div className="chat-input-wrap">
              <textarea
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Tulis pertanyaan..."
                disabled={mutation.isPending}
                aria-label="Pertanyaan"
              />
              <button
                type="button"
                className="send-button"
                disabled={!input.trim() || mutation.isPending}
                onClick={() => send(input)}
                aria-label="Kirim"
              >
                <Icon name="send" size={18} />
              </button>
            </div>
            <div className="chat-suggestions-bar">
              <span className="suggestions-label">Tanya cepat:</span>
              <div className="suggestion-chips-inline">
                {SOP_SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="suggestion-chip-small" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
                {SALES_SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="suggestion-chip-small sales" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
            {messages.length > 1 ? (
              <button type="button" className="button button-quiet new-chat-button" onClick={startNewChat}>
                <Icon name="trash" size={14} /> Percakapan Baru
              </button>
            ) : null}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
