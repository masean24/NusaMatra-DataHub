#!/usr/bin/env python3
"""
Nusa Matra Data Hub — DEMO Data Seeder

Generates deterministic DEMO fixture data for 38 provinces + 514 kab/kota
and seeds the SQLite database. Run from repo root:

    python data/seed_db.py

All generated data is labeled DEMO_EXAMPLE — not sourced from verified
LIVE measurements (Blocker #9).
"""

import csv
import os
import random
import sqlite3
import sys
from pathlib import Path

# Deterministic seed for reproducible DEMO data
random.seed(42)

# ─── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "nusa_matra_demo.db"
MIGRATION_PATH = REPO_ROOT / "migrations" / "001_init_schema.sql"
CSV_PATH = (
    REPO_ROOT / "data" / "INDICATOR_MAPPING.csv"
    if (REPO_ROOT / "data" / "INDICATOR_MAPPING.csv").exists()
    else REPO_ROOT / "INDICATOR_MAPPING.csv"
)

# ─── Province Master Data ─────────────────────────────────────────────────────
# (code, name, short_name, island_group, num_kab, num_kota, center_lat, center_lng)
# Total kab+kota must equal exactly 514.
PROVINCES = [
    ("11", "Aceh", "Aceh", "Sumatera", 18, 5, 4.695, 96.749),
    ("12", "Sumatera Utara", "Sumut", "Sumatera", 25, 8, 2.115, 99.545),
    ("13", "Sumatera Barat", "Sumbar", "Sumatera", 12, 7, -0.740, 100.800),
    ("14", "Riau", "Riau", "Sumatera", 10, 2, 1.547, 102.159),
    ("15", "Jambi", "Jambi", "Sumatera", 9, 2, -1.611, 103.613),
    ("16", "Sumatera Selatan", "Sumsel", "Sumatera", 13, 4, -3.319, 103.914),
    ("17", "Bengkulu", "Bengkulu", "Sumatera", 9, 1, -3.793, 102.260),
    ("18", "Lampung", "Lampung", "Sumatera", 13, 2, -4.559, 105.407),
    ("19", "Kepulauan Bangka Belitung", "Babel", "Sumatera", 6, 1, -2.741, 106.441),
    ("21", "Kepulauan Riau", "Kepri", "Sumatera", 5, 2, 3.946, 108.143),
    ("31", "DKI Jakarta", "Jakarta", "Jawa", 1, 5, -6.209, 106.846),
    ("32", "Jawa Barat", "Jabar", "Jawa", 18, 9, -6.889, 107.641),
    ("33", "Jawa Tengah", "Jateng", "Jawa", 29, 6, -7.151, 110.140),
    ("34", "DI Yogyakarta", "DIY", "Jawa", 4, 1, -7.797, 110.361),
    ("35", "Jawa Timur", "Jatim", "Jawa", 29, 9, -7.536, 112.238),
    ("36", "Banten", "Banten", "Jawa", 4, 4, -6.405, 106.064),
    ("51", "Bali", "Bali", "Bali & Nusa Tenggara", 8, 1, -8.450, 115.139),
    ("52", "Nusa Tenggara Barat", "NTB", "Bali & Nusa Tenggara", 8, 2, -8.653, 117.362),
    ("53", "Nusa Tenggara Timur", "NTT", "Bali & Nusa Tenggara", 21, 1, -8.657, 121.079),
    ("61", "Kalimantan Barat", "Kalbar", "Kalimantan", 12, 2, -0.279, 111.475),
    ("62", "Kalimantan Tengah", "Kalteng", "Kalimantan", 13, 1, -1.681, 113.382),
    ("63", "Kalimantan Selatan", "Kalsel", "Kalimantan", 11, 2, -3.093, 115.284),
    ("64", "Kalimantan Timur", "Kaltim", "Kalimantan", 7, 3, 1.694, 116.419),
    ("65", "Kalimantan Utara", "Kaltara", "Kalimantan", 4, 1, 3.073, 116.042),
    ("71", "Sulawesi Utara", "Sulut", "Sulawesi", 11, 4, 0.624, 124.892),
    ("72", "Sulawesi Tengah", "Sulteng", "Sulawesi", 12, 1, -1.431, 121.446),
    ("73", "Sulawesi Selatan", "Sulsel", "Sulawesi", 21, 3, -3.669, 119.974),
    ("74", "Sulawesi Tenggara", "Sultra", "Sulawesi", 15, 2, -4.145, 122.175),
    ("75", "Gorontalo", "Gorontalo", "Sulawesi", 5, 1, 0.544, 122.447),
    ("76", "Sulawesi Barat", "Sulbar", "Sulawesi", 6, 0, -2.844, 119.232),
    ("81", "Maluku", "Maluku", "Maluku", 9, 2, -3.238, 130.145),
    ("82", "Maluku Utara", "Malut", "Maluku", 8, 2, 1.571, 127.809),
    ("91", "Papua", "Papua", "Papua", 8, 1, -2.534, 140.718),
    ("92", "Papua Barat", "Papua Barat", "Papua", 6, 1, -1.336, 133.174),
    ("93", "Papua Selatan", "Papua Selatan", "Papua", 4, 0, -7.296, 140.019),
    ("94", "Papua Tengah", "Papua Tengah", "Papua", 8, 0, -3.589, 136.349),
    ("95", "Papua Pegunungan", "Papua Peg.", "Papua", 8, 0, -3.975, 138.951),
    ("96", "Papua Barat Daya", "Papua BD", "Papua", 5, 1, -1.052, 131.261),
]

