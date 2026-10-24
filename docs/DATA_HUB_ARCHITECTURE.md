# NUSA MATRA — DATA HUB SYSTEM ARCHITECTURE

**Document ID:** `NM-DH-05`  
**Target Platform:** Nusa Matra — Geographic Decision-Support System (WIA 2026)  
**Scope:** Medallion Data Pipeline, PostGIS Schema, Normalization Formulas & DEMO/LIVE Safeguards  

---

## 1. Arsitektur Berlapis (Four-Layer Separation of Concerns)

Arsitektur Data Hub dirancang untuk memisahkan secara tegas proses **Ingesti (Bronze)**, **Normalisasi & Penjembatanan Kode (Silver)**, **Gudang Snapshot Terverifikasi (Gold)**, dan **Layanan API Berkecepatan Tinggi (Serving)**.

```
+-----------------------------------------------------------------------------------+
|                        LAYER 1: INGESTION & RAW ARCHIVE (Bronze)                  |
|  [BPS API Connector]  [BNPB CKAN & Raster Zonal Job]  [Dapodik/SDI File Parsers]  |
|                                        |                                          |
|                                        v                                          |
|         MinIO / S3 Object Store: /raw/{agency}/{yyyy-mm-dd}/{sha256_payload}      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                   LAYER 2: NORMALIZATION & BRIDGING (Silver)                      |
|  - Code Cross-Walk Engine (Kemendagri 2025 <-> BPS MFD <-> Kemendikdasmen)        |
|  - Winsorized Normalization (0-100 Score) & National Percentile Ranking           |
|  - PostGIS Topology Simplification (Tier 1 TopoJSON & Tier 2 GeoJSON/MVT)         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                LAYER 3: VERSIONED SNAPSHOT WAREHOUSE (Gold - PostGIS)             |
|  - Immutable `data_snapshots` (e.g., `2026.10.0-wia-demo`, `2026.10.1-live`)      |
|  - `dim_regions`, `dim_indicators`, `dim_datasets`, `fact_indicator_values`       |
|  - Pre-computed Composite Domain Scores & Data Completeness Metrics               |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                     LAYER 4: API SERVING & SAFEGUARDS                             |
|  - FastAPI / Go REST Service (`/api/v1/...`) matching `docs/08-API-SPECIFICATION` |
|  - Redis + CDN Edge Caching (ETag / Immutable Snapshot Keys)                      |
|  - Mode Router (`X-Data-Mode: DEMO | LIVE` + Static Bundle Circuit Breaker)       |
+-----------------------------------------------------------------------------------+
```

---

## 2. Desain Skema Database (PostgreSQL 16 + PostGIS 3.4)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Registri Snapshot Immutable (Pengendali Mode DEMO vs LIVE)
CREATE TABLE data_snapshots (
    snapshot_id VARCHAR(64) PRIMARY KEY, -- contoh: '2026.10.0-wia-demo'
    label VARCHAR(120) NOT NULL,
    environment_tag VARCHAR(16) NOT NULL CHECK (environment_tag IN ('DEMO', 'LIVE', 'STAGING')),
    is_active_default BOOLEAN NOT NULL DEFAULT FALSE,
    boundary_version VARCHAR(64) NOT NULL, -- contoh: 'BIG-Kepmendagri-300.2.2-2430-2025'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    manifest_checksum CHAR(64) NOT NULL,
    notes TEXT
);

-- 2. Dimensi Wilayah Administrasi Kanonis (38 Provinsi + 514 Kab/Kota)
CREATE TABLE dim_regions (
    region_id CHAR(4) PRIMARY KEY,              -- '32' (Prov) atau '3201' (Kab/Kota kanonis)
    parent_region_id CHAR(2) REFERENCES dim_regions(region_id),
    level VARCHAR(16) NOT NULL CHECK (level IN ('provinsi', 'kabupaten', 'kota')),
    name VARCHAR(120) NOT NULL,                 -- 'Kabupaten Bogor'
    short_name VARCHAR(80) NOT NULL,            -- 'Bogor'
    kemendagri_code VARCHAR(8) NOT NULL UNIQUE, -- '32.01'
    bps_code VARCHAR(4) NOT NULL UNIQUE,        -- '3201'
    kemendikdasmen_code VARCHAR(8),             -- '020500'
    legacy_codes TEXT[] DEFAULT '{}',           -- Kode historis sebelum pemekaran
    island_group VARCHAR(40) NOT NULL,          -- 'Jawa', 'Sumatera', 'Papua', dll.
    area_km2 NUMERIC(12, 2),
    label_lat DOUBLE PRECISION NOT NULL,        -- ST_Y(ST_PointOnSurface(geom))
    label_lng DOUBLE PRECISION NOT NULL,        -- ST_X(ST_PointOnSurface(geom))
    bbox DOUBLE PRECISION[4] NOT NULL,          -- [minLng, minLat, maxLng, maxLat]
    geom_high GEOMETRY(MultiPolygon, 4326),     -- Poligon resolusi tinggi
    geom_low GEOMETRY(MultiPolygon, 4326),      -- Poligon hasil simplifikasi topologi
    boundary_version VARCHAR(64) NOT NULL
);

