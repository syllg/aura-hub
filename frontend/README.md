# Aura Hub Frontend

Dashboard internal Next.js + TypeScript untuk analytics penjualan dan SOP Knowledge Assistant PT. XYZ.

## Menjalankan lokal

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Buka `http://localhost:3000`. Default API adalah `http://localhost:8000`. Jika memakai `docker compose`, ubah `NEXT_PUBLIC_API_URL` menjadi `http://localhost:8002`.

Mock tidak aktif otomatis ketika backend gagal. Untuk demo eksplisit, set:

```dotenv
NEXT_PUBLIC_USE_MOCK_DATA=true
```

UI akan menampilkan badge `Demo Data` selama flag tersebut aktif.

## Route

- `/` — overview revenue, anomaly terbaru, forecasting readiness, dan status knowledge base.
- `/rag` — upload SOP (`PDF`, `Markdown`, `TXT`) dan chat dengan Top-3 retrieval context.
- `/analytics` — validasi/preview CSV, summary, chart, tren mingguan, review anomaly, dan readiness panel.
- `/knowledge` — redirect kompatibilitas ke `/rag`.

## Endpoint backend

- `POST /api/v1/rag/ingest`
- `POST /api/v1/rag/query`
- `POST /api/v1/analytics/upload`
- `GET /api/v1/analytics/summary`
- `GET /health/ready` untuk badge koneksi.

API client di `app/lib/api-client.ts` menangani timeout, abort, respons non-JSON, error standar backend, serta normalisasi variasi minor response.

## Validasi

```powershell
npm run lint
npm run type-check
npm test
npm run build
```