BOUNDARY_VER = "BIG-Kepmendagri-300.2.2-2430-2025"
SNAPSHOT_ID = "2026.10.0-wia-demo"

# ─── Dataset Definitions ─────────────────────────────────────────────────────
DATASETS = [
    ("bps_kemiskinan_2025", "BPS", "Badan Pusat Statistik",
     "Data Kemiskinan Kabupaten/Kota 2025 (Susenas Maret)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/kemiskinan/key/DEMO/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_ipm_2025", "BPS", "Badan Pusat Statistik",
     "Indeks Pembangunan Manusia Kabupaten/Kota 2025",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/ipm/key/DEMO/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_sakernas_2025", "BPS", "Badan Pusat Statistik",
     "Ketenagakerjaan Kabupaten/Kota 2025 (Sakernas Agustus)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/sakernas/key/DEMO/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_susenas_2025", "BPS", "Badan Pusat Statistik",
     "Survei Sosial Ekonomi Nasional 2025 (Perumahan & Infrastruktur)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/susenas/key/DEMO/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_podes_2024", "BPS", "Badan Pusat Statistik",
     "Pendataan Potensi Desa 2024",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/podes/key/DEMO/",
     "REST_API", "Data Terbuka BPS", "Tiga Tahunan"),
    ("bnpb_irbi_2025", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "Indeks Risiko Bencana Indonesia (IRBI) 2025",
     "https://data.bnpb.go.id/",
     "https://data.bnpb.go.id/api/3/action/package_search?q=indeks+risiko+bencana",
     "CKAN_API", "Lisensi Terbuka Satu Data Indonesia", "Tahunan"),
    ("bnpb_kejadian_2025", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "Kompilasi Data Kejadian dan Dampak Bencana 2021-2025",
     "https://data.bnpb.go.id/",
     "https://data.bnpb.go.id/api/3/action/package_search?q=kompilasi+data+kejadian",
     "CKAN_API", "Lisensi Terbuka Satu Data Indonesia", "Tahunan"),
    ("bnpb_inarisk_raster", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "InaRISK Hazard Index Rasters (Banjir, Gempa, Longsor)",
     "https://gis.bnpb.go.id/server/rest/services/inarisk/",
     "https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_BAHAYA_BANJIR/ImageServer",
     "ARCGIS_REST", "Data Geospasial Terbuka BNPB", "Tahunan"),
    ("kemendikdasmen_statistik_2026", "KEMENDIKDASMEN",
     "Kementerian Pendidikan Dasar dan Menengah",
     "Statistik Persekolahan & Neraca Pendidikan Daerah 2025/2026",
     "https://data.kemendikdasmen.go.id/",
     "https://data.kemendikdasmen.go.id/dataset/statistik-persekolahan",
     "BATCH_FILE", "Data Terbuka Kemendikdasmen", "Semesteran"),
    ("kemendikdasmen_dapodik_2026", "KEMENDIKDASMEN",
     "Kementerian Pendidikan Dasar dan Menengah",
     "Rekap Dapodik Semester Ganjil 2026/2027",
     "https://dapo.kemendikdasmen.go.id/",
     "https://dapo.kemendikdasmen.go.id/rekap/progresSP",
     "BATCH_FILE", "Data Terbuka Kemendikdasmen", "Semesteran"),
    ("kemenkes_profil_2025", "KEMENKES", "Kementerian Kesehatan",
     "Profil Kesehatan Indonesia 2025",
     "https://kemkes.go.id/",
     "https://data.go.id/dataset/profil-kesehatan-indonesia",
     "BATCH_FILE", "Satu Data Indonesia (Perpres 39/2019)", "Tahunan"),
    ("kemenkes_ski_ssgi_2025", "KEMENKES", "Kementerian Kesehatan",
     "Survei Kesehatan Indonesia / SSGI Prevalensi Stunting 2025",
     "https://kemkes.go.id/",
     "https://data.go.id/dataset/stunting-prevalensi-kabkota",
     "BATCH_FILE", "Satu Data Indonesia (Perpres 39/2019)", "Tahunan"),
    ("nusamatra_internal_2026", "NUSAMATRA", "Nusa Matra Data Hub",
     "Internal Computed Metrics (Completeness, Freshness, Sync Rate)",
     "internal://nusamatra-data-hub",
     "internal://nusamatra-data-hub/etl-audit-log",
     "INTERNAL", "Internal", "Continuous"),
]

