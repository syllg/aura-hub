# Aura Hub

Aura Hub adalah prototype backend service internal PT. XYZ untuk dua kebutuhan utama:

1. **Dynamic Document RAG Engine** — mengunggah, memproses, dan mencari informasi dari dokumen SOP retail berformat PDF, Markdown, atau TXT.
2. **Sales Insight & Anomaly Analytics** — memproses data transaksi harian, menangani missing value, mendeteksi anomali revenue, dan menyajikan ringkasan statistik serta tren mingguan.

Implementasi utama menggunakan **FastAPI**, **Qdrant**, **SQLite async**, dan **OpenAI**. Repositori juga menyediakan antarmuka **Next.js** sebagai fitur tambahan.

---

## Kesesuaian dengan Requirements

| Task | Requirement | Implementasi |
|---|---|---|
| Task 1 | `POST /api/v1/rag/ingest` | Upload PDF/Markdown/TXT, parsing, table-aware chunking, embedding, dan penyimpanan ke Qdrant |
| Task 1 | `POST /api/v1/rag/query` | Dense retrieval, lexical reranking, pengembalian Top-3 context beserta similarity score, dan jawaban dari LLM |
| Task 2 | `POST /api/v1/analytics/upload` | Validasi CSV, penggabungan tanggal duplikat, imputasi missing value, dan deteksi anomali revenue |
| Task 2 | `GET /api/v1/analytics/summary` | Total revenue, visitor metrics (raw & clean), tren mingguan, data harian, dan daftar tanggal anomali |
| Task 3 | Async FastAPI | Operasi I/O database, Qdrant, dan OpenAI menggunakan asynchronous implementation pada bagian yang sesuai |
| Task 3 | Struktur modular | Logic dipisahkan ke layer routes, services, repositories, schemas, dan core |
| Task 3 | Dependency file | Dependency backend tersedia pada `requirements.txt` |

---

## Arsitektur

```text
┌──────────────────┐
│ Client / Swagger │
└────────┬─────────┘
         ▼
┌──────────────────┐
│     FastAPI      │
│ Routes + Schemas │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Service / Core   │
│ RAG + Analytics  │
└───┬────────┬─────┘
    │        │
    ▼        ▼
┌────────┐ ┌──────────────┐
│ Qdrant │ │ SQLite async │
│ Vector │ │ Metadata     │
└────┬───┘ └──────────────┘
     │
     ▼
┌──────────────────┐
│ OpenAI API       │
│ Embedding + LLM  │
└──────────────────┘
```

### Komponen Utama

- **FastAPI** menangani endpoint, validasi request, response schema, dan lifecycle aplikasi.
- **Service layer** mengatur alur RAG dan analytics.
- **Core logic** berisi parsing, chunking, scoring, preprocessing, dan deteksi anomali.
- **SQLite async** menyimpan metadata dokumen, dataset, dan hasil pemrosesan.
- **Qdrant** menyimpan embedding beserta metadata chunk.
- **OpenAI** digunakan untuk embedding dan generation jawaban.

---

## Task 1 — RAG System

### Pipeline

```text
upload → parse → table-aware chunking → embed → store
query  → retrieve → rerank → select Top-3 → generate answer
```

### Strategi Chunking

Dokumen SOP dapat berisi heading, paragraf, daftar, dan tabel. Pemotongan hanya berdasarkan jumlah karakter berisiko memisahkan header tabel dari baris datanya sehingga aturan menjadi kehilangan konteks.

Implementasi menggunakan **hierarchical table-aware chunking**:

- Heading path dipertahankan sebagai metadata.
- Paragraf dan daftar dipotong berdasarkan batas ukuran chunk.
- Tabel Markdown dikenali sebagai unit khusus.
- Jika tabel terlalu besar, tabel dipecah per kelompok baris dan header diulang pada setiap chunk.

Strategi ini menjaga header, rentang aturan, dan nilai pada tabel tetap berada dalam konteks yang dapat dipahami saat retrieval.

### Retrieval dan Reranking

1. Pertanyaan diubah menjadi embedding.
2. Qdrant mengambil kandidat menggunakan dense vector search.
3. Kandidat direrank menggunakan dense score, lexical score, dan heading bonus.
4. Maksimal tiga context terbaik dikembalikan.
5. Context yang melewati minimum relevance threshold diteruskan ke LLM.

