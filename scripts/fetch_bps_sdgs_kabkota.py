#!/usr/bin/env python3
"""
Fetch BPS Susenas 2025 kabupaten/kota water & sanitation data and build the
verified CSV consumed by the LIVE seeder.

Source (official BPS WebAPI):
- var 2830: Persentase Rumah Tangga dengan Akses Sumber Air Minum Layak
- var 2748: Persentase Rumah Tangga dengan Akses Sanitasi Layak
- domain 0000, year id 125 (2025)

The source API still uses some legacy BPS region codes. Rows are crosswalked to
the canonical 2026 region_ids by name + level + province prefix before writing.

Environment:
    BPS_API_KEY or NM_BPS_API_KEY (or BPS_API_KEY in .env)
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.crosswalk_service import crosswalk_rows

YEAR_ID = 125
DOMAIN = "0000"
API_BASE = "https://webapi.bps.go.id/v1/api/list/model/data/domain"
RAW_DIR = REPO_ROOT / "data" / "raw" / "bps"
OUTPUT_CSV = REPO_ROOT / "data" / "bps_kabkota_water_sanitation_2025.csv"
OUTPUT_MANIFEST = REPO_ROOT / "data" / "bps_kabkota_water_sanitation_2025.provenance.json"
KAB_GEOJSON = REPO_ROOT / "data" / "boundaries" / "indonesia_kabupaten_low.geojson"

VARIABLES = {
    "inf_safe_water_pct": {
        "var_id": 2830,
        "title": "Persentase Rumah Tangga yang Memiliki Akses terhadap Sumber Air Minum Layak menurut Kabupaten/Kota",
    },
    "inf_safe_sanitation_pct": {
        "var_id": 2748,
        "title": "6.2.1 Persentase rumah tangga yang memiliki akses terhadap sanitasi layak menurut kabupaten/kota",
    },
}


def get_api_key() -> str:
    key = os.environ.get("BPS_API_KEY") or os.environ.get("NM_BPS_API_KEY")
    if key:
        return key.strip()

    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(("BPS_API_KEY=", "NM_BPS_API_KEY=")):
                return line.split("=", 1)[1].strip()

    raise SystemExit("BPS_API_KEY is not configured (env or .env).")


def fetch_variable(api_key: str, var_id: int) -> dict:
    url = f"{API_BASE}/{DOMAIN}/var/{var_id}/th/{YEAR_ID}/key/{api_key}/"
    request = urllib.request.Request(url, headers={"User-Agent": "NusaMatra-DataHub/0.1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "OK" or payload.get("data-availability") != "available":
        raise SystemExit(f"BPS var {var_id} th {YEAR_ID} is not available.")
    return payload


def parse_values(payload: dict, var_id: int) -> tuple[dict[str, str], dict[str, float]]:
    labels = {str(item["val"]): item["label"] for item in payload.get("vervar", [])}
    values: dict[str, float] = {}
    for key, value in payload.get("datacontent", {}).items():
        key = str(key)
        code = key[:4]
        if key[4:8] != str(var_id) or value is None:
            continue
        values[code] = float(value)
    return labels, values


def load_regions() -> list[dict]:
    data = json.loads(KAB_GEOJSON.read_text(encoding="utf-8"))
    regions = []
    for feature in data["features"]:
        props = feature["properties"]
        regions.append(
            {
                "region_id": str(props["region_id"]),
                "parent_region_id": str(props["parent_region_id"]),
                "bps_code": str(props["bps_code"]),
                "name": props["name"],
                "level": "kota" if str(props.get("type", "")).lower() == "kota" else "kabupaten",
            }
        )
    return regions


def main() -> None:
    api_key = get_api_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    payloads: dict[int, dict] = {}
    parsed: dict[str, dict[str, float]] = {}
    labels: dict[str, str] = {}
    raw_manifest: dict[str, dict] = {}

    for indicator_id, meta in VARIABLES.items():
        var_id = meta["var_id"]
        payload = fetch_variable(api_key, var_id)
        payloads[var_id] = payload
        indicator_labels, values = parse_values(payload, var_id)
        labels.update(indicator_labels)
        parsed[indicator_id] = values

        raw_path = RAW_DIR / f"var_{var_id}_th_{YEAR_ID}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        raw_manifest[indicator_id] = {
            "path": str(raw_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "bytes": raw_path.stat().st_size,
        }

    source_rows = []
    for code, label in labels.items():
        row = {"bps_code": code, "region_name": label}
        for indicator_id in VARIABLES:
            row[indicator_id] = parsed[indicator_id].get(code)
        source_rows.append(row)

    regions = load_regions()
    crosswalk = crosswalk_rows(source_rows, regions)
    if crosswalk.unmatched or crosswalk.ambiguous or len(crosswalk.covered_region_ids) != len(regions):
        raise SystemExit(
            f"Crosswalk incomplete: covered={len(crosswalk.covered_region_ids)}/{len(regions)} "
            f"unmatched={crosswalk.unmatched} ambiguous={crosswalk.ambiguous}"
        )

    row_by_region: dict[str, dict] = {}
    for code in labels:
        source_row = next(row for row in source_rows if row["bps_code"] == code)
        region_id = next(
            (rid for rid, rows in crosswalk.rows_by_region.items() if source_row in rows),
            None,
        )
        if region_id:
            row_by_region[region_id] = source_row

    region_by_id = {region["region_id"]: region for region in regions}
    output_rows = []
    for region_id in sorted(row_by_region):
        source = row_by_region[region_id]
        region = region_by_id[region_id]
        output_rows.append(
            {
                "region_id": region_id,
                "bps_code": region["bps_code"],
                "region_name": region["name"],
                "inf_safe_water_pct": source["inf_safe_water_pct"] if source["inf_safe_water_pct"] is not None else "",
                "inf_safe_sanitation_pct": source["inf_safe_sanitation_pct"] if source["inf_safe_sanitation_pct"] is not None else "",
                "year": YEAR_ID,
                "source": "BPS Susenas 2025",
                "source_url": f"https://webapi.bps.go.id/v1/api/list/model/data/domain/{DOMAIN}/",
            }
        )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    manifest = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "agency": "Badan Pusat Statistik (BPS)",
        "source": "BPS WebAPI",
        "domain": DOMAIN,
        "year_id": YEAR_ID,
        "variables": {key: value for key, value in VARIABLES.items()},
        "raw_files": raw_manifest,
        "derived_csv": {
            "path": str(OUTPUT_CSV.relative_to(REPO_ROOT)).replace("\\", "/"),
            "rows": len(output_rows),
            "sha256": hashlib.sha256(OUTPUT_CSV.read_bytes()).hexdigest(),
        },
        "notes": (
            "Values are BPS Susenas 2025 kabupaten/kota. Source bps_code values were "
            "crosswalked to 2026 Kemendagri codes by name+level+province; the derived "
            "CSV is keyed by canonical region_id."
        ),
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] {len(output_rows)} regions written to {OUTPUT_CSV}")
    print(f"[OK] Provenance manifest: {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    main()