# ─── Indicator → Dataset Mapping ──────────────────────────────────────────────
AGENCY_TO_DATASET = {
    "BPS": "bps_susenas_2025",
    "BNPB": "bnpb_irbi_2025",
    "BNPB + BPS": "bnpb_kejadian_2025",
    "BPS / Kemendikdasmen": "bps_susenas_2025",
    "Kemendikdasmen": "kemendikdasmen_statistik_2026",
    "Kemenkes": "kemenkes_profil_2025",
    "Kemenkes / BPS": "kemenkes_profil_2025",
    "BPS / Kemenkes": "kemenkes_profil_2025",
    "Nusa Matra Hub": "nusamatra_internal_2026",
    "N/A": None,
}

# More specific overrides by indicator_id prefix
INDICATOR_DATASET_OVERRIDE = {
    "dis_multihazard_index": "bnpb_irbi_2025",
    "dis_flood_hazard_idx": "bnpb_inarisk_raster",
    "dis_earthquake_hazard_idx": "bnpb_inarisk_raster",
    "dis_landslide_hazard_idx": "bnpb_inarisk_raster",
    "dis_events_5yr_freq": "bnpb_kejadian_2025",
    "dis_affected_pop_per_10k": "bnpb_kejadian_2025",
    "soc_poverty_rate": "bps_kemiskinan_2025",
    "soc_poverty_severity_p2": "bps_kemiskinan_2025",
    "soc_hdi": "bps_ipm_2025",
    "soc_expenditure_per_capita": "bps_ipm_2025",
    "soc_unemployment_rate": "bps_sakernas_2025",
    "soc_dependency_ratio": "bps_susenas_2025",
    "edu_mean_years_schooling": "bps_ipm_2025",
    "edu_expected_years_schooling": "bps_ipm_2025",
    "edu_student_teacher_ratio_sd": "kemendikdasmen_dapodik_2026",
    "edu_damaged_classrooms_pct": "kemendikdasmen_statistik_2026",
    "hlt_life_expectancy": "bps_ipm_2025",
    "hlt_stunting_prevalence": "kemenkes_ski_ssgi_2025",
    "hlt_jkn_coverage_pct": "bps_susenas_2025",
    "inf_asphalt_road_village_pct": "bps_podes_2024",
    "meta_dapodik_sync_rate": "kemendikdasmen_dapodik_2026",
}