Formula reranking:

```text
final_score =
    0.75 × normalized_dense
  + 0.20 × normalized_lexical
  + 0.05 × heading_bonus
```

Keterangan score:

- `dense` adalah similarity score dari vector search Qdrant.
- `lexical` adalah kecocokan istilah antara pertanyaan dan chunk.
- `final` adalah skor akhir setelah reranking.

---

## Task 2 — Sales Analytics dan Deteksi Anomali

### Format CSV

Kolom wajib:

```text
date,total_revenue,visitor_count
```

### Preprocessing

- Memvalidasi format tanggal dan tipe numeric.
- Menolak revenue atau visitor count negatif.
- Menggabungkan tanggal duplikat dengan penjumlahan.
- Mengurutkan data berdasarkan tanggal.
- Mengisi missing numeric menggunakan linear interpolation, lalu median sebagai fallback.
- Menyimpan processing report agar perubahan data dapat diaudit.

### Metode Deteksi Anomali

Metode utama menggunakan **Modified Z-Score**:

```text
modified_z_score = 0.6745 × (revenue - median) / MAD
anomaly = abs(modified_z_score) > 3.5
```

Modified Z-Score dipilih karena median dan Median Absolute Deviation lebih tahan terhadap nilai ekstrem dibanding mean dan standard deviation pada Z-Score biasa.

Fallback:

1. **IQR fence 1.5** ketika `MAD == 0`.
2. **Median deviation fallback** ketika MAD dan IQR sama-sama nol, tetapi masih terdapat nilai yang berbeda dari median.
3. Dataset dengan kurang dari lima baris tetap disimpan dengan status `insufficient_data`.

Anomali tidak langsung dianggap sebagai data salah. Sistem menandainya sebagai `requires_review` agar dapat diverifikasi sebelum digunakan dalam forecasting.

### Visitor Metrics Audit

Deteksi anomali saat ini hanya dilakukan pada kolom `total_revenue`. Agar metrik visitor tidak ambigu, response summary memisahkan visitor menjadi tiga kategori:

- **`total_visitors_raw`** — jumlah visitor dari semua baris.
- **`total_visitors_excluding_revenue_anomalies`** — jumlah visitor dari baris yang revenue-nya tidak terdeteksi anomaly.
- **`visitors_on_anomaly_rows`** — selisih keduanya.

Terminologi UI menggunakan **"Clean Visitors"** untuk `total_visitors_excluding_revenue_anomalies` agar jelas bahwa ini adalah visitor pada baris yang revenue-nya lolos deteksi anomaly, bukan hasil deteksi anomaly pada visitor itu sendiri.

Contoh:

```json
{
  "total_visitors_raw": 2547,
  "total_visitors_excluding_revenue_anomalies": 1387,
  "visitors_on_anomaly_rows": 1160,
  "average_daily_visitors_raw": 181.93,
  "average_daily_visitors_excluding_revenue_anomalies": 126.09
}
```

---

## Tech Stack

| Layer | Teknologi |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy async |
| Vector database | Qdrant 1.12.1 |
| Metadata database | SQLite + aiosqlite |
| Embedding | OpenAI `text-embedding-3-small` |
| LLM | OpenAI `gpt-4o-mini` |
| Container | Docker, Docker Compose |
| UI tambahan | Next.js 15, React 19, TypeScript |

---

## Prerequisites

### Docker

- Docker
- Docker Compose
- OpenAI API key

### Local Development

- Python 3.11+
- Docker untuk Qdrant, atau Qdrant local mode
- Node.js 20+ hanya jika menjalankan frontend tambahan
- OpenAI API key

---

## Environment Setup

Salin file environment:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Isi konfigurasi minimal:

```dotenv
OPENAI_API_KEY=sk-...
```

Konfigurasi model default:

```dotenv
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

---

## Menjalankan Aplikasi

### Docker Compose

Jalankan seluruh service:

```bash
docker compose up --build -d
```

Periksa service:

```bash
docker compose ps
```

Lihat log:

```bash
docker compose logs -f
```

Hentikan service:

```bash
docker compose down
```

Reset database dan vector storage:

```bash
docker compose down -v
```

---
## Service URLs

### Docker Compose

| Service | URL |
|---|---|
| Swagger UI | http://localhost:8002/docs |
| OpenAPI JSON | http://localhost:8002/openapi.json |
| Health Live | http://localhost:8002/health/live |
| Health Ready | http://localhost:8002/health/ready |
| Qdrant Dashboard | http://localhost:6335/dashboard |
| Frontend | http://localhost:3000 |


### Alamat Qdrant

| Sumber koneksi | Alamat |
|---|---|
| Backend dari host | `http://localhost:6335` |
| Backend dalam Docker network | `http://qdrant:6333` |

---

## Contoh Request dan Response API

Seluruh endpoint dapat diuji melalui Swagger UI. Contoh berikut menggunakan port `8002` untuk Docker Compose.

### Health Check

```bash
curl http://localhost:8002/health/live
curl http://localhost:8002/health/ready
```

### 1. Ingest SOP

```bash
curl -X POST http://localhost:8002/api/v1/rag/ingest \
  -F "file=@mock_data/SOP_Operational.md;type=text/markdown"
```

Response:

```json
{
  "document_id": "dda07b35-b1f1-4015-b8bb-b613e877a72d",
  "filename": "SOP_Operational.md",
  "checksum_sha256": "4cd4b4f3334315c7258ecf65fde6601e347a81fb5c1b48f5ca6495081cb14a86",
  "status": "completed",
  "duplicate": false,
  "chunk_count": 3,
  "chunk_type_counts": {
    "paragraph": 2,
    "table": 1,
    "list": 0
  },
  "detected_document_version": "1.0.0",
  "processing": {
    "pages_extracted": 1,
    "characters_extracted": 699,
    "embedding_model": "text-embedding-3-small",
    "duration_ms": 3256
  },
  "created_at": "2026-06-22T02:12:47.259661Z"
}
```

### 2. Query SOP

```bash
curl -X POST http://localhost:8002/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Bagaimana sistem bonus untuk SPG di PT.XYZ?","top_k":3}'
```

Response:

```json
{
  "question": "Bagaimana sistem bonus untuk SPG PT.XYZ?",
  "answer": "Sistem bonus untuk SPG di PT. XYZ dihitung berdasarkan persentase pencapaian target sales harian. Berikut adalah rincian skema insentif finansial harian:\n\n- Jika pencapaian target kurang dari 80%, bonus yang diberikan adalah Rp 0 dengan status evaluasi \"Underperform\".\n\n- Jika pencapaian target antara 80% hingga 100%, bonus yang diberikan adalah Rp 50.000 dengan status evaluasi \"Target Met\".\n\n- Jika pencapaian target lebih dari 100%, bonus yang diberikan adalah Rp 150.000 dengan status evaluasi \"Superb\".",
  "generation_status": "completed",
  "contexts": [
    {
      "rank": 1,
      "chunk_id": "88f767a4-7927-5b51-afed-37ec78861749",
      "document_id": "dda07b35-b1f1-4015-b8bb-b613e877a72d",
      "content": "Insentif dihitung berdasarkan persentase pencapaian target sales harian:\n\n| Target Achieved | Bonus SPG  | Status Evaluasi |\n|-----------------|------------|-----------------|\n| < 80%           | Rp 0       | Underperform    |\n| 80% - 100%      | Rp 50.000  | Target Met      |\n| > 100%          | Rp 150.000 | Superb          |",
      "metadata": {
        "filename": "SOP_Operational.md",
        "chunk_type": "table",
        "heading_path": [
          "KETENTUAN OPERASIONAL PT. XYZ",
          "Skema Insentif Finansial Harian"
        ],
        "document_version": "1.0.0",
        "page_start": null,
        "page_end": null
      },
      "scores": {
        "dense": 0.56596,
        "lexical": 1,
        "heading_bonus": 1,
        "final": 1
      },
      "meets_minimum_score": true,
      "used_for_generation": true
    },
    {
      "rank": 2,
      "chunk_id": "8460d03d-c60f-5860-9653-21de1523e2e5",
      "document_id": "dda07b35-b1f1-4015-b8bb-b613e877a72d",
      "content": "Semua SPG wajib melakukan absensi wajah pada kamera CCTV pintar di outlet tepat pukul 08.00 WIB sebelum toko dibuka. Setiap keterlambatan lebih dari 15 menit tanpa alasan darurat akan dikenakan pinalti pemotongan performa sebesar 5 poin KPI.",
      "metadata": {
        "filename": "SOP_Operational.md",
        "chunk_type": "paragraph",
        "heading_path": [
          "KETENTUAN OPERASIONAL PT. XYZ",
          "Prosedur Absensi SPG"
        ],
        "document_version": "1.0.0",
        "page_start": null,
        "page_end": null
      },
      "scores": {
        "dense": 0.554784,
        "lexical": 0.174464,
        "heading_bonus": 1,
        "final": 0.754008
      },
      "meets_minimum_score": true,
      "used_for_generation": true
    },
    {
      "rank": 3,
      "chunk_id": "7968d528-3feb-5c7b-b294-d14bff857e63",
      "document_id": "dda07b35-b1f1-4015-b8bb-b613e877a72d",
      "content": "*Versi Dokumen: 1.0.0 (Juni 2026)*",
      "metadata": {
        "filename": "SOP_Operational.md",
        "chunk_type": "paragraph",
        "heading_path": [
          "KETENTUAN OPERASIONAL PT. XYZ"
        ],
        "document_version": "1.0.0",
        "page_start": null,
        "page_end": null
      },
      "scores": {
        "dense": 0.462329,
        "lexical": 0,
        "heading_bonus": 1,
        "final": 0.05
      },
      "meets_minimum_score": false,
      "used_for_generation": false
    }
  ],
  "retrieval": {
    "candidate_count": 3,
    "returned_count": 3,
    "generation_context_count": 2,
    "embedding_model": "text-embedding-3-small",
    "strategy": "dense_retrieval_bm25_heading_rerank",
    "reranker": "dense_bm25_heading_v1",
    "score_weights": {
      "dense": 0.75,
      "lexical": 0.2,
      "heading_bonus": 0.05
    },
    "duration_ms": 911,
    "minimum_score_applied": 0.35
  },
  "generation": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "duration_ms": 3020
  },
  "warnings": []
}
```

