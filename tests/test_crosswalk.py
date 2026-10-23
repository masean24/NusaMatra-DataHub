"""Tests for the deterministic agency-row → 2026 region crosswalk."""

from app.services.crosswalk_service import (
    canonical_name,
    crosswalk_rows,
    first_value,
    sort_vintages,
)


REGIONS = [
    {"region_id": "9301", "parent_region_id": "93", "bps_code": "9301", "name": "Kabupaten Merauke", "level": "kabupaten"},
    {"region_id": "9501", "parent_region_id": "95", "bps_code": "9501", "name": "Kabupaten Jayawijaya", "level": "kabupaten"},
    {"region_id": "9601", "parent_region_id": "96", "bps_code": "9601", "name": "Kabupaten Sorong", "level": "kabupaten"},
    {"region_id": "9671", "parent_region_id": "96", "bps_code": "9671", "name": "Kota Sorong", "level": "kota"},
    {"region_id": "7371", "parent_region_id": "73", "bps_code": "7371", "name": "Kota Makassar", "level": "kota"},
]


def test_legacy_code_does_not_override_name():
    """CSV 9501 is Merauke, but 2026 code 9501 is Jayawijaya. Name must win."""
    rows = [
        {"bps_code": "9501", "region_name": "Merauke", "soc_hdi": "72.73"},
    ]
    result = crosswalk_rows(rows, REGIONS)
    assert "9301" in result.covered_region_ids
    assert "9501" not in result.covered_region_ids


def test_kabupaten_kota_collision_resolved_by_level():
    rows = [
        {"bps_code": "9107", "region_name": "Sorong", "soc_hdi": "68.0"},
        {"bps_code": "9271", "region_name": "Kota Sorong", "soc_hdi": "75.0"},
    ]
    result = crosswalk_rows(rows, REGIONS)
    assert "9601" in result.covered_region_ids
    assert "9671" in result.covered_region_ids


def test_name_alias_resolves_common_spelling_difference():
    rows = [{"bps_code": "7371", "region_name": "Kota Makasar", "soc_hdi": "80.0"}]
    result = crosswalk_rows(rows, REGIONS)
    assert canonical_name("Kota Makasar") == canonical_name("Kota Makassar")
    assert "7371" in result.covered_region_ids


def test_unmatched_rows_are_reported():
    rows = [{"bps_code": "0000", "region_name": "Wilayah Tidak Ada", "soc_hdi": "1"}]
    result = crosswalk_rows(rows, REGIONS)
    assert result.unmatched and result.unmatched[0]["reason"] == "UNMATCHED"


def test_ignore_national_aggregate_row():
    rows = [{"bps_code": "9999", "region_name": "INDONESIA", "soc_hdi": "70"}]
    result = crosswalk_rows(rows, REGIONS)
    assert not result.rows_by_region
    assert not result.unmatched


def test_multi_vintage_merges_first_non_empty_value():
    rows = [
        {"bps_code": "9401", "region_name": "Merauke", "soc_hdi": ""},
        {"bps_code": "9501", "region_name": "Merauke", "soc_hdi": "72.73"},
    ]
    result = crosswalk_rows(rows, REGIONS)
    ordered = sort_vintages(result.rows_by_region["9301"], ["soc_hdi"], REGIONS[0])
    assert first_value(ordered, "soc_hdi") == "72.73"
    assert len(result.rows_by_region["9301"]) == 2
    assert "9301" in result.multi_vintage_region_ids