# ─── Value Ranges per Indicator (for plausible DEMO data) ─────────────────────
# (min_val, max_val, reference_year)
INDICATOR_RANGES = {
    "dis_multihazard_index": (20.0, 280.0, 2025),
    "dis_flood_hazard_idx": (0.0, 1.0, 2025),
    "dis_earthquake_hazard_idx": (0.0, 1.0, 2025),
    "dis_landslide_hazard_idx": (0.0, 1.0, 2025),
    "dis_events_5yr_freq": (0, 150, 2025),
    "dis_affected_pop_per_10k": (0.0, 500.0, 2025),
    "soc_poverty_rate": (1.5, 40.0, 2025),
    "soc_poverty_severity_p2": (0.01, 5.0, 2025),
    "soc_hdi": (45.0, 85.0, 2025),
    "soc_expenditure_per_capita": (4000, 22000, 2025),
    "soc_unemployment_rate": (1.0, 12.0, 2025),
    "soc_dependency_ratio": (35.0, 70.0, 2025),
    "edu_mean_years_schooling": (3.0, 13.0, 2025),
    "edu_expected_years_schooling": (8.0, 16.5, 2025),
    "edu_net_enrollment_smp": (60.0, 99.0, 2025),
    "edu_net_enrollment_sma": (40.0, 95.0, 2025),
    "edu_student_teacher_ratio_sd": (5.0, 35.0, 2026),
    "edu_damaged_classrooms_pct": (0.5, 45.0, 2025),
    "hlt_life_expectancy": (58.0, 78.0, 2025),
    "hlt_stunting_prevalence": (5.0, 40.0, 2025),
    "hlt_facilities_per_10k": (0.2, 8.0, 2025),
    "hlt_doctors_per_10k": (0.1, 15.0, 2025),
    "hlt_jkn_coverage_pct": (50.0, 99.0, 2025),
    "inf_safe_water_pct": (30.0, 99.0, 2025),
    "inf_safe_sanitation_pct": (25.0, 98.0, 2025),
    "inf_electrification_pct": (50.0, 100.0, 2025),
    "inf_internet_household_pct": (10.0, 95.0, 2025),
    "inf_asphalt_road_village_pct": (15.0, 100.0, 2024),
    "meta_indicator_completeness": (60.0, 100.0, 2026),
    "meta_freshness_lag_years": (0.0, 3.0, 2026),
    "meta_dapodik_sync_rate": (70.0, 100.0, 2026),
}