CREATE INDEX idx_dim_regions_parent ON dim_regions(parent_region_id);
CREATE INDEX idx_dim_regions_geom_low ON dim_regions USING GIST(geom_low);

-- 3. Registri Dataset Resmi & Provenance (Jejak Audit Sumber)
CREATE TABLE dim_datasets (
    dataset_id VARCHAR(64) PRIMARY KEY,
    agency_code VARCHAR(32) NOT NULL,           -- 'BPS', 'BNPB', 'BIG', 'KEMENDIKDASMEN', 'KEMENKES'
    agency_name VARCHAR(160) NOT NULL,
    dataset_title VARCHAR(255) NOT NULL,
    official_portal_url TEXT NOT NULL,
    api_or_download_url TEXT NOT NULL,
    access_method VARCHAR(32) NOT NULL,         -- 'REST_API', 'CKAN_API', 'ARCGIS_REST', 'BATCH_FILE'
    license_name VARCHAR(120) NOT NULL,
    update_frequency VARCHAR(64) NOT NULL,
    last_ingested_at TIMESTAMPTZ NOT NULL,
    raw_archive_uri TEXT NOT NULL,              -- Lokasi berkas asli di S3/MinIO
    raw_sha256 CHAR(64) NOT NULL                -- Checksum SHA-256 berkas asli
);

-- 4. Katalog Metadata Indikator
CREATE TABLE dim_indicators (
    indicator_id VARCHAR(64) PRIMARY KEY,       -- contoh: 'soc_poverty_rate'
    indicator_name VARCHAR(160) NOT NULL,
    category VARCHAR(40) NOT NULL CHECK (category IN (
        'disaster_risk', 'socioeconomic', 'education_access',
        'healthcare_access', 'infrastructure', 'data_reliability'
    )),
    unit VARCHAR(40) NOT NULL,
    polarity VARCHAR(16) NOT NULL CHECK (polarity IN ('positive', 'negative', 'neutral')),
    availability_status VARCHAR(16) NOT NULL CHECK (availability_status IN ('DIRECT', 'DERIVED', 'UNAVAILABLE')),
    primary_dataset_id VARCHAR(64) REFERENCES dim_datasets(dataset_id),
    derivation_formula TEXT,
    description TEXT NOT NULL,
    national_mean NUMERIC(14, 4),
    national_median NUMERIC(14, 4),
    national_min NUMERIC(14, 4),
    national_max NUMERIC(14, 4)
);

-- 5. Tabel Fakta Nilai Indikator per Wilayah & Snapshot
CREATE TABLE fact_indicator_values (
    snapshot_id VARCHAR(64) NOT NULL REFERENCES data_snapshots(snapshot_id),
    region_id CHAR(4) NOT NULL REFERENCES dim_regions(region_id),
    indicator_id VARCHAR(64) NOT NULL REFERENCES dim_indicators(indicator_id),
    reference_year SMALLINT NOT NULL,           -- Tahun observasi data (mis. 2025)
    raw_value NUMERIC(18, 4),                   -- Nilai asli sesuai satuan
    normalized_score NUMERIC(6, 2),             -- Skor ternormalisasi (0.00 - 100.00)
    national_percentile NUMERIC(5, 2),          -- Persentil nasional (0.00 - 100.00)
    national_rank SMALLINT,                     -- Peringkat nasional (1 - 514)
    quality_flag VARCHAR(24) NOT NULL DEFAULT 'VERIFIED'
        CHECK (quality_flag IN ('VERIFIED', 'DERIVED', 'IMPUTED_PROVINCE', 'MISSING')),
    dataset_id VARCHAR(64) NOT NULL REFERENCES dim_datasets(dataset_id),
    source_record_ref VARCHAR(120),             -- Referensi baris/variabel sumber
    PRIMARY KEY (snapshot_id, region_id, indicator_id)
);

