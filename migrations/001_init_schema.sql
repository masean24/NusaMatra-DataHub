-- =============================================================================
-- Nusa Matra Data Hub — Initial Schema (SQLite MVP)
-- Adapted from DATA_HUB_ARCHITECTURE.md (NM-DH-05)
-- Includes fixes from REVIEW_AND_BLOCKERS.md:
--   - Blocker #6: reference_year added to fact_indicator_values PK
--   - Blocker #9: DEMO_EXAMPLE added as valid quality_flag
-- =============================================================================

-- 1. Registri Snapshot Immutable (Pengendali Mode DEMO vs LIVE)
CREATE TABLE IF NOT EXISTS data_snapshots (
    snapshot_id TEXT PRIMARY KEY,                        -- e.g. '2026.10.0-wia-demo'
    label TEXT NOT NULL,
    environment_tag TEXT NOT NULL
        CHECK (environment_tag IN ('DEMO', 'LIVE', 'STAGING')),
    is_active_default INTEGER NOT NULL DEFAULT 0,       -- SQLite boolean
    boundary_version TEXT NOT NULL,                     -- e.g. 'BIG-Kepmendagri-300.2.2-2430-2025'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    published_at TEXT,
    manifest_checksum TEXT NOT NULL,                    -- SHA-256
    notes TEXT
);

-- 2. Dimensi Wilayah Administrasi Kanonis (38 Provinsi + 514 Kab/Kota)
CREATE TABLE IF NOT EXISTS dim_regions (
    region_id TEXT PRIMARY KEY,                         -- '32' (Prov) or '3201' (Kab/Kota)
    parent_region_id TEXT,
    level TEXT NOT NULL
        CHECK (level IN ('provinsi', 'kabupaten', 'kota')),
    name TEXT NOT NULL,                                 -- 'Kabupaten Bogor'
    short_name TEXT NOT NULL,                           -- 'Bogor'
    kemendagri_code TEXT NOT NULL UNIQUE,               -- '32.01'
    bps_code TEXT NOT NULL UNIQUE,                      -- '3201'
    kemendikdasmen_code TEXT,                           -- '020500'
    island_group TEXT NOT NULL,                         -- 'Jawa', 'Sumatera', etc.
    area_km2 REAL,
    label_lat REAL NOT NULL,
    label_lng REAL NOT NULL,
    bbox_min_lng REAL,
    bbox_min_lat REAL,
    bbox_max_lng REAL,
    bbox_max_lat REAL,
    boundary_version TEXT NOT NULL,
    FOREIGN KEY (parent_region_id) REFERENCES dim_regions(region_id)
);

CREATE INDEX IF NOT EXISTS idx_dim_regions_parent ON dim_regions(parent_region_id);
CREATE INDEX IF NOT EXISTS idx_dim_regions_level ON dim_regions(level);

-- 3. Registri Dataset Resmi & Provenance
CREATE TABLE IF NOT EXISTS dim_datasets (
    dataset_id TEXT PRIMARY KEY,
    agency_code TEXT NOT NULL,                          -- 'BPS', 'BNPB', 'BIG', etc.
    agency_name TEXT NOT NULL,
    dataset_title TEXT NOT NULL,
    official_portal_url TEXT NOT NULL,
    api_or_download_url TEXT NOT NULL,
    access_method TEXT NOT NULL,                        -- 'REST_API', 'CKAN_API', etc.
    license_name TEXT NOT NULL,
    update_frequency TEXT NOT NULL,
    last_ingested_at TEXT NOT NULL,
    raw_archive_uri TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL                            -- SHA-256 checksum
);

-- 4. Katalog Metadata Indikator
CREATE TABLE IF NOT EXISTS dim_indicators (
    indicator_id TEXT PRIMARY KEY,                      -- e.g. 'soc_poverty_rate'
    indicator_name TEXT NOT NULL,
    category TEXT NOT NULL
        CHECK (category IN (
            'disaster_risk', 'socioeconomic', 'education_access',
            'healthcare_access', 'infrastructure', 'data_reliability'
        )),
    unit TEXT NOT NULL,
    polarity TEXT NOT NULL
        CHECK (polarity IN ('positive', 'negative', 'neutral')),
    availability_status TEXT NOT NULL
        CHECK (availability_status IN ('DIRECT', 'DERIVED', 'UNAVAILABLE')),
    primary_dataset_id TEXT REFERENCES dim_datasets(dataset_id),
    derivation_formula TEXT,
    description TEXT NOT NULL,
    national_mean REAL,
    national_median REAL,
    national_min REAL,
    national_max REAL
);

-- 5. Tabel Fakta Nilai Indikator per Wilayah & Snapshot
-- BLOCKER #6 FIX: reference_year included in PRIMARY KEY
CREATE TABLE IF NOT EXISTS fact_indicator_values (
    snapshot_id TEXT NOT NULL REFERENCES data_snapshots(snapshot_id),
    region_id TEXT NOT NULL REFERENCES dim_regions(region_id),
    indicator_id TEXT NOT NULL REFERENCES dim_indicators(indicator_id),
    reference_year INTEGER NOT NULL,                   -- e.g. 2025
    raw_value REAL,
    normalized_score REAL,                             -- 0.00 - 100.00
    national_percentile REAL,                          -- 0.00 - 100.00
    national_rank INTEGER,                             -- 1 - 514
    quality_flag TEXT NOT NULL DEFAULT 'DEMO_EXAMPLE'
        CHECK (quality_flag IN (
            'VERIFIED', 'DERIVED', 'IMPUTED_PROVINCE',
            'MISSING', 'DEMO_EXAMPLE'
        )),
    dataset_id TEXT NOT NULL REFERENCES dim_datasets(dataset_id),
    source_record_ref TEXT,
    PRIMARY KEY (snapshot_id, region_id, indicator_id, reference_year)
);

CREATE INDEX IF NOT EXISTS idx_fact_snapshot_indicator
    ON fact_indicator_values(snapshot_id, indicator_id);
CREATE INDEX IF NOT EXISTS idx_fact_snapshot_region
    ON fact_indicator_values(snapshot_id, region_id);

-- 6. Tabel Karantina Baris Gagal Petakan
CREATE TABLE IF NOT EXISTS etl_quarantine_rows (
    quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    raw_region_code TEXT,
    raw_region_name TEXT,
    raw_payload TEXT NOT NULL,                          -- JSON string
    failure_reason TEXT NOT NULL
);
