#!/usr/bin/env python3
"""
Build verified Kemenkes health-access indicators at kabupaten/kota level.

Sources (official, public):
- Data Puskesmas Teregistrasi Semester II 2025 (Kepmenkes 314/2026, regpus)
- RS Online / SIRS public hospital list (rekap_rs_all)
- SATUSEHAT Data: Jumlah Dokter di Fasilitas Kesehatan (provinsi)
- BPS Proyeksi Penduduk SP2020 2026 for the denominator

Outputs:
- data/kemenkes_health_access_2026.csv
- data/kemenkes_health_access_2026.provenance.json

Indicators:
- hlt_facilities_per_10k: (Puskesmas + RS) / population * 10,000. Kab/kota.
- hlt_doctors_per_10k: doctors per 10,000 population. The only official
  public series is province-level, so kab/kota values are the province rate
  and are explicitly flagged IMPUTED_PROVINCE.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.crosswalk_service import canonical_name, crosswalk_rows

RAW_DIR = REPO_ROOT / "data" / "raw" / "kemenkes"
OUTPUT_CSV = REPO_ROOT / "data" / "kemenkes_health_access_2026.csv"
OUTPUT_MANIFEST = REPO_ROOT / "data" / "kemenkes_health_access_2026.provenance.json"
KAB_GEOJSON = REPO_ROOT / "data" / "boundaries" / "indonesia_kabupaten_low.geojson"
PROV_GEOJSON = REPO_ROOT / "data" / "boundaries" / "indonesia_provinsi_low.geojson"
POPULATION_CSV = REPO_ROOT / "data" / "bps_dependency_ratio_2026.csv"

PUSKESMAS_PDF_URL = (
    "https://regpus.kemkes.go.id/media/dokumen/publikasi/2026-04-23/"
    "KMK_No._HK.01.07-MENKES-314-2026_ttg_Data_PKM_Teregistrasi__nZUZbyn.pdf"
)
SIRS_HOSPITALS_URL = "https://sirs.kemkes.go.id/fo/home/rekap_rs_all?id=0"
SIRS_PROVINCES_URL = "https://sirs.kemkes.go.id/fo/home/list_prop_noncovid?id=0"
DOCTORS_CSV_URL = (
    "https://api.kemkes.go.id/satusehat-data/dataset/public/"
    "65cff906-5fd1-4f8d-baad-9f6ad837f5b8/csv"
)
# Public web-client key embedded in the SATUSEHAT Data frontend. Override with
# SATUSEHAT_DATA_KEY if Kemenkes rotates it.
SATUSEHAT_DATA_KEY = os.environ.get(
    "SATUSEHAT_DATA_KEY",
    "jGq8uLW1RdApDKD4Hk2aaS5hxwX01bcGzeWD4uYqSBuyWC6D",
)


def download(url: str, filename: str, headers: dict | None = None) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / filename
    if path.exists() and path.stat().st_size > 0:
        return path
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NusaMatra-DataHub/0.1.0", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        path.write_bytes(response.read())
    return path


def load_json_regions(path: Path, level: str) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    regions = []
    for feature in data["features"]:
        props = feature["properties"]
        if level == "provinsi":
            actual_level = "provinsi"
        else:
            actual_level = (
                "kota"
                if str(props.get("type", "")).lower() == "kota"
                or str(props["name"]).startswith("Kota")
                else "kabupaten"
            )
        regions.append(
            {
                "region_id": str(props["region_id"]),
                "parent_region_id": str(props.get("parent_region_id") or ""),
                "bps_code": str(props.get("bps_code") or ""),
                "name": props["name"],
                "level": actual_level,
            }
        )
    return regions


def parse_puskesmas(text: str) -> dict[str, dict]:
    pattern = re.compile(r"^\s*(\d{4})\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")
    rows = {}
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        kode, name, non_inap, inap, total = match.groups()
        if int(non_inap) + int(inap) != int(total):
            continue
        rows[kode] = {
            "name": name.strip(),
            "non_inap": int(non_inap),
            "inap": int(inap),
            "total": int(total),
        }
    return rows


def main() -> None:
    puskesmas_pdf = download(PUSKESMAS_PDF_URL, "puskesmas_semester_ii_2025.pdf")
    hospitals_json = download(SIRS_HOSPITALS_URL, "sirs_hospitals.json")
    provinces_json = download(SIRS_PROVINCES_URL, "sirs_provinces.json")
    doctors_csv = download(
        DOCTORS_CSV_URL,
        "satusehat_doctors_provinsi.csv",
        headers={"x-satudata-key": SATUSEHAT_DATA_KEY},
    )

    reader = PdfReader(str(puskesmas_pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    (RAW_DIR / "puskesmas_semester_ii_2025.txt").write_text(text, encoding="utf-8")
    puskesmas = parse_puskesmas(text)
    if len(puskesmas) != 514:
        raise SystemExit(f"Expected 514 Puskesmas kab/kota rows, got {len(puskesmas)}")

    kab_regions = load_json_regions(KAB_GEOJSON, "kabupaten")
    prov_regions = load_json_regions(PROV_GEOJSON, "provinsi")
    region_by_id = {region["region_id"]: region for region in kab_regions}

    missing_puskesmas = sorted(set(region_by_id) - set(puskesmas))
    if missing_puskesmas:
        raise SystemExit(f"Puskesmas rows missing for region_ids: {missing_puskesmas}")

    hospitals = json.loads(hospitals_json.read_text(encoding="utf-8"))["data"]
    provinces = json.loads(provinces_json.read_text(encoding="utf-8"))["provinsi"]

    province_prefix: dict[str, str] = {}
    for province in prov_regions:
        province_prefix[canonical_name(province["name"])] = str(province["region_id"])[:2]
    for province in provinces:
        province_prefix.setdefault(canonical_name(province["propinsi_name"]), str(province["kode"]))
    province_prefix["YOGYAKARTA"] = "34"
    province_prefix["DAERAHISTIMEWAYOGYAKARTA"] = "34"

    hospital_rows = [
        {
            "region_name": hospital.get("kab"),
            "bps_code": province_prefix.get(canonical_name(hospital.get("nama_prop")), ""),
        }
        for hospital in hospitals
    ]
    hospital_crosswalk = crosswalk_rows(hospital_rows, kab_regions)
    if hospital_crosswalk.unmatched or hospital_crosswalk.ambiguous:
        raise SystemExit(
            "SIRS hospital crosswalk incomplete: "
            f"unmatched={hospital_crosswalk.unmatched[:10]} "
            f"ambiguous={hospital_crosswalk.ambiguous[:10]}"
        )
    hospital_counts = {
        region_id: len(rows)
        for region_id, rows in hospital_crosswalk.rows_by_region.items()
    }

    population: dict[str, float] = {}
    with open(POPULATION_CSV, "r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("total_population") or "").strip()
            if raw:
                population[row["region_id"]] = float(raw)
    missing_population = sorted(set(region_by_id) - set(population))
    if missing_population:
        raise SystemExit(f"Population missing for region_ids: {missing_population}")

    province_population: dict[str, float] = {}
    for region_id, value in population.items():
        province_population[region_id[:2]] = province_population.get(region_id[:2], 0.0) + value

    doctor_rate_by_province: dict[str, float] = {}
    doctor_rows = list(csv.DictReader(doctors_csv.open(encoding="utf-8")))
    for row in doctor_rows:
        prefix = (row.get("kode_provinsi") or "").strip()
        if not prefix or prefix not in province_population:
            continue
        total_doctors = sum(
            float(row.get(column) or 0)
            for column in ("puskesmas", "rumah_sakit", "faskes_lainnya")
        )
        doctor_rate_by_province[prefix] = (
            total_doctors / province_population[prefix] * 10000.0
        )
    if not doctor_rate_by_province:
        raise SystemExit("No province-level doctor rates could be computed")

    output_rows = []
    for region_id in sorted(region_by_id):
        region = region_by_id[region_id]
        total_population = population[region_id]
        hospital_count = hospital_counts.get(region_id, 0)
        puskesmas_count = puskesmas[region_id]["total"]
        total_facilities = puskesmas_count + hospital_count
        doctor_rate = doctor_rate_by_province.get(region["parent_region_id"])
        output_rows.append(
            {
                "region_id": region_id,
                "region_name": region["name"],
                "hlt_facilities_per_10k": round(total_facilities / total_population * 10000.0, 4),
                "hlt_doctors_per_10k": round(doctor_rate, 4) if doctor_rate is not None else "",
                "puskesmas_count": puskesmas_count,
                "hospital_count": hospital_count,
                "total_facilities": total_facilities,
                "total_population": int(total_population),
                "reference_year": 2026,
                "doctor_quality_flag": "IMPUTED_PROVINCE" if doctor_rate is not None else "UNAVAILABLE",
                "source_label": (
                    "Kemenkes Regpus Semester II 2025 + SIRS RS 2026; "
                    "doctors province-imputed (SATUSEHAT Data)"
                ),
                "source_url": "https://sirs.kemkes.go.id/fo/home/dashboard_rs?id=0",
            }
        )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    raw_manifest = {}
    for key, path in (
        ("puskesmas_pdf", puskesmas_pdf),
        ("sirs_hospitals", hospitals_json),
        ("sirs_provinces", provinces_json),
        ("satusehat_doctors", doctors_csv),
    ):
        raw_manifest[key] = {
            "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }

    manifest = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "agency": "Kementerian Kesehatan RI",
        "sources": {
            "puskesmas": {
                "url": PUSKESMAS_PDF_URL,
                "title": "Data Puskesmas Teregistrasi Semester II Tahun 2025 (Kepmenkes 314/2026)",
            },
            "hospitals": {
                "url": SIRS_HOSPITALS_URL,
                "title": "RS Online / SIRS - List Rumah Sakit Nasional",
            },
            "doctors": {
                "url": DOCTORS_CSV_URL,
                "title": "SATUSEHAT Data - Jumlah Dokter di Fasilitas Kesehatan (per provinsi)",
            },
            "population": {
                "url": "https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/2790/",
                "title": "BPS Proyeksi Penduduk SP2020 2026 (kab/kota)",
            },
        },
        "raw_files": raw_manifest,
        "derived_csv": {
            "path": str(OUTPUT_CSV.relative_to(REPO_ROOT)).replace("\\", "/"),
            "rows": len(output_rows),
            "sha256": hashlib.sha256(OUTPUT_CSV.read_bytes()).hexdigest(),
        },
        "formulas": {
            "hlt_facilities_per_10k": "(Puskesmas + RS) / total population * 10,000.",
            "hlt_doctors_per_10k": (
                "Province doctor count / province population * 10,000; "
                "the same province rate is assigned to each kab/kota and flagged IMPUTED_PROVINCE."
            ),
        },
        "coverage": {
            "puskesmas_kabkota": len(puskesmas),
            "hospitals_total": len(hospitals),
            "hospital_regions": len(hospital_counts),
            "doctor_provinces": len(doctor_rate_by_province),
        },
        "notes": (
            "Facilities are verified at kab/kota. Doctors are officially available only "
            "at province level, so they are explicitly marked IMPUTED_PROVINCE rather than "
            "fabricating an intra-province distribution."
        ),
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {len(output_rows)} regions -> {OUTPUT_CSV}")
    print(f"[OK] hospitals={len(hospitals)} regions={len(hospital_counts)} doctors_provinces={len(doctor_rate_by_province)}")
    print(f"[OK] Provenance -> {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    main()
