# NUSA MATRA — DATA HUB IMPLEMENTATION ROADMAP

**Document ID:** `NM-DH-07`  
**Target Platform:** Nusa Matra — Geographic Decision-Support System (WIA 2026)  
**Scope:** Step-by-Step Execution Plan for Backend Engineering Agent  

---

## Tahap 1: Fondasi Geospasial & Tabel Bridging Kode Wilayah (Hari 1–3)
**Tujuan:** Membangun referensi tunggal 38 Provinsi dan 514 Kabupaten/Kota beserta poligon batas wilayah yang siap dirender di peta 3D.

1. **Penyediaan Infrastruktur Penyimpanan (`docker-compose.yml`):**
   * Jalankan kontainer **PostgreSQL 16 + PostGIS 3.4**, **Redis 7**, dan **MinIO** (penyimpanan objek lokal kompatibel S3 untuk arsip data mentah `nusa-matra-raw-archive`).
   * Eksekusi migrasi SQL awal (`migrations/001_init_schema.sql`) sesuai spesifikasi pada `DATA_HUB_ARCHITECTURE.md`.
2. **Pemuatan Master Kode Wilayah (`dim_regions`):**
   * Muat daftar 38 Provinsi dan 514 Kabupaten/Kota berdasarkan Kepmendagri No. 300.2.2-2430 Tahun 2025.
   * Gabungkan dengan tabel relasi **SIG-BPS Bridging Kode** (`kemendagri_code` $\leftrightarrow$ `bps_code`) serta tabel kode wilayah 6 digit **Kemendikdasmen**.
   * Isi kolom `legacy_codes` untuk 29 Kabupaten/Kota di wilayah pemekaran Papua agar data historis 2020–2022 tetap terpetakan dengan akurat.
   * **Gerbang Validasi 1:** Pastikan query `SELECT COUNT(*) FROM dim_regions WHERE level IN ('kabupaten', 'kota')` menghasilkan tepat **514 baris** dan `WHERE level = 'provinsi'` menghasilkan **38 baris** tanpa nilai `NULL` pada kode BPS maupun Kemendagri.
3. **Pemrosesan Geometri Batas Wilayah BIG:**
   * Impor layer *Batas Wilayah Administrasi Kabupaten/Kota* dari BIG ke PostGIS menggunakan `ogr2ogr`.
   * Hitung luas wilayah (`area_km2`), `bbox`, dan titik jangkar daratan `ST_PointOnSurface(geom)` (`label_lat`, `label_lng`).
   * Jalankan simplifikasi topologi (`mapshaper -simplify visvalingam 8% keep-shapes -o format=topojson`) untuk menghasilkan berkas `kabupaten_low.topojson` ($< 1,8\text{ MB}$) dan `provinsi_low.topojson`.

---

## Tahap 2: Pembangunan Konektor Ingesti Sumber Resmi (Hari 4–7)
**Tujuan:** Mengambil data dari API dan publikasi resmi pemerintah, menyimpan arsip mentah ber-checksum SHA-256, dan memuatnya ke tabel staging.

1. **Konektor A — BPS WebAPI (`etl/connectors/bps_client.py`):**
   * Gunakan `BPS_API_KEY` untuk menarik tabel kompilasi Kabupaten/Kota (`domain=0000`) mencakup Kemiskinan (`P0`, `P2`), IPM (`HDI`, `UHH`, `HLS`, `RLS`, `Pengeluaran`), Pengangguran (`TPT`), Air Minum Layak, Sanitasi Layak, Elektrifikasi, Akses Internet, dan Jalan Desa Podes.
   * Simpan respons JSON asli ke `/raw/bps/{yyyy-mm-dd}/{var_id}.json` dan catat hash SHA-256 ke `dim_datasets`.
2. **Konektor B — BNPB Satu Data CKAN & InaRISK (`etl/connectors/bnpb_client.py`):**
   * Tarik dataset *Indeks Risiko Bencana Indonesia (IRBI)* dan *Kompilasi Data Kejadian dan Dampak Bencana* (akumulasi 5 tahun terakhir) melalui CKAN API `https://data.bnpb.go.id/api/3/action/`.
   * Jalankan skrip *zonal statistics* (`rasterstats` / PostGIS Raster) terhadap layer `ImageServer` InaRISK (`INDEKS_BAHAYA_BANJIR`, `GEMPABUMI`, `TANAH_LONGSOR`) pada poligon `dim_regions.geom_high` untuk menghasilkan indeks rata-rata bahaya per Kabupaten/Kota.
3. **Konektor C — Kemendikdasmen & Kemenkes (`etl/connectors/sectoral_client.py`):**
   * Parsing berkas master *Statistik Persekolahan*, *Neraca Pendidikan Daerah (NPD)*, dan progres sinkronisasi *Dapodik* menggunakan jembatan `kemendikdasmen_code`.
   * Parsing tabel prevalensi stunting Kabupaten/Kota (*SKI/SSGI*) dan rasio fasilitas/tenaga kesehatan dari *Profil Kesehatan Indonesia* Kemenkes / `data.go.id`.

---

## Tahap 3: Normalisasi, Audit Kualitas & Pembekuan Snapshot `DEMO` (Hari 8–9)
**Tujuan:** Menghitung skor ternormalisasi, metrik keandalan data, dan mengunci snapshot deterministik untuk WIA 2026.

1. **Mesin Normalisasi & Peringkat (`etl/normalize/scorer.py`):**
   * Hitung nilai `normalized_score` ($0 - 100$ dengan *min-max full-range*, `v2.2-minmax-full-range`), `national_percentile`, dan `national_rank` ($1 - 514$) untuk seluruh indikator aktif.
   * Hitung indikator keandalan data `meta_indicator_completeness` dan `meta_freshness_lag_years` untuk setiap Kabupaten/Kota.
2. **Pembekuan Snapshot `2026.10.0-wia-demo`:**
   * Jalankan rangkaian pengujian integritas data (`pytest tests/data_integrity/`).
   * Ekspor seluruh respons utama snapshot `2026.10.0-wia-demo` ke dalam bundel JSON/TopoJSON statis di `/snapshots/2026.10.0-wia-demo/` sebagai cadangan *circuit breaker*.

---

## Tahap 4: Layanan API & Integrasi Kontrak Frontend (Hari 10–12)
**Tujuan:** Menyajikan endpoint `/api/v1` dengan waktu respons $< 50\text{ ms}$ dan ketahanan penuh terhadap kegagalan.

1. **Implementasi Server API (`app/main.py` — FastAPI + AsyncPG + Redis):**
   * Bangun seluruh endpoint yang didefinisikan pada `API_CONTRACT_DRAFT.md` (`/regions`, `/boundaries`, `/indicators`, `/datasets`, `/snapshots`, `/health`).
   * Terapkan middleware pemilih mode (`X-Data-Mode: DEMO | LIVE`) dan *fallback circuit breaker* otomatis ke bundel statis jika terjadi gangguan database.
2. **Pengujian Beban & Kepatuhan Kontrak:**
   * Ekspor skema OpenAPI 3.1 (`/api/v1/openapi.json`) dan pastikan kecocokan struktur JSON dengan `docs/08-API-SPECIFICATION.md` pada repositori frontend.
   * Uji beban (*load testing*) pada endpoint `/api/v1/boundaries/kabupaten` dan `/api/v1/indicators/{id}/values` untuk memastikan latensi p95 di bawah $50\text{ ms}$.