### 3. Upload Sales CSV

```bash
curl -X POST http://localhost:8002/api/v1/analytics/upload \
  -F "file=@mock_data/sales_mock.csv;type=text/csv"
```

Response:

```json
{
  "dataset_id": "3d6f8239-1d1f-4e36-80af-94d7979cdb49",
  "filename": "sales_mock.csv",
  "checksum_sha256": "9f63c8d2144b9d6957f1ef65f5e27ef82ff620d546a556c6107484dd899b3d1e",
  "status": "completed",
  "duplicate": false,
  "date_range": {
    "start": "2026-06-01",
    "end": "2026-06-14"
  },
  "processing_report": {
    "rows_received": 14,
    "rows_processed": 14,
    "invalid_rows": 0,
    "duplicate_dates_merged": 0,
    "imputed_cells": {
      "total_revenue": 0,
      "visitor_count": 0
    },
    "extra_columns_ignored": [],
    "warnings": []
  },
  "anomaly_detection": {
    "status": "completed",
    "method": "modified_z_score",
    "threshold": 3.5,
    "median_revenue": 5125000,
    "mad_revenue": 200000,
    "anomaly_count": 3
  },
  "created_at": "2026-06-22T02:15:06.733111Z"
}
```

### 4. Analytics Summary

```bash
curl http://localhost:8002/api/v1/analytics/summary
```

Response:

```json
{
  "dataset": {
    "dataset_id": "3d6f8239-1d1f-4e36-80af-94d7979cdb49",
    "filename": "sales_mock.csv",
    "date_start": "2026-06-01",
    "date_end": "2026-06-14",
    "row_count": 14,
    "created_at": "2026-06-22T02:15:06.733111Z"
  },
  "metrics": {
    "total_revenue_raw": 103150000,
    "total_revenue_clean": 56050000,
    "revenue_excluded_as_anomaly": 47100000,
    "total_visitors_raw": 2547,
    "total_visitors_excluding_revenue_anomalies": 1387,
    "visitors_on_anomaly_rows": 1160,
    "average_daily_visitors_raw": 181.93,
    "average_daily_visitors_excluding_revenue_anomalies": 126.09,
    "average_daily_revenue_raw": 7367857.14,
    "average_daily_revenue_clean": 5095454.55,
    "anomaly_count": 3,
    "anomaly_rate": 0.214286
  },
  "daily_records": [
    {
      "date": "2026-06-01",
      "total_revenue": 5000000,
      "visitor_count": 120,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-02",
      "total_revenue": 5200000,
      "visitor_count": 125,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-03",
      "total_revenue": 25000000,
      "visitor_count": 600,
      "is_anomaly": true,
      "anomaly_direction": "high"
    },
    {
      "date": "2026-06-04",
      "total_revenue": 4800000,
      "visitor_count": 115,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-05",
      "total_revenue": 5100000,
      "visitor_count": 130,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-06",
      "total_revenue": 100000,
      "visitor_count": 10,
      "is_anomaly": true,
      "anomaly_direction": "low"
    },
    {
      "date": "2026-06-07",
      "total_revenue": 5300000,
      "visitor_count": 140,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-08",
      "total_revenue": 4900000,
      "visitor_count": 118,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-09",
      "total_revenue": 5050000,
      "visitor_count": 122,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-10",
      "total_revenue": 5150000,
      "visitor_count": 126,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-11",
      "total_revenue": 4850000,
      "visitor_count": 114,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-12",
      "total_revenue": 5300000,
      "visitor_count": 135,
      "is_anomaly": false,
      "anomaly_direction": null
    },
    {
      "date": "2026-06-13",
      "total_revenue": 22000000,
      "visitor_count": 550,
      "is_anomaly": true,
      "anomaly_direction": "high"
    },
    {
      "date": "2026-06-14",
      "total_revenue": 5400000,
      "visitor_count": 142,
      "is_anomaly": false,
      "anomaly_direction": null
    }
  ],
  "weekly_trend": [
    {
      "week_start": "2026-06-01",
      "week_end": "2026-06-07",
      "observed_days": 7,
      "clean_days": 5,
      "raw_revenue": 50500000,
      "clean_revenue": 25400000,
      "raw_average_daily_revenue": 7214285.71,
      "clean_average_daily_revenue": 5080000,
      "raw_visitors": 1240,
      "visitors_excluding_revenue_anomalies": 630,
      "anomaly_count": 2
    },
    {
      "week_start": "2026-06-08",
      "week_end": "2026-06-14",
      "observed_days": 7,
      "clean_days": 6,
      "raw_revenue": 52650000,
      "clean_revenue": 30650000,
      "raw_average_daily_revenue": 7521428.57,
      "clean_average_daily_revenue": 5108333.33,
      "raw_visitors": 1307,
      "visitors_excluding_revenue_anomalies": 757,
      "anomaly_count": 1
    }
  ],
  "anomalies": [
    {
      "date": "2026-06-03",
      "total_revenue": 25000000,
      "visitor_count": 600,
      "direction": "high",
      "method": "modified_z_score",
      "score": 67.028437,
      "lower_bound": 4087194.2179392143,
      "upper_bound": 6162805.782060786,
      "status": "requires_review"
    },
    {
      "date": "2026-06-06",
      "total_revenue": 100000,
      "visitor_count": 10,
      "direction": "low",
      "method": "modified_z_score",
      "score": -16.946813,
      "lower_bound": 4087194.2179392143,
      "upper_bound": 6162805.782060786,
      "status": "requires_review"
    },
    {
      "date": "2026-06-13",
      "total_revenue": 22000000,
      "visitor_count": 550,
      "direction": "high",
      "method": "modified_z_score",
      "score": 56.910938,
      "lower_bound": 4087194.2179392143,
      "upper_bound": 6162805.782060786,
      "status": "requires_review"
    }
  ],
  "data_quality": {
    "duplicate_dates_merged": 0,
    "imputed_value_count": 0,
    "warnings": []
  }
}
```

---

## Bootstrap dan Data Persistence

Saat API startup, aplikasi secara idempotent:

- Membuat direktori data jika belum tersedia.
- Membuat tabel SQLite melalui SQLAlchemy.
- Membuat atau memvalidasi collection Qdrant.

Bootstrap manual:

```bash
make bootstrap
```

atau:

```bash
python scripts/bootstrap.py
```

Named volume Docker:

- `aura_data` untuk SQLite dan data aplikasi.
- `qdrant_data` untuk vector storage Qdrant.