# Kemendikdasmen province code map (2-digit prov -> 6-digit prefix)
KEMENDIKDASMEN_PROV_MAP = {
    "31": "01", "32": "02", "33": "03", "34": "04", "35": "05", "36": "06",
    "11": "07", "12": "08", "13": "09", "14": "10", "15": "11", "16": "12",
    "17": "13", "18": "14", "19": "15", "21": "16",
    "51": "17", "52": "18", "53": "19",
    "61": "20", "62": "21", "63": "22", "64": "23", "65": "24",
    "71": "25", "72": "26", "73": "27", "74": "28", "75": "29", "76": "30",
    "81": "31", "82": "32",
    "91": "33", "92": "34", "93": "35", "94": "36", "95": "37", "96": "38",
}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 70)
    print("Nusa Matra Data Hub - DEMO Data Seeder")
    print("=" * 70)

    # Remove existing DB
    if DB_PATH.exists():
        print(f"[INFO] Removing existing database: {DB_PATH}")
        DB_PATH.unlink()

    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # -- 1. Run migration --------------------------------------------------
    print("[1/6] Running migration schema...")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()
    print("       [OK] Schema created")

    # -- 2. Insert snapshot ------------------------------------------------
    print("[2/6] Inserting DEMO snapshot...")
    conn.execute(
        """INSERT INTO data_snapshots
           (snapshot_id, label, environment_tag, is_active_default,
            boundary_version, manifest_checksum, notes, published_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            SNAPSHOT_ID,
            "WIA 2026 Demo Showcase Dataset",
            "DEMO",
            1,
            BOUNDARY_VER,
            "d3m0" * 16,  # 64-char placeholder
            "DEMO/EXAMPLE data only. Not sourced from verified LIVE measurements.",
        ),
    )
    conn.commit()
    print("       [OK] Snapshot: " + SNAPSHOT_ID)

    # -- 3. Insert datasets ------------------------------------------------
    print("[3/6] Inserting dataset catalog...")
    for ds in DATASETS:
        conn.execute(
            """INSERT INTO dim_datasets
               (dataset_id, agency_code, agency_name, dataset_title,
                official_portal_url, api_or_download_url, access_method,
                license_name, update_frequency, last_ingested_at,
                raw_archive_uri, raw_sha256)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)""",
            (
                ds[0], ds[1], ds[2], ds[3], ds[4], ds[5], ds[6], ds[7], ds[8],
                f"/raw/{ds[1].lower()}/2026-10-20/{ds[0]}.json",
                "demo_placeholder_" + "0" * (64 - len("demo_placeholder_")),
            ),
        )
    conn.commit()
    print(f"       [OK] {len(DATASETS)} datasets inserted")

    # -- 4. Insert regions -------------------------------------------------
    print("[4/6] Generating regions (38 provinces + 514 kab/kota)...")

    region_ids = []  # collect all kab/kota IDs for fact generation

    # Insert provinces
    for prov_code, name, short, island, n_kab, n_kota, lat, lng in PROVINCES:
        kemendagri = prov_code  # 2-digit for province
        conn.execute(
            """INSERT INTO dim_regions
               (region_id, parent_region_id, level, name, short_name,
                kemendagri_code, bps_code, kemendikdasmen_code,
                island_group, area_km2, label_lat, label_lng,
                bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat,
                boundary_version)
               VALUES (?, NULL, 'provinsi', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?)""",
            (
                prov_code,
                f"Provinsi {name}", short, kemendagri, prov_code,
                f"{KEMENDIKDASMEN_PROV_MAP.get(prov_code, '00')}0000",
                island, round(random.uniform(500, 150000), 2),
                lat, lng,
                lng - 1.5, lat - 1.0, lng + 1.5, lat + 1.0,
                BOUNDARY_VER,
            ),
        )

    # Insert kabupaten
    kab_kota_count = 0
    for prov_code, name, short, island, n_kab, n_kota, lat, lng in PROVINCES:
        kemdik_prefix = KEMENDIKDASMEN_PROV_MAP.get(prov_code, "00")

        for i in range(1, n_kab + 1):
            kab_code = f"{prov_code}{i:02d}"
            jitter_lat = lat + random.uniform(-0.8, 0.8)
            jitter_lng = lng + random.uniform(-0.8, 0.8)
            kemdik_code = f"{kemdik_prefix}{i:02d}00"

            conn.execute(
                """INSERT INTO dim_regions
                   (region_id, parent_region_id, level, name, short_name,
                    kemendagri_code, bps_code, kemendikdasmen_code,
                    island_group, area_km2, label_lat, label_lng,
                    bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat,
                    boundary_version)
                   VALUES (?, ?, 'kabupaten', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?)""",
                (
                    kab_code, prov_code,
                    f"Kabupaten Demo {short} {i}",
                    f"Demo {short} {i}",
                    f"{prov_code}.{i:02d}",
                    kab_code,
                    kemdik_code,
                    island,
                    round(random.uniform(100, 15000), 2),
                    round(jitter_lat, 6), round(jitter_lng, 6),
                    round(jitter_lng - 0.4, 6), round(jitter_lat - 0.3, 6),
                    round(jitter_lng + 0.4, 6), round(jitter_lat + 0.3, 6),
                    BOUNDARY_VER,
                ),
            )
            region_ids.append(kab_code)
            kab_kota_count += 1

        for j in range(1, n_kota + 1):
            kota_code = f"{prov_code}{70 + j:02d}"
            jitter_lat = lat + random.uniform(-0.5, 0.5)
            jitter_lng = lng + random.uniform(-0.5, 0.5)
            kemdik_code = f"{kemdik_prefix}{60 + j:02d}00"

            conn.execute(
                """INSERT INTO dim_regions
                   (region_id, parent_region_id, level, name, short_name,
                    kemendagri_code, bps_code, kemendikdasmen_code,
                    island_group, area_km2, label_lat, label_lng,
                    bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat,
                    boundary_version)
                   VALUES (?, ?, 'kota', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?)""",
                (
                    kota_code, prov_code,
                    f"Kota Demo {short} {j}",
                    f"Kota {short} {j}",
                    f"{prov_code}.{70 + j:02d}",
                    kota_code,
                    kemdik_code,
                    island,
                    round(random.uniform(20, 800), 2),
                    round(jitter_lat, 6), round(jitter_lng, 6),
                    round(jitter_lng - 0.15, 6), round(jitter_lat - 0.1, 6),
                    round(jitter_lng + 0.15, 6), round(jitter_lat + 0.1, 6),
                    BOUNDARY_VER,
                ),
            )
            region_ids.append(kota_code)
            kab_kota_count += 1

    conn.commit()
    print(f"       [OK] 38 provinces + {kab_kota_count} kab/kota = {38 + kab_kota_count} regions")

    # -- 5. Insert indicators from CSV -------------------------------------
    print("[5/6] Loading indicators from INDICATOR_MAPPING.csv...")
    indicators = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ind_id = row["indicator_id"].strip()
            agency = row["primary_source_agency"].strip()

            # Determine dataset_id
            dataset_id = INDICATOR_DATASET_OVERRIDE.get(ind_id)
            if dataset_id is None:
                dataset_id = AGENCY_TO_DATASET.get(agency)

            # Generate plausible national stats
            rng = INDICATOR_RANGES.get(ind_id)
            if rng:
                lo, hi, _ = rng
                n_mean = round(random.uniform(lo + (hi - lo) * 0.3, lo + (hi - lo) * 0.7), 4)
                n_median = round(n_mean + random.uniform(-2, 2), 4)
                n_min = round(lo + random.uniform(0, (hi - lo) * 0.1), 4)
                n_max = round(hi - random.uniform(0, (hi - lo) * 0.1), 4)
            else:
                n_mean = n_median = n_min = n_max = None

            conn.execute(
                """INSERT INTO dim_indicators
                   (indicator_id, indicator_name, category, unit, polarity,
                    availability_status, primary_dataset_id, derivation_formula,
                    description, national_mean, national_median,
                    national_min, national_max)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ind_id,
                    row["indicator_name"].strip(),
                    row["category"].strip(),
                    row["unit"].strip(),
                    row["polarity"].strip(),
                    row["availability_status"].strip(),
                    dataset_id,
                    row.get("derivation_formula_or_notes", "").strip() or None,
                    row["indicator_name"].strip(),
                    n_mean, n_median, n_min, n_max,
                ),
            )
            indicators.append((ind_id, row["availability_status"].strip(), dataset_id))

    conn.commit()
    print(f"       [OK] {len(indicators)} indicators loaded")

    # -- 6. Generate fact_indicator_values ---------------------------------
    print("[6/6] Generating indicator values for all kab/kota...")

    available_indicators = [
        (iid, dsid) for iid, status, dsid in indicators
        if status != "UNAVAILABLE" and dsid is not None
    ]
    print(f"       Generating values for {len(available_indicators)} available indicators * {len(region_ids)} regions...")

    total_facts = 0
    for ind_id, dataset_id in available_indicators:
        rng = INDICATOR_RANGES.get(ind_id)
        if not rng:
            continue

        lo, hi, ref_year = rng

        # Generate raw values for all regions
        raw_values = []
        for rid in region_ids:
            raw = round(random.uniform(lo, hi), 4)
            raw_values.append((rid, raw))

        # Sort by raw value for ranking
        sorted_vals = sorted(raw_values, key=lambda x: x[1])

        # Compute normalized scores using min-max within generated data
        actual_min = sorted_vals[0][1]
        actual_max = sorted_vals[-1][1]
        val_range = actual_max - actual_min if actual_max != actual_min else 1.0

        polarity = None
        for iid, status, _ in indicators:
            if iid == ind_id:
                # Look up polarity from the CSV data we already loaded
                break

        # Get polarity from DB since we already inserted it
        cur = conn.execute(
            "SELECT polarity FROM dim_indicators WHERE indicator_id = ?", (ind_id,)
        )
        polarity_row = cur.fetchone()
        polarity = polarity_row[0] if polarity_row else "negative"

        # Batch insert
        batch = []
        for rank_idx, (rid, raw) in enumerate(sorted_vals):
            # Normalized score: 0-100
            if polarity == "positive":
                # Lower raw = higher vulnerability score
                norm = round((1.0 - (raw - actual_min) / val_range) * 100, 2)
            else:
                # Higher raw = higher vulnerability score
                norm = round(((raw - actual_min) / val_range) * 100, 2)

            # Rank: 1 = highest vulnerability score
            if polarity == "positive":
                rank = rank_idx + 1  # lowest raw = rank 1 (most vulnerable)
            else:
                rank = len(sorted_vals) - rank_idx  # highest raw = rank 1

            # Percentile: 100 = most vulnerable, independent of source polarity
            pct = round(
                ((len(sorted_vals) - rank) / max(len(sorted_vals) - 1, 1)) * 100, 2
            )

            batch.append((
                SNAPSHOT_ID, rid, ind_id, ref_year,
                raw, norm, pct, rank,
                "DEMO_EXAMPLE", dataset_id, f"demo-seed-{ind_id}",
            ))

        conn.executemany(
            """INSERT INTO fact_indicator_values
               (snapshot_id, region_id, indicator_id, reference_year,
                raw_value, normalized_score, national_percentile,
                national_rank, quality_flag, dataset_id, source_record_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            batch,
        )
        total_facts += len(batch)

    conn.commit()
    print(f"       [OK] {total_facts} fact rows inserted")

    # -- Validation --------------------------------------------------------
    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    checks = [
        ("Provinces", "SELECT COUNT(*) FROM dim_regions WHERE level = 'provinsi'", 38),
        ("Kab/Kota", "SELECT COUNT(*) FROM dim_regions WHERE level IN ('kabupaten', 'kota')", 514),
        ("Total Regions", "SELECT COUNT(*) FROM dim_regions", 552),
        ("Indicators", "SELECT COUNT(*) FROM dim_indicators", 33),
        ("Available Indicators", "SELECT COUNT(*) FROM dim_indicators WHERE availability_status != 'UNAVAILABLE'", 31),
        ("Datasets", "SELECT COUNT(*) FROM dim_datasets", len(DATASETS)),
        ("Snapshots", "SELECT COUNT(*) FROM data_snapshots", 1),
    ]

    all_pass = True
    for label, query, expected in checks:
        cur = conn.execute(query)
        actual = cur.fetchone()[0]
        status = "[OK]" if actual == expected else "[FAIL]"
        if actual != expected:
            all_pass = False
        print(f"  {status} {label}: {actual} (expected {expected})")

    # Fact rows check (flexible)
    cur = conn.execute("SELECT COUNT(*) FROM fact_indicator_values")
    fact_count = cur.fetchone()[0]
    print(f"  {'[OK]' if fact_count > 0 else '[FAIL]'} Fact rows: {fact_count}")

    conn.close()

    print()
    if all_pass:
        print("[SUCCESS] All validation checks passed!")
        print(f"[PATH] Database created at: {DB_PATH}")
    else:
        print("[ERROR] Some validation checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
