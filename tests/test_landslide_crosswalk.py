"""Regression checks for the BNPB IRBI 2024 landslide crosswalk."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "data" / "verified_indicators_master.csv"
HAZARDS = ROOT / "data" / "bnpb_irbi_specific_hazards_2024.csv"
PROVINCES = ROOT / "data" / "bps_provincial_sdgs_2025.csv"


def _norm(value):
    value = (value or "").upper()
    value = value.replace("KABUPATEN", "").replace("KAB.", "").replace("KOTA", "")
    value = value.replace("ADM.", "").replace("ADMINISTRASI", "")
    return re.sub(r"[^A-Z0-9]", "", value)


def _level(value):
    return "kota" if (value or "").upper().startswith("KOTA") else "kabupaten"


def _read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


PROVINCE_ALIASES = {
    "DAERAHISTIMEWAYOGYAKARTA": "DIYOGYAKARTA",
    "KEPULAUANBANGKABELITUNG": "KEPBANGKABELITUNG",
    "KEPULAUANRIAU": "KEPRIAU",
}


def test_landslide_values_are_joined_by_province_and_level():
    province_prefixes = {
        _norm(row["province_name"]): row["bps_prov_code"][:2]
        for row in _read(PROVINCES)
    }
    source = {}
    for row in _read(HAZARDS):
        key = _norm(row["province_name"])
        prefix = province_prefixes.get(PROVINCE_ALIASES.get(key, key))
        if prefix is None:
            continue
        source[(prefix, _level(row["region_name"]), _norm(row["region_name"]))] = row
    master = {
        (
            row["bps_code"][:2],
            _level(row["region_name"]),
            _norm(row["region_name"]),
        ): row
        for row in _read(MASTER)
    }

    duplicate_names = {
        _norm(row["region_name"])
        for row in source.values()
        if sum(
            1
            for other in source.values()
            if _norm(other["region_name"]) == _norm(row["region_name"])
        )
        > 1
    }
    assert len(duplicate_names) == 26

    checked = 0
    for key, source_row in source.items():
        if _norm(source_row["region_name"]) not in duplicate_names:
            continue
        master_row = master.get(key)
        assert master_row is not None, f"missing master row for {key}"
        assert master_row["dis_landslide_score"] == source_row["dis_landslide_score"], key
        assert master_row["dis_landslide_class"] == source_row["dis_landslide_class"], key
        checked += 1

    assert checked >= 52