`docker compose down` tidak menghapus volume tersebut.

---

## Testing dan Code Quality

### Backend Test

```bash
python -m pytest
```

### Makefile Commands

### Makefile Commands Utama

| Command | Fungsi |
|---|---|
| `make install` | Install dependency backend |
| `make docker-up` | Menjalankan Docker Compose |
| `make docker-down` | Menghentikan Docker Compose |
| `make bootstrap` | Bootstrap database dan Qdrant |
---

## Additional Features — Improvisasi
Bagian ini berisi fitur yang tidak diwajibkan oleh `Instructions.md`. Seluruh requirement utama tetap dapat digunakan tanpa bergantung pada fitur-fitur berikut.

### 1. Next.js Dashboard

- UI untuk upload dokumen SOP dan CSV sales.
- Dashboard analytics untuk melihat metric, daily revenue, tren mingguan, dan anomali.
- Navigasi terpadu antara chat dan analytics.

<img width="1906" height="895" alt="demo_1-1" src="https://github.com/user-attachments/assets/d0f057af-810a-45dd-bc8c-898d1fa17eda" />

<img width="1911" height="906" alt="Screenshot 2026-06-21 231725" src="https://github.com/user-attachments/assets/9462de2b-2741-4583-aed7-81d97fbcd54e" />

### 2. AuraHub Assistant

Endpoint tambahan:

```text
POST /api/v1/assistant/query
```

Assistant menggabungkan akses ke RAG SOP dan Sales Analytics melalui intent router.

| Intent | Data yang digunakan |
|---|---|
| `sop_question` | Qdrant + RAG generation |
| `analytics_summary` | Ringkasan dataset terbaru dari SQLite |
| `analytics_anomaly` | Daftar anomali |
| `analytics_trend` | Tren mingguan |
| `combined` | RAG SOP dan analytics |

Contoh request:

```bash
curl -X POST http://localhost:8002/api/v1/assistant/query \
  -H "Content-Type: application/json" \
  -d '{"message":"Berapa total revenue?"}'
```

Contoh response:

```json
{
  "answer": "Total revenue adalah sebagai berikut:\n\n- **Total Revenue Raw**: 103,150,000\n- **Total Revenue Clean**: 56,050,000\n\nPerlu dicatat bahwa ada revenue yang dikecualikan sebagai anomali sebesar 47,100,000. Anomali memerlukan review lebih lanjut.",
  "intent": "analytics_summary",
  "tools_used": [
    "get_analytics_summary"
  ],
  "sources": [
    {
      "type": "analytics",
      "label": "sales_mock.csv",
      "dataset_id": "3d6f8239-1d1f-4e36-80af-94d7979cdb49",
      "filename": "sales_mock.csv"
    }
  ],
  "conversation_id": "53fb2207-fad3-4060-8100-a94f9de40837",
  "warnings": []
}
```

### 3. Multi-File Upload

Frontend dapat menerima beberapa file dan mengunggahnya secara sequential ke endpoint backend single-file. Desain ini menjaga kontrak API tetap sederhana.

### 4. Suggestion Chips

Chat menyediakan saran pertanyaan SOP dan analytics agar pengguna dapat memulai percakapan tanpa mengetik pertanyaan dari awal.

### 5. Data Quality Panel

Frontend menampilkan jumlah imputasi, tanggal duplikat yang digabung, dan warning preprocessing dari backend.

### 6. Forecasting Readiness Indicator

Dashboard menampilkan status `Ready` atau `Needs Review` berdasarkan anomali yang masih memerlukan verifikasi.

### 7. Interactive Charts

- Daily revenue chart dengan marker spike dan drop.
- Weekly trend chart untuk membandingkan raw revenue dan cleaned revenue.
- Tooltip detail pada setiap titik data.

### 8. Anomaly Bounds

Setiap record anomali menyertakan `lower_bound` dan `upper_bound` untuk membantu proses verifikasi.

### 9. Document Version Metadata

Payload chunk Qdrant menyertakan `document_version` untuk mendukung pengembangan versioning dokumen.

### 10. RAG Context Tracking

Response query menyertakan:

- `meets_minimum_score`.
- `used_for_generation`.
- `generation_context_count`.
- Status `skipped_no_relevant_context` ketika tidak ada context yang memenuhi threshold.
