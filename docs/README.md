# Dokumentasi Nusa Matra Data Hub

Mulai dari sini. Dokumen di folder ini dibagi menjadi **dokumen aktif** dan **arsip historis**.

## Dokumen aktif

### Arsitektur
- [Arsitektur Data Hub](architecture/DATA_HUB_ARCHITECTURE.md) — pipeline, layer, dan desain sistem.
- [Geografi & Kode Wilayah](architecture/GEOGRAPHY_AND_REGION_CODES.md) — batas administrasi dan crosswalk kode wilayah.
- [Snapshot Versioning](architecture/SNAPSHOT_VERSIONING.md) — snapshot immutable, digest, dan retensi.

### API
- [Spesifikasi API](api/API_SPECIFICATION.md) — kontrak endpoint `/api/v1`.

### Data
- [Katalog Dataset](data/DATASET_CATALOG.md) — daftar sumber data resmi dan status integrasi.
- [Sumber Data Pemerintah](data/GOVERNMENT_DATA_SOURCES.md) — portal, endpoint, dan lisensi.
- [Verifikasi Sumber Data](data/DATA_SOURCE_VERIFICATION.md) — audit ketersediaan dan risiko sumber.

### Frontend
- [Panduan Integrasi Frontend](frontend/FRONTEND_INTEGRATION.md) — kontrak API, snapshot, error envelope, dan perilaku data.
- [Handoff Data 2025](frontend/FRONTEND_HANDOFF_2025_REFRESH.md) — perubahan terbaru yang perlu diketahui FE.
- [Integrasi BMKG](frontend/BMKG_INTEGRATION.md) — feed gempa bumi.

### Keamanan
- [Security Plan](security/SECURITY_PLAN.md) — threat model, kontrol akses, dan batasan keamanan.

### Operasi
- [Telemetry & Persistence](operations/TELEMETRY_PERSISTENCE.md) — deployment, volume, dan penyimpanan telemetry.

### Testing
- [Production samples](testing/production_samples/) — contoh response production.
- [Staging / contract samples](testing/staging_samples/) — fixture kontrak API.

## Arsip

Laporan audit, smoke test, verification report, handoff lama, dan dokumen versi sebelumnya ada di [archive/](archive/). Dokumen arsip disimpan untuk jejak historis, bukan panduan utama.

## Dokumen di root

- `README.md` — gambaran proyek dan cara menjalankan.
