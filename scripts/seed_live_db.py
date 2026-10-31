#!/usr/bin/env python3
"""
Nusa Matra Data Hub — Official LIVE Database Seeder

Seeds data/nusa_matra_live.db from:
- Real BIG 2026 boundaries (38 Prov & 514 Kab/Kota)
- Real Master CSV (data/verified_indicators_master.csv)
- Real Metadata (data/INDICATOR_MAPPING.csv)
"""

import csv
import json
import os
import sqlite3
import sys
import hashlib
import statistics
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.crosswalk_service import crosswalk_rows, first_value, sort_vintages
from app.services.indicator_policy import (
    RETIRED_PUBLIC_INDICATORS,
    retirement_reason,
)
from app.services.normalization_service import (
    METHODOLOGY_VERSION,
    normalize_score,
    rank_normalized_values,
)
from app.services.snapshot_integrity import (
    STAGING_SNAPSHOT_ID,
    ensure_snapshot_schema,
    finalize_staging_snapshot,
    mark_legacy_snapshots,
    verify_content_digest,
)
DB_PATH = Path(
    os.environ.get("NM_LIVE_DATABASE_PATH")
    or os.environ.get("LIVE_DATABASE_PATH")
    or REPO_ROOT / "data" / "nusa_matra_live.db"
)
MIGRATION_PATH = REPO_ROOT / "migrations" / "001_init_schema.sql"
MASTER_CSV = REPO_ROOT / "data" / "verified_indicators_master.csv"
MAPPING_CSV = REPO_ROOT / "data" / "INDICATOR_MAPPING.csv"
PROV_GEOJSON = REPO_ROOT / "data" / "boundaries" / "indonesia_provinsi_low.geojson"
KAB_GEOJSON = REPO_ROOT / "data" / "boundaries" / "indonesia_kabupaten_low.geojson"

SNAPSHOT_ID = STAGING_SNAPSHOT_ID
BOUNDARY_VER = "BIG-20260601"

