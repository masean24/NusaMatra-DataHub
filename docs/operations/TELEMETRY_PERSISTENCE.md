# Telemetry Persistence di Coolify

## Kenapa angka statistik hilang saat redeploy?

Telemetry sebelumnya hanya in-memory. Container Coolify bersifat ephemeral: redeploy membuat container baru, memori lama hilang. SQLite bukan penyebabnya.

## Perubahan v2.2

Telemetry sekarang:

- Tetap mencatat request di memori (tanpa I/O per request).
- Menyimpan snapshot ke SQLite setiap `NM_TELEMETRY_FLUSH_INTERVAL_SECONDS` detik.
- Memuat snapshot saat startup.
- Menyimpan snapshot terakhir saat shutdown.
- Menyimpan `first_started_at`, sehingga uptime layanan tidak reset saat redeploy.

Field baru di `GET /api/v1/stats`:

| Field | Arti |
|---|---|
| `uptime_seconds` / `uptime_formatted` | Uptime layanan, persisten lintas redeploy |
| `service_uptime_seconds` / `service_uptime_formatted` | Sama dengan uptime layanan |
| `process_uptime_seconds` / `process_uptime_formatted` | Uptime proses/container saat ini |
| `first_started_at` | Waktu pertama layanan mulai (ISO 8601) |
| `persistence.enabled` | Apakah persistensi aktif |
| `persistence.last_flush_at` | Snapshot terakhir |
| `persistence.flush_interval_seconds` | Interval flush |

Counter yang persisten: `total_requests`, `status_codes`, `top_endpoints`, `modes`, total/min/max latency, dan `recent_requests`.

## Yang harus dilakukan di Coolify

### Opsi 1 — Persistent Storage UI (disarankan)

1. Buka aplikasi di Coolify.
2. **Persistent Storage** → Add.
3. Name: `nusa-matra-telemetry` (nama historis; sekarang menyimpan LIVE DB dan telemetry).
4. Mount path: `/data`.
5. Tambahkan environment:
   ```
   NM_LIVE_DATABASE_PATH=/data/nusa_matra_live.db
   NM_TELEMETRY_DB_PATH=/data/telemetry.db
   NM_TELEMETRY_FLUSH_INTERVAL_SECONDS=5
   NM_ENABLE_LIVE_MODE=true
   ```
6. **Sebelum redeploy pertama**, salin `nusa_matra_live.db` dari container lama ke volume ini. Lihat `../archive/reports/INDICATOR_RETIREMENT_V2_3.md` bagian one-time migration.
7. Redeploy.

### Opsi 2 — Docker Compose

`docker-compose.yml` sudah memuat:

```yaml
environment:
  - NM_LIVE_DATABASE_PATH=/data/nusa_matra_live.db
  - NM_TELEMETRY_DB_PATH=/data/telemetry.db
  - NM_TELEMETRY_FLUSH_INTERVAL_SECONDS=5
  - NM_ENABLE_LIVE_MODE=true
volumes:
  - nusa-matra-telemetry:/data
```

Pastikan Coolify memakai compose tersebut, lalu redeploy. Volume ini menyimpan
LIVE database **dan** telemetry.

> **Jangan mount volume ke `/app/data`.** Gunakan `/data`; `/app/data` berisi
> DEMO database dari image dan bisa menutupi file yang di-seed.

## Verifikasi

1. Buka `https://api.orangkeren.me/api/v1/stats`.
2. Pastikan:
   ```json
   "persistence": {
     "enabled": true,
     "initialized": true,
     "flush_interval_seconds": 5.0,
     "last_flush_at": "..."
   }
   ```
3. Catat `total_requests` dan `first_started_at`.
4. Redeploy.
5. Cek lagi: `total_requests` lanjut, `first_started_at` tetap, `process_uptime_seconds` reset.
6. Cek snapshot:
   ```http
   GET /api/v1/snapshots?mode=live
   ```
   Snapshot lama `2026.10.0-live-62354dfad392d985` harus tetap ada, dan snapshot
   baru 30 indikator harus menjadi `is_active_default`.
7. Pin snapshot lama:
   ```http
   GET /api/v1/indicators?mode=live&snapshot_id=2026.10.0-live-62354dfad392d985
   ```
   Harus `200` dengan 33 indikator.

## Batasan

- **Satu worker/replica.** SQLite aman untuk satu proses penulis. Jika Coolify menjalankan lebih dari satu worker/replica, gunakan Redis.
- **Kehilangan maksimal satu interval flush** jika container mati keras (`kill -9`). Default 5 detik.
- **Volume harus persisten.** Kalau volume dihapus, data telemetry hilang.
- Jangan mount volume ke `/app/data`; itu bisa menutupi database hasil seeder. Gunakan `/data`.

## Telemetry hygiene (v2.3)

- Hanya request pada prefix API bisnis eksplisit (`/api/v1/regions`, `/api/v1/indicators`, `/api/v1/boundaries`, `/api/v1/datasets`, `/api/v1/snapshots`, `/api/v1/earthquakes`) yang dihitung. Probe scanner seperti `/.gitmodules`, `/runtime.js`, `/api/v1/unknown`, dan `/api/v1/openapi.json` tidak masuk statistik.
- Filter tidak lagi bergantung pada `APIRoute.path_regex`. Di production, regex route hanya cocok untuk `/api/v1/openapi.json` sehingga seluruh request API nyata diam-diam dibuang dan counter tampak 0.
- Endpoint parameterized digabung memakai template route, misalnya `/api/v1/regions/{region_id}`, bukan ribuan ID berbeda.
- Semua waktu manusiawi memakai **Asia/Jakarta (WIB)**: `recent_requests[].time`, `first_started_at`, `last_flush_at`, dan `server_time`.
- Saat deploy versi ini, counter lama di-reset satu kali (`state_version` 1/2 → 3) untuk membuang data dari filter yang salah. `first_started_at` tetap dipertahankan; request setelah deploy akan mulai dihitung.
