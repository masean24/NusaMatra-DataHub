"""
Deterministic crosswalk between external agency rows and canonical 2026 regions.

The external master CSV (BPS/BNPB/Kemenkes/Kemendikdasmen) was compiled over
several years. Its ``bps_code`` column contains legacy BPS codes that collide
with 2026 Kemendagri codes for *different* regions (for example CSV ``9501`` is
Merauke, while the 2026 boundary uses ``9501`` for Jayawijaya).

Resolving by code alone therefore injects data into the wrong regency. This
module resolves rows by normalized name + level + province prefix, keeps every
matched vintage for per-indicator merging, and reports unmatched/ambiguous rows
for the ETL quarantine table.

Pure functions only: no database or app dependencies, so it is trivially
testable and reusable by the seeder.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


# Manual aliases for source names that differ from the official 2026 names.
# Keys and values are already-normalized names.
NAME_ALIASES: dict[str, str] = {
    "TOBASAMOSIRTOBA": "TOBA",
    "TOBASAMOSIR": "TOBA",
    "KEPSERIBU": "KEPULAUANSERIBU",
    "MAKASAR": "MAKASSAR",
    "MAMUJUUTARAPASANGKAYU": "PASANGKAYU",
    "MAMUJUUTARA": "PASANGKAYU",
    "MALUKUTENGGARABARATKEPULAUANTANIMBAR": "KEPULAUANTANIMBAR",
    "MALUKUTENGGARABARAT": "KEPULAUANTANIMBAR",
    "SIAUTAGULANDANGBIARO": "KEPSIAUTAGULANDANGBIARO",
    "SITAROSIAUTAGULANDANGBIARO": "KEPSIAUTAGULANDANGBIARO",
    "SITARO": "KEPSIAUTAGULANDANGBIARO",
    "PADANGSIDIMPUAN": "PADANGSIDEMPUAN",
}


def normalize_name(name: str | None) -> str:
    """Uppercase and strip administrative prefixes/punctuation for matching."""
    if not name:
        return ""
    value = name.upper()
    value = re.sub(r"\bKAB\.?\b", "", value)
    value = value.replace("KABUPATEN", "").replace("KAB.", "").replace("KOTA", "")
    value = value.replace("ADM.", "").replace("ADMINISTRASI", "")
    return re.sub(r"[^A-Z0-9]", "", value)


def canonical_name(name: str | None) -> str:
    normalized = normalize_name(name)
    return NAME_ALIASES.get(normalized, normalized)


def _row_level(row: Mapping[str, Any]) -> str:
    name = (row.get("region_name") or "").upper()
    return "kota" if name.startswith("KOTA") else "kabupaten"


@dataclass
class CrosswalkResult:
    """Outcome of mapping source rows onto canonical regions."""

    rows_by_region: dict[str, list[Mapping[str, Any]]] = field(default_factory=dict)
    unmatched: list[dict[str, Any]] = field(default_factory=list)
    ambiguous: list[dict[str, Any]] = field(default_factory=list)
    region_codes: dict[str, list[str]] = field(default_factory=dict)

    @property
    def covered_region_ids(self) -> set[str]:
        return set(self.rows_by_region)

    @property
    def multi_vintage_region_ids(self) -> list[str]:
        return [rid for rid, rows in self.rows_by_region.items() if len(rows) > 1]


def build_region_index(
    regions: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, list[Mapping[str, Any]]], dict[str, Mapping[str, Any]]]:
    """Index regions by canonical name and by region_id."""
    by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_id: dict[str, Mapping[str, Any]] = {}
    for region in regions:
        by_name[canonical_name(region["name"])].append(region)
        by_id[region["region_id"]] = region
    return by_name, by_id


def resolve_region(
    row: Mapping[str, Any],
    by_name: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[Mapping[str, Any] | None, str | None]:
    """
    Resolve one source row to a canonical region.

    Returns ``(region, error)`` where error is ``None``, ``"UNMATCHED"`` or
    ``"AMBIGUOUS"``.
    """
    key = canonical_name(row.get("region_name"))
    candidates = list(by_name.get(key, []))
    if not candidates:
        return None, "UNMATCHED"

    if len(candidates) == 1:
        return candidates[0], None

    level = _row_level(row)
    same_level = [c for c in candidates if c.get("level") == level]
    if len(same_level) == 1:
        return same_level[0], None

    pool = same_level or candidates
    source_prefix = str(row.get("bps_code") or "")[:2]
    same_province = [c for c in pool if str(c.get("parent_region_id") or "") == source_prefix]
    if len(same_province) == 1:
        return same_province[0], None

    return None, "AMBIGUOUS"


def crosswalk_rows(
    source_rows: Sequence[Mapping[str, Any]],
    regions: Sequence[Mapping[str, Any]],
    *,
    ignore_codes: Sequence[str] = ("9999",),
) -> CrosswalkResult:
    """Map every source row to a canonical region and group vintages."""
    by_name, _ = build_region_index(regions)
    result = CrosswalkResult()

    for row in source_rows:
        code = str(row.get("bps_code") or "").strip()
        if code in ignore_codes:
            continue

        region, error = resolve_region(row, by_name)
        if region is None:
            payload = {
                "bps_code": code,
                "region_name": row.get("region_name"),
                "reason": error,
            }
            if error == "AMBIGUOUS":
                candidates = by_name.get(canonical_name(row.get("region_name")), [])
                payload["candidates"] = [
                    {"region_id": c["region_id"], "name": c["name"], "level": c["level"]}
                    for c in candidates
                ]
                result.ambiguous.append(payload)
            else:
                result.unmatched.append(payload)
            continue

        region_id = str(region["region_id"])
        result.rows_by_region.setdefault(region_id, []).append(row)
        result.region_codes.setdefault(region_id, []).append(code)

    return result


def count_non_empty_values(row: Mapping[str, Any], columns: Iterable[str]) -> int:
    return sum(1 for column in columns if str(row.get(column) or "").strip())


def sort_vintages(
    rows: Sequence[Mapping[str, Any]],
    columns: Iterable[str],
    region: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """
    Order multiple source vintages for a region.

    Preference: row whose code prefix equals the region's parent province,
    then rows with more populated indicator columns, then the higher (newer)
    code. This keeps merging deterministic without dropping usable data.
    """
    columns = list(columns)
    parent = str(region.get("parent_region_id") or "")

    def key(row: Mapping[str, Any]):
        code = str(row.get("bps_code") or "")
        province_match = 0 if code[:2] == parent else 1
        non_empty = count_non_empty_values(row, columns)
        try:
            numeric_code = int(code)
        except ValueError:
            numeric_code = 0
        return (province_match, -non_empty, -numeric_code)

    return sorted(rows, key=key)


def first_value(
    rows: Sequence[Mapping[str, Any]],
    column: str,
) -> str | None:
    """Return the first non-empty raw value for a column across ordered vintages."""
    for row in rows:
        value = row.get(column)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None