OFFICIAL_DATASETS = [
    ("bps_susenas_sakernas_2025", "BPS", "Badan Pusat Statistik",
     "Indikator Strategis & SDGs Kemiskinan, Ketenagakerjaan, Sanitasi 2024-2025",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_ipm_2025", "BPS", "Badan Pusat Statistik",
     "Indeks Pembangunan Manusia (IPM) dan Umur Harapan Hidup (UHH) 2025",
     "https://www.bps.go.id/id/publication/2026/04/24/f96755ab0e48765d028c0462/indeks-pembangunan-manusia-2025.html",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/2205/th/125/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bnpb_irbi_2024", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "Indeks Risiko Bencana Indonesia (IRBI) Multi-Bencana & Per Ancaman 2024",
     "https://inarisk.bnpb.go.id/",
     "https://inarisk.bnpb.go.id/IRBI-2024/",
     "FLIPBOOK_HTML", "Data Terbuka BNPB", "Tahunan"),
    ("bnpb_irbi_2025", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "Indeks Risiko Bencana Indonesia (IRBI) 2025 — Multi-Bencana, Gempa, Banjir",
     "https://inarisk.bnpb.go.id/irbi",
     "https://inarisk.bnpb.go.id/irbi",
     "DASHBOARD_TABLE", "Data Terbuka BNPB", "Tahunan"),
    ("kemenkes_ski_2023", "KEMENKES", "Kementerian Kesehatan",
     "Survei Kesehatan Indonesia (SKI) 2023 Prevalensi Status Gizi Balita",
     "https://badankebijakan.kemkes.go.id/",
     "https://badankebijakan.kemkes.go.id/ski-2023-dalam-angka/",
     "PDF_TABLE", "Data Terbuka Kemenkes", "Tahunan"),
    ("kemenkes_ssgi_2024", "KEMENKES", "Kementerian Kesehatan",
     "Survei Status Gizi Indonesia (SSGI) 2024 Dalam Angka",
     "https://www.badankebijakan.kemkes.go.id/perpustakaanbkpkkemkes/index.php?id=40008&p=show_detail",
     "https://drive.google.com/file/d/1FmhMtFsElv0l95YNGqsoKy5xJh-m-glM/view",
     "PDF_TABLE", "Data Terbuka Kemenkes", "Tahunan"),
    ("kemendikdasmen_ref_2026", "KEMENDIKDASMEN", "Kementerian Pendidikan Dasar dan Menengah",
     "Data Referensi Satuan Pendidikan Persekolahan (SD, SMP, SMA, SMK) 2026",
     "https://referensi.data.kemendikdasmen.go.id/",
     "https://referensi.data.kemendikdasmen.go.id/pendidikan/dikdas",
     "WEB_TABLE", "Data Terbuka Kemendikdasmen", "Semesteran"),
    ("big_batas_2026", "BIG", "Badan Informasi Geospasial",
     "Batas Wilayah Administrasi Kabupaten/Kota Edisi 1 Juni 2026",
     "https://geoservices.big.go.id/",
     "https://geoservices.big.go.id/rbi/rest/services/BATASWILAYAH/",
     "ESRI_GDB", "Geospasial Terbuka BIG", "Semesteran"),
    ("bmkg_earthquakes_live", "BMKG", "Badan Meteorologi, Klimatologi, dan Geofisika",
     "Pemantauan Gempabumi Terkini & Dirasakan Indonesia (Auto-Gempa & M >= 5.0)",
     "https://data.bmkg.go.id/gempabumi/",
     "https://data.bmkg.go.id/DataMKG/TEWS/",
     "REST_API", "Data Terbuka BMKG", "Event-Driven"),
    ("nusa_matra_internal_audit", "NUSAMATRA", "Nusa Matra Data Hub",
     "Internal Ingestion Audit (completeness & freshness derived from active snapshot)",
     "https://api.nusamatra.site",
     "internal://ingestion-audit",
     "INTERNAL_DERIVATION", "Internal", "Per Snapshot"),
    ("bps_sdgs_kabkota_2025", "BPS", "Badan Pusat Statistik",
     "Susenas 2025 - Akses Air Minum Layak & Sanitasi Layak per Kabupaten/Kota (WebAPI var 2830 & 2748)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("kemendikdasmen_apm_2024_2025", "KEMENDIKDASMEN", "Kementerian Pendidikan Dasar dan Menengah",
     "APK/APM PAUD, SD, SMP, dan SM Tahun 2024/2025 (termasuk Madrasah dan Sederajat)",
     "https://data.kemendikdasmen.go.id/",
     "https://data.kemendikdasmen.go.id/publikasi/p/vokasi-buku-analisis/apk-apm-paud-sd-smp-dan-sm-tahun-2024-2025-termasuk-madrasah-dan-sederajat-2025",
     "PDF_TABLE", "Data Terbuka Kemendikdasmen", "Tahunan"),
    ("bnpb_dibi_kabkota_2024", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "Kompilasi Data Kejadian dan Dampak Bencana - Jumlah Kejadian per Kabupaten 2010-2024",
     "https://data.bnpb.go.id/dataset/data-bencana-indonesia",
     "https://data.bnpb.go.id/api/3/action/datastore_search?resource_id=21044ffd-c397-4b3c-acbd-5adaa03d79e3",
     "CKAN_API", "Lisensi Terbuka Satu Data Indonesia", "Tahunan"),
    ("bps_proyeksi_penduduk_2026", "BPS", "Badan Pusat Statistik",
     "Proyeksi Penduduk Indonesia 2020-2050 Hasil SP2020 - Kabupaten/Kota menurut Kelompok Umur (2026)",
     "https://www.bps.go.id/id/statistics-table/2/Mjc5MCMy/-jumlah-penduduk-menurut-kabupaten-kota-dan-kelompok-umur.html",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/2790/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_susenas_tik_2024", "BPS", "Badan Pusat Statistik",
     "Susenas 2024 - Persentase Rumah Tangga yang Mengakses Internet (provinsi)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/398/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_susenas_jkn_2025", "BPS", "Badan Pusat Statistik",
     "Susenas Maret 2025 - Persentase Penduduk dengan Jaminan Kesehatan Nasional (provinsi)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/2279/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bps_provincial_sdgs_2025", "BPS", "Badan Pusat Statistik",
     "Susenas 2025 - Akses Air Minum Layak per Provinsi (legacy BPS province codes)",
     "https://webapi.bps.go.id/developer/",
     "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/845/th/125/",
     "REST_API", "Data Terbuka BPS", "Tahunan"),
    ("bnpb_dibi_affected_2024", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "BNPB DIBI 2024 - Korban Terdampak dan Mengungsi Menurut Provinsi",
     "https://data.bnpb.go.id/dataset/data-bencana-indonesia",
     "https://data.bnpb.go.id/api/3/action/datastore_search?resource_id=39ceb577-b49f-45c9-b909-7dd8daef417a",
     "CKAN_API", "Lisensi Terbuka Satu Data Indonesia", "Tahunan"),
    ("bnpb_dibi_affected_2025", "BNPB", "Badan Nasional Penanggulangan Bencana",
     "BNPB DIBI 2025 - Korban Terdampak dan Mengungsi Menurut Provinsi",
     "https://data.bnpb.go.id/dataset/kompilasi-data-kejadian-dan-dampak-bencana-2025",
     "https://data.bnpb.go.id/api/3/action/datastore_search?resource_id=8d8db1c8-d79b-4fb1-b735-d8b9c1e0517a",
     "CKAN_API", "Lisensi Terbuka Satu Data Indonesia", "Tahunan"),
    ("kemendikdasmen_statistik_2026", "KEMENDIKDASMEN", "Kementerian Pendidikan Dasar dan Menengah",
     "Statistik Ruang Kelas dan Rasio Murid-Guru SD Tahun Ajaran 2022/2023 (kab/kota)",
     "https://data.kemendikdasmen.go.id/dataset/p/sarana-dan-prasarana",
     "https://cdn.data-portal.belajar.id/Aset-Dataset/20241105/1d05febc22bb5ad9f749ccfa6eee06e9444c08256b3f48977f7ff465c78af9d6.xlsx",
     "XLSX_DOWNLOAD", "Data Terbuka Kemendikdasmen", "Tahunan"),
    ("kemendikdasmen_npd_2025", "KEMENDIKDASMEN", "Kementerian Pendidikan Dasar dan Menengah",
     "Neraca Pendidikan Daerah (NPD) 2025 — Rasio Pendidik : Peserta Didik SD",
     "https://npd.kemendikdasmen.go.id/grafik?tahun=2025",
     "https://npd.kemendikdasmen.go.id/grafik?tahun=2025",
     "DASHBOARD_TABLE", "Data Terbuka Kemendikdasmen", "Tahunan"),
    ("kemendikdasmen_statistik_2025", "KEMENDIKDASMEN", "Kementerian Pendidikan Dasar dan Menengah",
     "Jumlah Ruang Kelas Menurut Kondisi — SD & SMP, 2025",
     "https://data.kemendikdasmen.go.id/dataset/td/sarana-dan-prasarana-qraac/jumlah-ruang-kelas-menurut-kondisi-2025-semua-wilayah-sd-mi-sederajat-1",
     "https://api.data.belajar.id/data-portal-backend/v2/datasets",
     "REST_API", "Data Terbuka Kemendikdasmen", "Tahunan"),
    ("kemenkes_sirs_regpus_2026", "KEMENKES", "Kementerian Kesehatan",
     "RS Online dan Data Puskesmas Teregistrasi Semester II 2025 (kab/kota)",
     "https://sirs.kemkes.go.id/fo/home/dashboard_rs?id=0",
     "https://sirs.kemkes.go.id/fo/home/rekap_rs_all?id=0",
     "REST_API+PDF_TABLE", "Data Terbuka Kemenkes", "Semesteran"),
    ("kemenkes_satusehat_dokter_2026", "KEMENKES", "Kementerian Kesehatan",
     "Jumlah Dokter di Fasilitas Kesehatan per Provinsi (SATUSEHAT Data)",
     "https://satusehat.kemkes.go.id/data/dataset/65cff906-5fd1-4f8d-baad-9f6ad837f5b8",
     "https://api.kemkes.go.id/satusehat-data/dataset/public/65cff906-5fd1-4f8d-baad-9f6ad837f5b8/csv",
     "REST_API", "Data Terbuka Kemenkes", "Bulanan"),
]