CREATE INDEX idx_fact_snapshot_indicator ON fact_indicator_values(snapshot_id, indicator_id);
CREATE INDEX idx_fact_snapshot_region ON fact_indicator_values(snapshot_id, region_id);

-- 6. Tabel Karantina Baris Gagal Petakan (Audit Data Quality)
CREATE TABLE etl_quarantine_rows (
    quarantine_id BIGSERIAL PRIMARY KEY,
    dataset_id VARCHAR(64) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_region_code TEXT,
    raw_region_name TEXT,
    raw_payload JSONB NOT NULL,
    failure_reason TEXT NOT NULL
);
```

---

## 3. Metodologi Normalisasi & Perhitungan Skor Prioritas ($0 - 100$)

Agar berbagai indikator dengan satuan berbeda (persentase, skor IRBI, rasio dokter, rupiah pengeluaran) dapat digabungkan ke dalam **Indeks Prioritas Wilayah**, setiap indikator dinormalisasi ke skala $0 - 100$ di mana **skor mendekati $100$ selalu berarti tingkat kerentanan/kebutuhan intervensi yang lebih tinggi**:

1. **Min-Max Full-Range Scaling (`v2.2-minmax-full-range`):**
   Nilai mentah $x$ dinormalisasi terhadap $x_{\min}$ dan $x_{\max}$ dari seluruh observasi kanonik indikator pada snapshot yang sama. Implementasi saat ini tidak memakai Winsorized clipping $P_2 - P_{98}$; outlier tetap dipertahankan dan tercakup dalam digest snapshot.
2. **Penyelarasan Polaritas (Polarity Alignment):**
   * Untuk indikator **polaritas negatif** (mis. Kemiskinan, Stunting, Risiko Bencana — semakin tinggi angka asli berarti semakin rentan):
     $$S_{\text{vuln}} = \frac{x - x_{\min}}{x_{\max} - x_{\min}} \times 100$$
   * Untuk indikator **polaritas positif** (mis. IPM, Akses Air Layak, Harapan Lama Sekolah — semakin rendah angka asli berarti semakin rentan):
     $$S_{\text{vuln}} = \left(1 - \frac{x - x_{\min}}{x_{\max} - x_{\min}}\right) \times 100$$

---

## 4. Mekanisme Pengaman Mode `DEMO` vs `LIVE`

| Komponen Pengaman | Perilaku Mode `DEMO` (Default Showcase WIA 2026) | Perilaku Mode `LIVE` (Production Operational) |
| :--- | :--- | :--- |
| **Target Snapshot** | Terkunci pada snapshot *immutable* `2026.10.0-wia-demo` yang telah diaudit penuh. | Mengarah ke snapshot terbaru dengan `environment_tag = 'LIVE'` dan `is_active_default = TRUE`. |
| **Gerbang Promosi Data (Promotion Gate)** | Tidak dapat diubah oleh *cron job* otomatis; hanya dapat diperbarui melalui perintah CLI manual dengan verifikasi checksum. | Ingesti baru masuk ke `STAGING` terlebih dahulu. Hanya dipromosikan ke `LIVE` jika lulus uji otomatis: (1) 514 Kab/Kota lengkap, (2) 0 geometri rusak, (3) selisih nilai kosong $< 5\%$. |
| **Pemilihan Mode via API** | Aktif secara bawaan atau saat klien mengirim `?mode=demo` / header `X-Data-Mode: DEMO`. | Aktif saat klien mengirim `?mode=live` / header `X-Data-Mode: LIVE`. |
| **Static Bundle Circuit Breaker** | Jika database mengalami gangguan atau latensi $> 800\text{ ms}$, API otomatis menyajikan berkas JSON/TopoJSON statis yang telah dibekukan di memori/disk (`/snapshots/demo/`) dan menyertakan header `X-Data-Fallback: STATIC_DEMO_BUNDLE`. | Otomatis beralih (*failover*) ke snapshot `DEMO` apabila query `LIVE` mengalami kegagalan. |