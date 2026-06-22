"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import AppShell from "../components/layout/AppShell";
import MetricCard from "../components/data/MetricCard";
import RevenueTrendChart from "../components/data/RevenueTrendChart";
import DailyRevenueChart from "../components/data/DailyRevenueChart";
import AnomalyTable from "../components/data/AnomalyTable";
import FileDropzone, { validateFile } from "../components/upload/FileDropzone";
import Icon from "../components/Icon";
import StatusBadge from "../components/feedback/StatusBadge";
import { EmptyState, ErrorState, LoadingSkeleton } from "../components/feedback/FeedbackStates";
import { ApiError, getAnalyticsSummary, uploadAnalytics } from "../lib/api-client";
import { parseCsvPreview, type CsvPreview } from "../lib/csv";
import { formatDate, formatNumber, formatRupiah } from "../lib/formatters";
import type { AnalyticsSummary } from "../lib/types";

const csvRule = { extensions: [".csv"], label: "CSV dengan header wajib", maxBytes: 10 * 1024 * 1024 };

function CsvUploadPanel({ onUploadSuccess }: { onUploadSuccess?: (datasetId: string) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const mutation = useMutation({
    mutationFn: uploadAnalytics,
    onSuccess: (result) => {
      onUploadSuccess?.(result.datasetId);
    },
  });

  async function selectFiles(incoming: File[]) {
    const candidate = incoming[0];
    if (!candidate) return;
    mutation.reset(); setPreview(null);
    const fileError = validateFile(candidate, csvRule);
    if (fileError) { setFiles([]); setValidationError(fileError); return; }
    setValidating(true); setValidationError(null);
    try {
      const result = await parseCsvPreview(candidate);
      setFiles([candidate]); setPreview(result);
    } catch (error) {
      setFiles([]); setValidationError(error instanceof Error ? error.message : "CSV tidak dapat divalidasi.");
    } finally { setValidating(false); }
  }

  function reset() { setFiles([]); setPreview(null); setValidationError(null); mutation.reset(); }
  const result = mutation.data;
  const file = files[0] ?? null;

  return (
    <section className="panel upload-panel" aria-labelledby="csv-upload-title">
      <div className="panel-heading"><div><p className="eyebrow">Dataset ingestion</p><h2 id="csv-upload-title">Upload CSV Penjualan</h2></div>{mutation.isSuccess ? <StatusBadge tone="success">Selesai</StatusBadge> : null}</div>
      <div className="upload-layout">
        <div>
          <p className="panel-description">Backend tetap menjadi sumber kebenaran untuk preprocessing dan deteksi anomali.</p>
          <FileDropzone files={files} rule={csvRule} onFiles={selectFiles} onRemove={reset} disabled={mutation.isPending || validating} error={validationError} />
          <div className="csv-requirements" aria-label="Kolom CSV wajib"><div><code>date</code><span>Tanggal transaksi</span></div><div><code>total_revenue</code><span>Revenue harian berupa angka</span></div><div><code>visitor_count</code><span>Jumlah pengunjung berupa angka</span></div></div>
          {validating ? <p className="progress-inline" aria-live="polite"><Icon name="loader" className="spin" size={17} /> Memvalidasi header dan baris CSV…</p> : null}
          {mutation.isError ? <p className="field-error" role="alert"><Icon name="alert" size={16} /> {mutation.error.message} Perbaiki file atau periksa backend lalu coba lagi.</p> : null}
          {!mutation.isSuccess ? <button className="button button-primary button-full" type="button" disabled={!file || !preview || mutation.isPending} onClick={() => file && mutation.mutate(file)}><Icon name={mutation.isPending ? "loader" : "upload"} className={mutation.isPending ? "spin" : ""} size={18} />{mutation.isPending ? "Mengunggah & Menganalisis…" : "Upload & Analisis CSV"}</button> : null}
        </div>

        <div className="csv-preview">
          {result ? (
            <div className="upload-result" role="status">
              <span className="success-mark"><Icon name="checkCircle" size={26} /></span>
              <div>
                <strong>{result.filename} berhasil diproses</strong>
                <p>{result.duplicate ? "Dataset ini sudah pernah diupload sebelumnya. Menampilkan data yang tersimpan." : "Analytics telah diperbarui dari hasil backend."}</p>
              </div>
              <dl>
                <div><dt>Total rows</dt><dd>{formatNumber(result.totalRows)}</dd></div>
                <div><dt>Valid rows</dt><dd>{formatNumber(result.validRows)}</dd></div>
                <div><dt>Missing value rows</dt><dd>{formatNumber(result.missingValueRows)}</dd></div>
                {result.imputation && result.imputation.totalCells > 0 ? (
                  <div><dt>Imputasi</dt><dd>{formatNumber(result.imputation.totalCells)} sel ({result.imputation.method})</dd></div>
                ) : null}
                <div><dt>Anomali</dt><dd>{formatNumber(result.anomalyCount)}</dd></div>
                <div><dt>Tanggal upload</dt><dd>{result.createdAt ? formatDate(result.createdAt) : formatDate(new Date().toISOString())}</dd></div>
              </dl>
              {result.warnings.length > 0 ? (
                <div className="upload-warnings">
                  {result.warnings.map((w, i) => (
                    <p key={i}><Icon name="alert" size={14} /> {w}</p>
                  ))}
                </div>
              ) : null}
              <div className="result-actions"><button className="button button-secondary" type="button" onClick={reset}>Upload Lagi</button><a className="button button-primary" href="#analytics-summary">Lihat Analytics</a></div>
            </div>
          ) : preview ? (
            <><div className="preview-heading"><div><strong>Preview Data</strong><span>Maksimal 5 baris pertama</span></div><StatusBadge tone="success">Header Valid</StatusBadge></div><div className="table-scroll compact-preview" tabIndex={0} aria-label="Preview CSV, dapat digulir horizontal"><table><thead><tr>{preview.headers.map((header) => <th scope="col" key={header}>{header}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.headers.map((header) => <td key={header}>{row[header] || "—"}</td>)}</tr>)}</tbody></table></div></>
          ) : <EmptyState title="Preview CSV" description="Pilih file untuk memeriksa header dan melihat maksimal 5 baris sebelum upload." icon="file" />}
        </div>
      </div>
    </section>
  );
}