def calc_bbox_and_centroid(coords):
    def flatten(c):
        for item in c:
            if isinstance(item[0], (int, float)):
                yield item
            else:
                yield from flatten(item)
    all_pts = list(flatten(coords))
    if not all_pts:
        return 0, 0, 0, 0, 0, 0
    lngs = [p[0] for p in all_pts]
    lats = [p[1] for p in all_pts]
    min_lng, max_lng = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)
    center_lng = (min_lng + max_lng) / 2
    center_lat = (min_lat + max_lat) / 2
    return center_lat, center_lng, min_lng, min_lat, max_lng, max_lat

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 70)
    print("Nusa Matra Data Hub — Official LIVE Database Seeder")
    print("=" * 70)

    if DB_PATH.exists():
        print(f"[INFO] Preserving existing snapshot history in: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    # Metadata tables are upserted by primary key; facts from older immutable
    # snapshots must remain valid while the build is in progress.
    conn.execute("PRAGMA foreign_keys = OFF")

    # 1. Init schema
    print("[1/6] Initialising schema from migrations/001_init_schema.sql...")
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    ensure_snapshot_schema(conn)
    conn.commit()

    # 2. Rebuild only the unpublished staging snapshot.
    print("[2/6] Preparing immutable LIVE snapshot staging area...")
    for table in ("fact_indicator_values", "snapshot_indicators", "data_snapshots"):
        if table == "data_snapshots":
            conn.execute(
                "DELETE FROM data_snapshots WHERE snapshot_id = ? AND is_immutable = 0",
                (SNAPSHOT_ID,),
            )
        else:
            conn.execute(f"DELETE FROM {table} WHERE snapshot_id = ?", (SNAPSHOT_ID,))
    checksum = hashlib.sha256(b"nusa_matra_official_live_staging").hexdigest()
    conn.execute(
        """INSERT INTO data_snapshots
           (snapshot_id, label, environment_tag, is_active_default,
            boundary_version, manifest_checksum, notes, published_at,
            content_hash_spec, is_immutable, is_reproducible, methodology_version)
           VALUES (?, ?, 'LIVE', 0, ?, ?, ?, datetime('now'), 'canonical-json-v1', 0, 0, ?)""",
        (
            SNAPSHOT_ID,
            "Nusa Matra Official LIVE Snapshot (staging)",
            BOUNDARY_VER,
            checksum,
            "Staging snapshot; replaced by a digest-addressed immutable snapshot.",
            METHODOLOGY_VERSION,
        ),
    )
    conn.commit()

    # 3. Insert Datasets
    print("[3/6] Inserting official dataset catalog...")
    for ds in OFFICIAL_DATASETS:
        conn.execute(
            """INSERT OR REPLACE INTO dim_datasets
               (dataset_id, agency_code, agency_name, dataset_title,
                official_portal_url, api_or_download_url, access_method,
                license_name, update_frequency, last_ingested_at,
                raw_archive_uri, raw_sha256)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)""",
            (
                ds[0], ds[1], ds[2], ds[3], ds[4], ds[5], ds[6], ds[7], ds[8],
                f"/data/raw/{ds[1].lower()}/",
                hashlib.sha256(ds[0].encode()).hexdigest(),
            ),
        )
    conn.commit()
    print(f"       [OK] {len(OFFICIAL_DATASETS)} official datasets inserted")

    # 4. Insert Regions from GeoJSON
    print("[4/6] Seeding 38 Provinsi & 514 Kab/Kota from official GeoJSON...")
    
    # Provinces
    with open(PROV_GEOJSON, "r", encoding="utf-8") as f:
        prov_gj = json.load(f)
    for feat in prov_gj["features"]:
        props = feat["properties"]
        geom = feat["geometry"]
        c_lat, c_lng, min_lng, min_lat, max_lng, max_lat = calc_bbox_and_centroid(geom["coordinates"])
        conn.execute(
            """INSERT OR REPLACE INTO dim_regions
               (region_id, parent_region_id, level, name, short_name,
                kemendagri_code, bps_code, island_group, area_km2,
                label_lat, label_lng, bbox_min_lng, bbox_min_lat,
                bbox_max_lng, bbox_max_lat, boundary_version)
               VALUES (?, NULL, 'provinsi', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                props["region_id"],
                props["name"],
                props["short_name"],
                props["kemendagri_code"],
                props["bps_code"],
                "Indonesia",
                0.0,
                round(c_lat, 6), round(c_lng, 6),
                round(min_lng, 6), round(min_lat, 6),
                round(max_lng, 6), round(max_lat, 6),
                BOUNDARY_VER,
            ),
        )

    # Kab/Kota
    with open(KAB_GEOJSON, "r", encoding="utf-8") as f:
        kab_gj = json.load(f)
    kab_count = 0
    for feat in kab_gj["features"]:
        props = feat["properties"]
        geom = feat["geometry"]
        c_lat, c_lng, min_lng, min_lat, max_lng, max_lat = calc_bbox_and_centroid(geom["coordinates"])
        lvl = "kota" if props["type"].lower() == "kota" else "kabupaten"
        conn.execute(
            """INSERT OR REPLACE INTO dim_regions
               (region_id, parent_region_id, level, name, short_name,
                kemendagri_code, bps_code, island_group, area_km2,
                label_lat, label_lng, bbox_min_lng, bbox_min_lat,
                bbox_max_lng, bbox_max_lat, boundary_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                props["region_id"],
                props["parent_region_id"],
                lvl,
                props["name"],
                props["short_name"],
                props["kemendagri_code"],
                props["bps_code"],
                props["province_name"],
                0.0,
                round(c_lat, 6), round(c_lng, 6),
                round(min_lng, 6), round(min_lat, 6),
                round(max_lng, 6), round(max_lat, 6),
                BOUNDARY_VER,
            ),
        )
        kab_count += 1

    conn.commit()
    print(f"       [OK] {len(prov_gj['features'])} provinces & {kab_count} kab/kota inserted from BIG 2026")

    # 5. Insert Indicators catalog
    print("[5/6] Inserting indicator catalog from INDICATOR_MAPPING.csv...")
    indicators_meta = {}
    with open(MAPPING_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ind_id = r["indicator_id"]
            ds_id = "bps_susenas_sakernas_2025"
            if ind_id in ("soc_hdi", "hlt_life_expectancy"):
                ds_id = "bps_ipm_2025"
            elif ind_id == "dis_affected_pop_per_10k":
                ds_id = "bnpb_dibi_affected_2025"
            elif ind_id == "dis_events_5yr_freq":
                ds_id = "bnpb_dibi_kabkota_2024"
            elif ind_id in (
                "dis_multihazard_index",
                "dis_flood_hazard_idx",
                "dis_earthquake_hazard_idx",
            ):
                ds_id = "bnpb_irbi_2025"
            elif "BNPB" in r["primary_source_agency"]:
                ds_id = "bnpb_irbi_2024"
            elif ind_id == "hlt_stunting_prevalence":
                ds_id = "kemenkes_ssgi_2024"
            elif "Kemenkes" in r["primary_source_agency"]:
                ds_id = "kemenkes_ski_2023"
            elif "Kemendikdasmen" in r["primary_source_agency"]:
                ds_id = "kemendikdasmen_ref_2026"
            elif "Nusa Matra" in r["primary_source_agency"]:
                ds_id = "nusa_matra_internal_audit"

            if ind_id == "edu_student_teacher_ratio_sd":
                ds_id = "kemendikdasmen_npd_2025"
            elif ind_id == "edu_damaged_classrooms_pct":
                ds_id = "kemendikdasmen_statistik_2025"
            elif ind_id == "hlt_facilities_per_10k":
                ds_id = "kemenkes_sirs_regpus_2026"
            elif ind_id == "hlt_doctors_per_10k":
                ds_id = "kemenkes_satusehat_dokter_2026"

            indicators_meta[ind_id] = {
                "name": r["indicator_name"],
                "category": r["category"],
                "unit": r["unit"],
                "polarity": r["polarity"],
                "availability": r["availability_status"],
                "dataset_id": ds_id,
                "formula": r["derivation_formula_or_notes"]
            }
            is_public = 0 if ind_id in RETIRED_PUBLIC_INDICATORS else 1
            retired_at = (
                datetime.now(timezone.utc).isoformat() if not is_public else None
            )
            conn.execute(
                """INSERT OR REPLACE INTO dim_indicators
                   (indicator_id, indicator_name, category, unit, polarity,
                    availability_status, primary_dataset_id, derivation_formula,
                    description, is_public, retired_at, retirement_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ind_id, r["indicator_name"], r["category"], r["unit"],
                    r["polarity"], r["availability_status"], ds_id,
                    r["derivation_formula_or_notes"], r["indicator_name"],
                    is_public, retired_at, retirement_reason(ind_id),
                ),
            )
    conn.commit()

    # 6. Insert Fact Indicator Values from Master CSV
    print("[6/6] Populating fact_indicator_values with real verified data...")
    with open(MASTER_CSV, "r", encoding="utf-8") as f:
        master_rows = list(csv.DictReader(f))

    regions = [
        {
            "region_id": row[0],
            "parent_region_id": row[1],
            "bps_code": row[2],
            "name": row[3],
            "level": row[4],
        }
        for row in conn.execute(
            "SELECT region_id, parent_region_id, bps_code, name, level "
            "FROM dim_regions WHERE level IN ('kabupaten', 'kota')"
        )
    ]

    crosswalk = crosswalk_rows(master_rows, regions)
    print(
        f"       Crosswalk matched {len(crosswalk.covered_region_ids)}/{len(regions)} regions "
        f"({len(crosswalk.multi_vintage_region_ids)} multi-vintage); "
        f"unmatched={len(crosswalk.unmatched)}, ambiguous={len(crosswalk.ambiguous)}"
    )

    uncovered = sorted(
        {region["region_id"] for region in regions} - crosswalk.covered_region_ids
    )
    if uncovered:
        print(f"       [ERROR] Crosswalk left {len(uncovered)} regions uncovered: {uncovered}")
        sys.exit(1)

    for entry in crosswalk.unmatched + crosswalk.ambiguous:
        conn.execute(
            """INSERT INTO etl_quarantine_rows
               (dataset_id, raw_region_code, raw_region_name, raw_payload, failure_reason)
               VALUES (?, ?, ?, ?, ?)""",
            (
                "crosswalk",
                entry.get("bps_code"),
                entry.get("region_name"),
                json.dumps(entry, ensure_ascii=False),
                entry["reason"],
            ),
        )

    # Column to indicator mapping: (indicator_id, reference_year, dataset_id, source_label)
    col_to_ind = {
        "edu_mean_years_schooling": ("edu_mean_years_schooling", 2025, "bps_susenas_sakernas_2025", "BPS RLS 2025"),
        "edu_expected_years_schooling": ("edu_expected_years_schooling", 2025, "bps_susenas_sakernas_2025", "BPS HLS 2025"),
        "soc_expenditure_per_capita": ("soc_expenditure_per_capita", 2025, "bps_susenas_sakernas_2025", "BPS Pengeluaran Riil 2025"),
        "soc_poverty_rate": ("soc_poverty_rate", 2025, "bps_susenas_sakernas_2025", "BPS P0 Susenas 2025"),
        "soc_poverty_count": ("soc_poverty_count", 2025, "bps_susenas_sakernas_2025", "BPS Jumlah Miskin 2025"),
        "soc_poverty_severity_p2": ("soc_poverty_severity_p2", 2025, "bps_susenas_sakernas_2025", "BPS P2 Susenas 2025"),
        "soc_unemployment_rate": ("soc_unemployment_rate", 2025, "bps_susenas_sakernas_2025", "BPS TPT Sakernas 2025"),
        "dis_landslide_score": ("dis_landslide_hazard_idx", 2024, "bnpb_irbi_2024", "BNPB IRBI 2024 Longsor"),
        "inf_electrification_prov_pct": ("inf_electrification_pct", 2025, "bps_susenas_sakernas_2025", "BPS Susenas Prov 2025"),
    }
    master_columns = list(master_rows[0].keys())

    def _seed_facts(ind_id, ref_year, ds_id, ref_src, values, polarity):
        """
        Replace one indicator's observations for this snapshot, then normalize
        and rank the full canonical set exactly once.

        Replacing instead of merging prevents leftover rows from an earlier
        provenance pass from retaining stale normalized scores.
        """
        if not values or ind_id in RETIRED_PUBLIC_INDICATORS:
            return 0

        conn.execute(
            "DELETE FROM fact_indicator_values WHERE snapshot_id = ? AND indicator_id = ?",
            (SNAPSHOT_ID, ind_id),
        )

        raw_numbers = [v[1] for v in values]
        v_min, v_max = min(raw_numbers), max(raw_numbers)
        v_mean = sum(raw_numbers) / len(raw_numbers)
        v_median = statistics.median(raw_numbers)

        conn.execute(
            """UPDATE dim_indicators
               SET national_min = ?, national_max = ?, national_mean = ?, national_median = ?
               WHERE indicator_id = ?""",
            (round(v_min, 4), round(v_max, 4), round(v_mean, 4), round(v_median, 4), ind_id),
        )

        normalized = []
        for item in values:
            if len(item) == 5:
                rid, val, flag, row_ds_id, row_ref = item
            else:
                rid, val, flag = item
                row_ds_id, row_ref = ds_id, ref_src
            norm_score = normalize_score(val, v_min, v_max, polarity)
            normalized.append((rid, val, norm_score, flag, row_ds_id, row_ref))

        ranked_rows = rank_normalized_values(
            [(rid, val, score, flag) for rid, val, score, flag, _, _ in normalized]
        )
        by_region = {
            rid: (val, score, rank, percentile)
            for rid, val, score, rank, percentile in ranked_rows
        }
        for rid, val, norm_score, flag, row_ds_id, row_ref in normalized:
            _, _, rank, percentile = by_region[rid]
            conn.execute(
                """INSERT OR REPLACE INTO fact_indicator_values
                   (snapshot_id, region_id, indicator_id, reference_year,
                    raw_value, normalized_score, national_percentile, national_rank,
                    quality_flag, dataset_id, source_record_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    SNAPSHOT_ID, rid, ind_id, ref_year,
                    round(val, 4), norm_score, percentile,
                    rank, flag, row_ds_id, row_ref,
                ),
            )
        return len(normalized)

    for col_name, (ind_id, ref_year, ds_id, ref_src) in col_to_ind.items():
        if ind_id not in indicators_meta:
            continue

        values = []
        for region in regions:
            rid = region["region_id"]
            rows = sort_vintages(
                crosswalk.rows_by_region.get(rid, []), master_columns, region
            )
            raw = first_value(rows, col_name)
            if raw is None:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            flag = "IMPUTED_PROVINCE" if col_name.endswith("_prov_pct") else "VERIFIED"
            values.append((rid, value, flag))

        _seed_facts(
            ind_id,
            ref_year,
            ds_id,
            ref_src,
            values,
            indicators_meta[ind_id]["polarity"],
        )

    conn.commit()

    # 6-bps-ipm. BPS IPM 2025 (variables 2205/2206) covers all 514 kab/kota.
    # This replaces the 2024 IPM/UHH values from the older master snapshot.
    ipm_2025_csv = REPO_ROOT / "data" / "bps_ipm_2025_kabkota.csv"
    if not ipm_2025_csv.exists():
        print(f"[ERROR] Missing required BPS IPM 2025 CSV: {ipm_2025_csv}")
        sys.exit(1)
    with open(ipm_2025_csv, "r", encoding="utf-8") as f:
        ipm_rows = list(csv.DictReader(f))

    for ind_id, column in (
        ("soc_hdi", "soc_hdi"),
        ("hlt_life_expectancy", "hlt_life_expectancy"),
    ):
        values = []
        for row in ipm_rows:
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                values.append((row["region_id"], float(raw), "VERIFIED"))
            except (KeyError, ValueError):
                continue
        if len(values) != 514:
            print(
                f"[ERROR] {ind_id} IPM 2025 coverage is {len(values)}/514; "
                "refusing partial series."
            )
            sys.exit(1)
        _seed_facts(
            ind_id,
            2025,
            "bps_ipm_2025",
            f"BPS IPM 2025 — {column} (kab/kota)",
            values,
            indicators_meta[ind_id]["polarity"],
        )
    conn.commit()
    print(f"       [OK] BPS IPM/UHH 2025: {len(ipm_rows)} rows")

    # 6-irbi. IRBI 2025 from the InaRISK web export. Only multi-hazard,
    # earthquake, and flood are replaced; landslide remains the 2024 series
    # because its 2025 coverage (455/514) is lower than 2024 (510/514).
    irbi_2025_csv = REPO_ROOT / "data" / "bnpb_irbi_2025_hazards.csv"
    if not irbi_2025_csv.exists():
        print(f"[ERROR] Missing required IRBI 2025 CSV: {irbi_2025_csv}")
        sys.exit(1)
    with open(irbi_2025_csv, "r", encoding="utf-8") as f:
        irbi_rows = list(csv.DictReader(f))

    for ind_id, column, expected in (
        ("dis_multihazard_index", "dis_multihazard_index", 514),
        ("dis_earthquake_hazard_idx", "dis_earthquake_hazard_idx", 514),
        ("dis_flood_hazard_idx", "dis_flood_hazard_idx", 510),
    ):
        values = []
        for row in irbi_rows:
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                values.append((row["region_id"], float(raw), "VERIFIED"))
            except (KeyError, ValueError):
                continue
        if len(values) != expected:
            print(
                f"[ERROR] {ind_id} IRBI 2025 coverage is {len(values)}/{expected}; "
                "refusing partial series."
            )
            sys.exit(1)
        _seed_facts(
            ind_id,
            2025,
            "bnpb_irbi_2025",
            f"BNPB IRBI 2025 — {column} (kab/kota)",
            values,
            indicators_meta[ind_id]["polarity"],
        )
    conn.commit()
    print(f"       [OK] IRBI 2025 multi/gempa/banjir: {len(irbi_rows)} rows")

    # 6-stunting. Verified SSGI 2024 has full 514 kab/kota coverage, including
    # the 27 regions absent from SKI 2023. This replaces the older stunting
    # vintage for the new snapshot instead of mixing survey years.
    stunting_csv = REPO_ROOT / "data" / "kemenkes_ssgi_2024_stunting.csv"
    if not stunting_csv.exists():
        print(f"[ERROR] Missing required SSGI 2024 CSV: {stunting_csv}")
        sys.exit(1)
    with open(stunting_csv, "r", encoding="utf-8") as f:
        stunting_rows = list(csv.DictReader(f))

    stunting_values = []
    for row in stunting_rows:
        raw = (row.get("hlt_stunting_prevalence") or "").strip()
        if not raw:
            continue
        try:
            stunting_values.append(
                (
                    row["region_id"],
                    float(raw),
                    "VERIFIED",
                    "kemenkes_ssgi_2024",
                    f"Kemenkes SSGI 2024 p.{row.get('pdf_page', '?')}",
                )
            )
        except (KeyError, ValueError):
            continue

    if len(stunting_values) != 514:
        print(
            f"[ERROR] SSGI 2024 stunting coverage is {len(stunting_values)}/514; "
            "refusing to publish a partial series."
        )
        sys.exit(1)

    _seed_facts(
        "hlt_stunting_prevalence",
        2024,
        "kemenkes_ssgi_2024",
        "Kemenkes SSGI 2024 (kab/kota)",
        stunting_values,
        indicators_meta["hlt_stunting_prevalence"]["polarity"],
    )
    conn.commit()
    print(f"       [OK] Verified SSGI 2024 stunting: {len(stunting_values)}/514 kab/kota")

    # 6a. Build the canonical water/sanitation sets.
    # Verified kab/kota values come from BPS WebAPI (var 2830 & 2748, th 125).
    # When a kab/kota water value is genuinely absent (Lanny Jaya 9507), retain
    # the official province-level Susenas value as an explicit IMPUTED_PROVINCE
    # fallback. Both sources are normalized together exactly once.
    verified_sdgs_csv = REPO_ROOT / "data" / "bps_kabkota_water_sanitation_2025.csv"
    if verified_sdgs_csv.exists():
        with open(verified_sdgs_csv, "r", encoding="utf-8") as f:
            sdgs_rows = list(csv.DictReader(f))

        province_names_by_code: dict[str, str] = {}
        province_csv = REPO_ROOT / "data" / "bps_provincial_sdgs_2025.csv"
        if province_csv.exists():
            with open(province_csv, "r", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    province_names_by_code[str(row.get("bps_prov_code") or "")[:2]] = (
                        row.get("province_name") or "unknown"
                    )

        verified_by_region = {row["region_id"]: row for row in sdgs_rows}
        for ind_id, column, fallback_column in (
            ("inf_safe_water_pct", "inf_safe_water_pct", "inf_safe_water_prov_pct"),
            ("inf_safe_sanitation_pct", "inf_safe_sanitation_pct", None),
        ):
            values = []
            for region in regions:
                rid = region["region_id"]
                verified_row = verified_by_region.get(rid) or {}
                raw = (verified_row.get(column) or "").strip()
                if raw:
                    try:
                        values.append(
                            (
                                rid,
                                float(raw),
                                "VERIFIED",
                                "bps_sdgs_kabkota_2025",
                                "BPS Susenas 2025 WebAPI (kab/kota)",
                            )
                        )
                    except ValueError:
                        continue
                    continue

                if not fallback_column:
                    continue

                ordered = sort_vintages(
                    crosswalk.rows_by_region.get(rid, []), master_columns, region
                )
                fallback = first_value(ordered, fallback_column)
                if not fallback:
                    continue
                source_row = next(
                    (
                        row
                        for row in ordered
                        if (row.get(fallback_column) or "").strip()
                    ),
                    {},
                )
                legacy_prefix = str(source_row.get("bps_code") or "")[:2]
                province_name = province_names_by_code.get(legacy_prefix, "unknown")
                values.append(
                    (
                        rid,
                        float(fallback),
                        "IMPUTED_PROVINCE",
                        "bps_provincial_sdgs_2025",
                        (
                            f"BPS Susenas 2025 Provinsi {province_name} "
                            f"(legacy BPS {legacy_prefix}00)"
                        ),
                    )
                )

            if values:
                _seed_facts(
                    ind_id,
                    2025,
                    "bps_sdgs_kabkota_2025",
                    "BPS Susenas 2025 WebAPI (kab/kota)",
                    values,
                    indicators_meta[ind_id]["polarity"],
                )
        conn.commit()
        print(f"       [OK] Canonical water & sanitation sets: {len(sdgs_rows)} verified rows")

    # 6b. Verified APM SMP & SMA/SMK from Kemendikdasmen Pusdatin (2024/2025).
    verified_apm_csv = REPO_ROOT / "data" / "kemendikdasmen_apm_smp_sma_2024_2025.csv"
    if verified_apm_csv.exists():
        with open(verified_apm_csv, "r", encoding="utf-8") as f:
            apm_rows = list(csv.DictReader(f))

        for ind_id in ("edu_net_enrollment_smp", "edu_net_enrollment_sma"):
            values = []
            for row in apm_rows:
                raw = (row.get(ind_id) or "").strip()
                if not raw:
                    continue
                try:
                    values.append((row["region_id"], float(raw), "VERIFIED"))
                except (KeyError, ValueError):
                    continue
            if values:
                _seed_facts(
                    ind_id,
                    2025,
                    "kemendikdasmen_apm_2024_2025",
                    "Kemendikdasmen APK/APM 2024/2025 (kab/kota)",
                    values,
                    indicators_meta[ind_id]["polarity"],
                )
        conn.commit()
        print(f"       [OK] Verified APM SMP & SMA: {len(apm_rows)} rows")

    # 6c. Verified disaster event frequency from BNPB DIBI (2020-2024).
    verified_events_csv = REPO_ROOT / "data" / "bnpb_events_5yr_kabkota_2020_2024.csv"
    if verified_events_csv.exists():
        with open(verified_events_csv, "r", encoding="utf-8") as f:
            event_rows = list(csv.DictReader(f))

        values = []
        for row in event_rows:
            raw = (row.get("dis_events_5yr_freq") or "").strip()
            if not raw:
                continue
            try:
                values.append((row["region_id"], float(raw), "VERIFIED"))
            except (KeyError, ValueError):
                continue
        if values:
            _seed_facts(
                "dis_events_5yr_freq",
                2024,
                "bnpb_dibi_kabkota_2024",
                "BNPB DIBI 2020-2024 (kab/kota)",
                values,
                indicators_meta["dis_events_5yr_freq"]["polarity"],
            )
        conn.commit()
        print(f"       [OK] Verified disaster event frequency: {len(event_rows)} rows")

    # 6d. Dependency ratio from BPS population projection (SP2020, 2026).
    verified_dependency_csv = REPO_ROOT / "data" / "bps_dependency_ratio_2026.csv"
    if verified_dependency_csv.exists():
        with open(verified_dependency_csv, "r", encoding="utf-8") as f:
            dependency_rows = list(csv.DictReader(f))

        values = []
        for row in dependency_rows:
            raw = (row.get("soc_dependency_ratio") or "").strip()
            if not raw:
                continue
            try:
                values.append((row["region_id"], float(raw), "DERIVED"))
            except (KeyError, ValueError):
                continue
        if values:
            _seed_facts(
                "soc_dependency_ratio",
                2026,
                "bps_proyeksi_penduduk_2026",
                "BPS Proyeksi Penduduk SP2020 2026 (kab/kota)",
                values,
                indicators_meta["soc_dependency_ratio"]["polarity"],
            )
        conn.commit()
        print(f"       [OK] Derived dependency ratio: {len(dependency_rows)} rows")

    # 6e. Province-level BPS indicators imputed to kab/kota (explicitly flagged).
    verified_province_csv = REPO_ROOT / "data" / "bps_province_internet_jkn_2024_2025.csv"
    if verified_province_csv.exists():
        with open(verified_province_csv, "r", encoding="utf-8") as f:
            province_rows = list(csv.DictReader(f))

        for ind_id, column, year, ds_id, source_label in (
            ("inf_internet_household_pct", "inf_internet_household_pct", 2024, "bps_susenas_tik_2024", "BPS Susenas 2024 (province-imputed)"),
            ("hlt_jkn_coverage_pct", "hlt_jkn_coverage_pct", 2025, "bps_susenas_jkn_2025", "BPS Susenas 2025 (province-imputed)"),
        ):
            values = []
            for row in province_rows:
                raw = (row.get(column) or "").strip()
                if not raw:
                    continue
                try:
                    values.append((row["region_id"], float(raw), "IMPUTED_PROVINCE"))
                except (KeyError, ValueError):
                    continue
            if values:
                _seed_facts(
                    ind_id,
                    year,
                    ds_id,
                    source_label,
                    values,
                    indicators_meta[ind_id]["polarity"],
                )
        conn.commit()
        print(f"       [OK] Province-imputed internet & JKN: {len(province_rows)} rows")

    # 6f. Province-imputed disaster impact per 10k population (BNPB DIBI 2025).
    verified_affected_csv = REPO_ROOT / "data" / "bnpb_affected_per_10k_2025.csv"
    if verified_affected_csv.exists():
        with open(verified_affected_csv, "r", encoding="utf-8") as f:
            affected_rows = list(csv.DictReader(f))

        values = []
        for row in affected_rows:
            raw = (row.get("dis_affected_pop_per_10k") or "").strip()
            if not raw:
                continue
            try:
                values.append((row["region_id"], float(raw), "IMPUTED_PROVINCE"))
            except (KeyError, ValueError):
                continue
        if values:
            _seed_facts(
                "dis_affected_pop_per_10k",
                2025,
                "bnpb_dibi_affected_2025",
                "BNPB DIBI 2025 (province-imputed)",
                values,
                indicators_meta["dis_affected_pop_per_10k"]["polarity"],
            )
        conn.commit()
        print(f"       [OK] Province-imputed disaster impact: {len(affected_rows)} rows")

    # 6g. Verified Kemendikdasmen education indicators (2025).
    # Mixed by indicator: NPD supplies the SD ratio; the 2025 statistics API
    # supplies exact classroom-condition counts for SD + SMP.
    verified_edu_csv = REPO_ROOT / "data" / "kemendikdasmen_edu_kabkota_2025.csv"
    if not verified_edu_csv.exists():
        print(f"[ERROR] Missing required Kemendikdasmen 2025 CSV: {verified_edu_csv}")
        sys.exit(1)
    with open(verified_edu_csv, "r", encoding="utf-8") as f:
        edu_rows = list(csv.DictReader(f))

    for ind_id, column, ds_id, label in (
        (
            "edu_student_teacher_ratio_sd",
            "edu_student_teacher_ratio_sd",
            "kemendikdasmen_npd_2025",
            "NPD 2025 — Rasio Pendidik : Peserta Didik SD (kab/kota)",
        ),
        (
            "edu_damaged_classrooms_pct",
            "edu_damaged_classrooms_pct",
            "kemendikdasmen_statistik_2025",
            "Kemendikdasmen 2025 — Ruang Kelas Menurut Kondisi, SD+SMP (kab/kota)",
        ),
    ):
        values = []
        for row in edu_rows:
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                values.append((row["region_id"], float(raw), "VERIFIED"))
            except (KeyError, ValueError):
                continue
        if len(values) != 514:
            print(
                f"[ERROR] {ind_id} coverage is {len(values)}/514; refusing partial education series."
            )
            sys.exit(1)
        _seed_facts(
            ind_id,
            2025,
            ds_id,
            label,
            values,
            indicators_meta[ind_id]["polarity"],
        )
    conn.commit()
    print(f"       [OK] Verified Kemendikdasmen 2025 education: {len(edu_rows)} rows")

    # 6h. Verified Kemenkes facilities per 10k (Puskesmas + SIRS hospitals).
    verified_health_csv = REPO_ROOT / "data" / "kemenkes_health_access_2026.csv"
    if verified_health_csv.exists():
        with open(verified_health_csv, "r", encoding="utf-8") as f:
            health_rows = list(csv.DictReader(f))

        for ind_id, column, ds_id, label in (
            (
                "hlt_facilities_per_10k",
                "hlt_facilities_per_10k",
                "kemenkes_sirs_regpus_2026",
                "Kemenkes Regpus Semester II 2025 + SIRS RS 2026 (kab/kota)",
            ),
            (
                "hlt_doctors_per_10k",
                "hlt_doctors_per_10k",
                "kemenkes_satusehat_dokter_2026",
                "SATUSEHAT Data 2026 (province-imputed)",
            ),
        ):
            values = []
            for row in health_rows:
                raw = (row.get(column) or "").strip()
                if not raw:
                    continue
                flag = (
                    "IMPUTED_PROVINCE"
                    if ind_id == "hlt_doctors_per_10k"
                    else "VERIFIED"
                )
                try:
                    values.append((row["region_id"], float(raw), flag))
                except (KeyError, ValueError):
                    continue
            if values:
                _seed_facts(
                    ind_id,
                    2026,
                    ds_id,
                    label,
                    values,
                    indicators_meta[ind_id]["polarity"],
                )
        conn.commit()
        print(f"       [OK] Verified Kemenkes health access: {len(health_rows)} rows")

    # 6b. Internal reliability indicators derived from the snapshot itself.
    # Completeness is measured against the public non-meta framework. Restricted
    # retired indicators are excluded so their absence does not punish regions.
    core_indicator_ids = [
        iid
        for iid in indicators_meta
        if not iid.startswith("meta_")
        and iid not in RETIRED_PUBLIC_INDICATORS
    ]
    completeness_by_region = {region["region_id"]: 0 for region in regions}
    years_by_region = {region["region_id"]: [] for region in regions}
    for rid, iid, year in conn.execute(
        "SELECT region_id, indicator_id, reference_year FROM fact_indicator_values WHERE snapshot_id = ?",
        (SNAPSHOT_ID,),
    ):
        if iid in core_indicator_ids and rid in completeness_by_region:
            completeness_by_region[rid] += 1
            years_by_region[rid].append(year)

    completeness_values = []
    freshness_values = []
    for region in regions:
        rid = region["region_id"]
        if core_indicator_ids:
            pct = completeness_by_region[rid] / len(core_indicator_ids) * 100.0
            completeness_values.append((rid, round(pct, 4), "DERIVED"))
        years = years_by_region[rid]
        if years:
            lag = 2026 - (sum(years) / len(years))
            freshness_values.append((rid, round(lag, 4), "DERIVED"))

    _seed_facts(
        "meta_indicator_completeness", 2026, "nusa_matra_internal_audit",
        "Internal snapshot completeness audit", completeness_values, "positive",
    )
    _seed_facts(
        "meta_freshness_lag_years", 2026, "nusa_matra_internal_audit",
        "Internal snapshot freshness audit", freshness_values, "negative",
    )

    # Mark indicators without observations as UNAVAILABLE instead of pretending they exist.
    for ind_id in indicators_meta:
        has_rows = conn.execute(
            "SELECT 1 FROM fact_indicator_values WHERE snapshot_id = ? AND indicator_id = ? LIMIT 1",
            (SNAPSHOT_ID, ind_id),
        ).fetchone()
        if not has_rows:
            conn.execute(
                "UPDATE dim_indicators SET availability_status = 'UNAVAILABLE' WHERE indicator_id = ?",
                (ind_id,),
            )

    conn.commit()

    # Freeze the staging facts into a digest-addressed immutable snapshot.
    previous_active = conn.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag = 'LIVE' AND is_active_default = 1 AND snapshot_id != ? "
        "LIMIT 1",
        (SNAPSHOT_ID,),
    ).fetchone()
    snapshot_result = finalize_staging_snapshot(
        conn,
        SNAPSHOT_ID,
        label="Nusa Matra Official LIVE Snapshot (BIG, BPS, BNPB, Kemenkes, Kemendikdasmen)",
        boundary_version=BOUNDARY_VER,
        notes=(
            "Verified official data compiled from primary government sources. "
            "Stunting uses Kemenkes SSGI 2024 (514/514 kab/kota), replacing SKI 2023."
        ),
        supersedes=previous_active[0] if previous_active else None,
    )
    final_snapshot_id = snapshot_result["snapshot_id"]
    mark_legacy_snapshots(conn)

    if not verify_content_digest(conn, final_snapshot_id):
        print("[ERROR] Snapshot content digest verification failed.")
        sys.exit(1)

    # Normalization audit: every observation must match its frozen bounds.
    normalization_errors = []
    for indicator_row in conn.execute(
        "SELECT indicator_id, polarity, national_min, national_max FROM dim_indicators"
    ):
        ind_id, polarity, national_min, national_max = indicator_row
        for rid, raw, stored in conn.execute(
            "SELECT region_id, raw_value, normalized_score FROM fact_indicator_values "
            "WHERE snapshot_id = ? AND indicator_id = ?",
            (final_snapshot_id, ind_id),
        ):
            expected = normalize_score(raw, national_min, national_max, polarity)
            if expected is None or abs(expected - stored) > 0.02:
                normalization_errors.append((ind_id, rid, raw, stored, expected))
    if normalization_errors:
        print(f"[ERROR] {len(normalization_errors)} normalization mismatches found.")
        for item in normalization_errors[:5]:
            print("       ", item)
        sys.exit(1)

    conn.execute("PRAGMA foreign_keys = ON")
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        print(f"[ERROR] Foreign key violations: {fk_violations[:5]}")
        sys.exit(1)

    final_facts = conn.execute(
        "SELECT COUNT(*) FROM fact_indicator_values WHERE snapshot_id = ?",
        (final_snapshot_id,),
    ).fetchone()[0]
    print(f"       [OK] {final_facts} fact rows in final snapshot")
    print(
        f"       [OK] Snapshot {final_snapshot_id} "
        f"content_sha256={snapshot_result['content_sha256'][:16]}..."
    )

    # Integrity verification
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM dim_regions")
    n_regions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM dim_indicators")
    n_indicators = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM fact_indicator_values WHERE snapshot_id = ?", (final_snapshot_id,))
    n_facts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT region_id) FROM fact_indicator_values WHERE snapshot_id = ?", (final_snapshot_id,))
    n_fact_regions = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT indicator_id FROM fact_indicator_values WHERE snapshot_id = ?)",
        (final_snapshot_id,),
    )
    n_fact_indicators = cursor.fetchone()[0]
    cursor.execute(
        "SELECT MAX(national_rank) FROM fact_indicator_values WHERE snapshot_id = ?",
        (final_snapshot_id,),
    )
    max_rank = cursor.fetchone()[0] or 0
    cursor.execute(
        """SELECT COUNT(DISTINCT f.region_id)
           FROM fact_indicator_values f
           JOIN dim_regions r ON r.region_id = f.region_id
           WHERE f.snapshot_id = ? AND r.level IN ('kabupaten', 'kota')""",
        (final_snapshot_id,),
    )
    n_kabkota_with_facts = cursor.fetchone()[0]

    conn.close()

    print("\n" + "=" * 70)
    print("Seeding Complete! Integrity Summary for LIVE Database:")
    print(f"- Output Database: {DB_PATH} ({os.path.getsize(DB_PATH):,} bytes)")
    print(f"- Snapshot ID:     {final_snapshot_id}")
    print(f"- Content SHA-256: {snapshot_result['content_sha256']}")
    print(f"- Metadata SHA-256: {snapshot_result['metadata_checksum']}")
    print(f"- Dim Regions:     {n_regions} (38 Prov + 514 Kab/Kota)")
    print(f"- Dim Indicators:  {n_indicators} catalog indicators")
    print(f"- Fact Values:     {n_facts:,} observations ({n_fact_indicators} indicators)")
    print(f"- Covered Regions: {n_fact_regions} regions with observations")
    print(f"- Kab/Kota coverage: {n_kabkota_with_facts}/514")
    print(f"- Max national_rank: {max_rank} (must be <= 514)")
    if n_kabkota_with_facts != 514 or max_rank > 514:
        print("[ERROR] LIVE database failed regional integrity checks.")
        sys.exit(1)
    print("=" * 70)

if __name__ == "__main__":
    main()