export default function AnalyticsPage() {
  const [summaryData, setSummaryData] = useState<AnalyticsSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<Error | null>(null);

  async function handleUploadSuccess(datasetId: string) {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const controller = new AbortController();
      const data = await getAnalyticsSummary(controller.signal, datasetId);
      setSummaryData(data);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setSummaryData(null);
      } else {
        setSummaryError(error instanceof Error ? error : new Error(String(error)));
      }
    } finally {
      setSummaryLoading(false);
    }
  }

  const data = summaryData;

  return (
    <AppShell title="Sales Analytics" description="Validasi kualitas data, telaah anomali, dan nilai kesiapan forecasting.">
      <CsvUploadPanel onUploadSuccess={handleUploadSuccess} />

      {!data ? (
        <section id="analytics-summary" className="section-block" aria-labelledby="summary-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Analytics summary</p>
              <h2 id="summary-heading">Ringkasan Dataset</h2>
            </div>
          </div>
          {summaryLoading ? (
            <div className="metric-grid analytics-metrics">
              {Array.from({ length: 4 }, (_, index) => <LoadingSkeleton key={index} lines={3} className="metric-skeleton" />)}
            </div>
          ) : summaryError ? (
            <ErrorState message={summaryError.message} onRetry={() => {}} />
          ) : (
            <EmptyState title="Belum Ada Dataset Penjualan" description="Upload CSV di atas untuk menampilkan revenue, visitors, tren, dan hasil deteksi anomali." icon="analytics" />
          )}
        </section>
      ) : (
        <>
          <section id="analytics-summary" className="section-block" aria-labelledby="summary-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Analytics summary</p>
                <h2 id="summary-heading">Ringkasan Dataset</h2>
              </div>
              <span className="panel-meta">
                File: <strong>{data.dataset.filename}</strong> · Periode data: {formatDate(data.dataset.dateStart).replace(/ \d{4}$/, "")} – {formatDate(data.dataset.dateEnd)} · {data.dataset.rowCount} hari observasi
              </span>
            </div>

            <div className="metric-grid analytics-metrics">
              <MetricCard label="Total Revenue" value={formatRupiah(data.metrics.totalRevenue)} helper="Sebelum filtering anomali" icon="analytics" />
              <MetricCard label="Cleaned Revenue" value={formatRupiah(data.metrics.cleanedRevenue)} helper="Tanpa baris anomali" icon="checkCircle" tone="success" />
              <MetricCard label="Total Visitors" value={formatNumber(data.metrics.totalVisitorsRaw)} helper="Seluruh baris observasi" icon="users" />
              <MetricCard label="Clean Visitors" value={formatNumber(data.metrics.totalVisitorsExcludingRevenueAnomalies)} helper="Baris revenue lolos deteksi anomali" icon="users" tone="success" />
            </div>
            <div className="info-banner" style={{ marginTop: 12 }}>
              <Icon name="alert" size={18} />
              <p>
                Deteksi anomali dilakukan pada <strong>total_revenue</strong>. Jumlah &quot;Clean Visitors&quot;
                adalah visitor pada baris yang revenue-nya lolos deteksi anomali, bukan hasil deteksi
                anomaly pada visitor.
              </p>
            </div>
            {(data.dataQuality.imputedValueCount > 0 || data.dataQuality.duplicateDatesMerged > 0 || data.dataQuality.warnings.length > 0) ? (
              <div className="panel data-quality-panel" style={{ marginTop: 18, marginBottom: 18 }}>
                <div className="panel-heading">
                  <div><p className="eyebrow">Data quality</p><h2>Informasi Preprocessing</h2></div>
                  <StatusBadge tone={data.dataQuality.warnings.length ? "warning" : "info"}>{data.dataQuality.warnings.length ? "Perlu Perhatian" : "Clean"}</StatusBadge>
                </div>
                <div className="data-quality-grid">
                  {data.dataQuality.imputedValueCount > 0 ? (
                    <div className="data-quality-item">
                      <Icon name="alert" size={18} />
                      <div>
                        <strong>{formatNumber(data.dataQuality.imputedValueCount)} nilai diimputasi</strong>
                        <span>Missing value pada total_revenue atau visitor_count telah diisi dengan median.</span>
                      </div>
                    </div>
                  ) : null}
                  {data.dataQuality.duplicateDatesMerged > 0 ? (
                    <div className="data-quality-item">
                      <Icon name="checkCircle" size={18} />
                      <div>
                        <strong>{formatNumber(data.dataQuality.duplicateDatesMerged)} tanggal duplikat digabung</strong>
                        <span>Baris dengan tanggal sama telah diagregasi menjadi satu entri.</span>
                      </div>
                    </div>
                  ) : null}
                  {data.dataQuality.warnings.map((w, i) => (
                    <div className="data-quality-item" key={i}>
                      <Icon name="alert" size={18} />
                      <div><strong>Peringatan</strong><span>{w}</span></div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          <div className="analytics-grid">
            <section className="panel chart-panel daily-chart" aria-labelledby="daily-chart-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Daily trend</p>
                  <h2 id="daily-chart-heading">Revenue Harian</h2>
                </div>
              </div>
              <p className="panel-description">Revenue harian dengan anomaly yang ditandai</p>
              {data.dailyRecords.length ? (
                <DailyRevenueChart dailyRecords={data.dailyRecords} />
              ) : (
                <EmptyState title="Data Harian Belum Tersedia" description="Backend belum mengembalikan rekaman harian." icon="analytics" />
              )}
            </section>

            <aside className="panel readiness-panel" aria-labelledby="readiness-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Forecasting readiness</p>
                  <h2 id="readiness-heading">{data.forecastingReady ? "Ready" : "Needs Review"}</h2>
                </div>
                <span className={`forecast-icon ${data.forecastingReady ? "ready" : "review"}`}>
                  <Icon name={data.forecastingReady ? "checkCircle" : "alert"} size={24} />
                </span>
              </div>
              <p className="readiness-body">
                {data.forecastingReady
                  ? "Tidak ada anomali yang belum ditinjau. Dataset dapat diteruskan ke proses forecasting."
                  : `${data.metrics.anomalyCount} dari ${data.dataset.rowCount} data ditandai sebagai anomaly. Periksa data tersebut sebelum digunakan dalam pipeline forecasting.`}
              </p>
              {!data.forecastingReady && data.anomalies.length > 0 ? (
                <div className="readiness-dates">
                  <strong>Tanggal anomaly:</strong>
                  <ul>
                    {data.anomalies.map((a) => (
                      <li key={a.date}>{formatDate(a.date)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </aside>

            <section className="panel chart-panel weekly-chart" aria-labelledby="revenue-chart-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Weekly trend</p>
                  <h2 id="revenue-chart-heading">Revenue Trend Mingguan</h2>
                </div>
              </div>
              <p className="panel-description">Perbandingan raw dan cleaned revenue per minggu</p>
              {data.weeklyTrend.length ? (
                <RevenueTrendChart data={data.weeklyTrend} />
              ) : (
                <EmptyState title="Tren Belum Tersedia" description="Backend belum mengembalikan agregasi mingguan." icon="analytics" />
              )}
            </section>

            <section className="panel anomaly-table-panel" aria-labelledby="anomaly-table-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Review queue</p>
                  <h2 id="anomaly-table-heading">Anomaly Review</h2>
                </div>
                <StatusBadge tone={data.anomalies.length ? "warning" : "success"}>
                  {data.anomalies.length ? `${data.anomalies.length} Requires Review` : "Tidak Ada Anomali"}
                </StatusBadge>
              </div>
              <div className="info-banner">
                <Icon name="alert" size={18} />
                <p>Tanggal yang ditandai perlu diperiksa sebelum data digunakan untuk proses forecasting.</p>
              </div>
              {data.anomalies.length ? (
                <AnomalyTable items={data.anomalies} />
              ) : (
                <EmptyState title="Tidak Ada Anomali" description="Semua transaksi berada dalam pola yang diharapkan." icon="checkCircle" />
              )}
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
