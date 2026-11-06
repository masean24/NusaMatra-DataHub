"""Contract tests for the source-link reference overlay."""

import shutil
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.services.snapshot_integrity import verify_content_digest
from app.services.source_link_registry import (
    REFERENCE_VERSION,
    indicator_source,
    resolved_dataset_id,
)

LIVE_DB = Path(__file__).resolve().parent.parent / "data" / "nusa_matra_live.db"


@pytest_asyncio.fixture
async def live_client(monkeypatch):
    if not LIVE_DB.exists():
        pytest.skip("LIVE database not generated")
    monkeypatch.setattr(settings, "live_database_path", str(LIVE_DB))
    monkeypatch.setattr(settings, "enable_live_mode", True)
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def _clone_snapshot(conn, source_id: str, target_id: str) -> None:
    columns = [
        row[1]
        for row in conn.execute("PRAGMA table_info(data_snapshots)").fetchall()
    ]
    row = conn.execute(
        "SELECT * FROM data_snapshots WHERE snapshot_id = ?", (source_id,)
    ).fetchone()
    values = list(row)
    values[columns.index("snapshot_id")] = target_id
    values[columns.index("is_active_default")] = 0
    placeholders = ",".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO data_snapshots ({','.join(columns)}) VALUES ({placeholders})",
        values,
    )

    indicator_columns = [
        row[1]
        for row in conn.execute("PRAGMA table_info(snapshot_indicators)").fetchall()
    ]
    other_indicator_columns = [
        column for column in indicator_columns if column != "snapshot_id"
    ]
    conn.execute(
        "INSERT INTO snapshot_indicators (snapshot_id,"
        + ",".join(other_indicator_columns)
        + ") SELECT ?,"
        + ",".join(other_indicator_columns)
        + " FROM snapshot_indicators WHERE snapshot_id = ?",
        (target_id, source_id),
    )

    fact_columns = [
        row[1]
        for row in conn.execute("PRAGMA table_info(fact_indicator_values)").fetchall()
    ]
    other_fact_columns = [
        column for column in fact_columns if column != "snapshot_id"
    ]
    conn.execute(
        "INSERT INTO fact_indicator_values (snapshot_id,"
        + ",".join(other_fact_columns)
        + ") SELECT ?,"
        + ",".join(other_fact_columns)
        + " FROM fact_indicator_values WHERE snapshot_id = ?",
        (target_id, source_id),
    )


@pytest_asyncio.fixture
async def five_snapshot_client(tmp_path, monkeypatch):
    if not LIVE_DB.exists():
        pytest.skip("LIVE database not generated")
    db_path = tmp_path / "five_snapshots.db"
    shutil.copy2(LIVE_DB, db_path)

    conn = sqlite3.connect(db_path)
    source_id = conn.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE content_sha256 IS NOT NULL ORDER BY created_at DESC LIMIT 1"
    ).fetchone()[0]
    snapshot_ids = [source_id]
    for index in range(1, 5):
        target_id = f"2026.10.0-live-fixture-{index}"
        _clone_snapshot(conn, source_id, target_id)
        snapshot_ids.append(target_id)
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings, "live_database_path", str(db_path))
    monkeypatch.setattr(settings, "enable_live_mode", True)
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, snapshot_ids


def test_registry_contract_exceptions():
    assert indicator_source("hlt_facilities_per_10k").url is None
    assert (
        indicator_source("hlt_facilities_per_10k").verification
        == "problem_unresolved"
    )
    assert indicator_source("dis_landslide_hazard_idx").verification == "pending"
    assert indicator_source("hlt_jkn_coverage_pct").verification == "verified"
    assert indicator_source("meta_freshness_lag_years").verification == "not_applicable"
    assert (
        resolved_dataset_id(
            "inf_safe_water_pct", "9507", "bps_provincial_sdgs_2025"
        )
        == "bps_provincial_sdgs_2025"
    )
    assert (
        resolved_dataset_id(
            "inf_safe_water_pct", "3201", "bps_sdgs_kabkota_2025"
        )
        == "bps_sdgs_kabkota_2025"
    )
    assert (
        resolved_dataset_id(
            "edu_mean_years_schooling", "3201", "bps_susenas_sakernas_2025"
        )
        == "bps_ipm_2025"
    )


@pytest.mark.asyncio
async def test_catalog_uses_resolved_source_links(client):
    resp = await client.get("/api/v1/indicators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["reference_version"] == REFERENCE_VERSION

    rows = {
        item["indicator_id"]: item
        for items in body["data"].values()
        for item in items
    }
    item = rows["edu_mean_years_schooling"]
    assert item["provenance"]["dataset_id"] == "bps_ipm_2025"
    assert item["provenance"]["source_link_level"] == "publication"
    assert "indeks-pembangunan-manusia-2025" in item["provenance"]["official_portal_url"]

    facilities = rows["hlt_facilities_per_10k"]["provenance"]
    assert facilities["official_portal_url"] is None
    assert facilities["source_link_level"] is None
    assert facilities["source_verification"] == "problem_unresolved"
    assert rows["dis_landslide_hazard_idx"]["provenance"]["source_verification"] == "pending"
    assert rows["dis_events_5yr_freq"]["provenance"]["verification_scope"] == "all_rows"
    assert rows["edu_net_enrollment_sma"]["provenance"]["verification_scope"] == "all_rows"
    assert rows["hlt_jkn_coverage_pct"]["provenance"]["verification_scope"] == "sample"
    assert rows["dis_affected_pop_per_10k"]["provenance"]["verification_scope"] == "province_level"


@pytest.mark.asyncio
async def test_region_detail_uses_aliases_and_fact_dataset(client):
    resp = await client.get("/api/v1/regions/3201")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert resp.json()["meta"]["reference_version"] == REFERENCE_VERSION

    rows = {item["indicator_id"]: item for item in data["indicators"]}
    edu = rows["edu_mean_years_schooling"]["provenance"]
    assert edu["dataset_id"] == "bps_ipm_2025"
    assert edu["official_url"] == edu["official_portal_url"]
    assert edu["source_link_level"] == "publication"

    facilities = rows["hlt_facilities_per_10k"]["provenance"]
    assert facilities["official_url"] is None
    assert facilities["official_portal_url"] is None
    assert facilities["source_verification"] == "problem_unresolved"


@pytest.mark.asyncio
async def test_dataset_catalog_uses_dataset_registry(live_client):
    resp = await live_client.get("/api/v1/datasets", params={"mode": "live"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["reference_version"] == REFERENCE_VERSION
    rows = {item["dataset_id"]: item for item in body["data"]}

    assert rows["big_batas_2026"]["official_portal_url"].endswith("/MapServer")
    assert rows["nusa_matra_internal_audit"]["official_portal_url"] is None
    assert rows["bps_susenas_sakernas_2025"]["official_portal_url"] is None
    assert rows["bps_sdgs_kabkota_2025"]["source_verification"] == "pending"
    assert rows["bps_ipm_2025"]["source_verification"] == "verified"
    assert rows["bps_ipm_2025"]["verification_scope"] == "sample"
    assert rows["kemendikdasmen_apm_2024_2025"]["verification_scope"] == "all_rows"


def test_retired_sources_do_not_use_old_portals():
    for indicator_id in (
        "inf_asphalt_road_village_pct",
        "meta_dapodik_sync_rate",
        "edu_school_travel_time_p90",
        "hlt_realtime_icu_occupancy",
    ):
        link = indicator_source(indicator_id)
        assert link is not None
        assert link.url is None
        assert link.level is None
        assert "tidak dipublikasikan" in link.note_idn


def test_sanitation_note_does_not_describe_water_exception():
    note = indicator_source("inf_safe_sanitation_pct").note_idn
    assert "9507" not in note
    assert "air" not in note.lower()


def test_public_notes_do_not_leak_sample_region_values():
    notes = []
    for record_type, record_id in (
        ("indicator", "dis_landslide_hazard_idx"),
        ("indicator", "hlt_jkn_coverage_pct"),
        ("indicator", "soc_poverty_severity_p2"),
        ("indicator", "hlt_facilities_per_10k"),
        ("indicator", "soc_dependency_ratio"),
        ("indicator", "inf_safe_water_pct"),
    ):
        link = (
            indicator_source(record_id)
            if record_type == "indicator"
            else dataset_source(record_id)
        )
        notes.extend([link.note_idn or "", link.note_en or ""])
    joined = " ".join(notes)
    for token in (
        "70,62",
        "70.62",
        "0,23",
        "0.23",
        "13,74",
        "13.74",
        "0.2309",
        "3201",
        "9507",
        "1229",
        "Bogor",
        "Jawa Barat",
    ):
        assert token not in joined, token


def test_verified_records_label_their_scope():
    all_rows = indicator_source("dis_events_5yr_freq")
    assert all_rows.verification == "verified"
    assert all_rows.verification_scope == "all_rows"
    assert "seluruh baris" in all_rows.note_idn.lower()

    sample = indicator_source("soc_poverty_severity_p2")
    assert sample.verification == "verified"
    assert sample.verification_scope == "sample"
    assert "satu baris contoh" in sample.note_idn.lower()

    province = indicator_source("dis_affected_pop_per_10k")
    assert province.verification == "verified"
    assert province.verification_scope == "province_level"
    assert "nilai provinsi cocok" in province.note_idn.lower()


def test_all_registry_records_have_honest_verification_status():
    for record_type, record_id in (
        ("indicator", "dis_earthquake_hazard_idx"),
        ("indicator", "dis_flood_hazard_idx"),
        ("indicator", "dis_multihazard_index"),
        ("indicator", "hlt_stunting_prevalence"),
        ("indicator", "edu_damaged_classrooms_pct"),
        ("indicator", "inf_safe_sanitation_pct"),
        ("indicator", "inf_safe_water_pct"),
    ):
        link = indicator_source(record_id)
        assert link.verification in {"pending", "partial"}
        assert "belum" in link.note_idn.lower()


@pytest.mark.asyncio
async def test_overlay_on_five_snapshot_fixture(five_snapshot_client):
    client, snapshot_ids = five_snapshot_client
    observed_hashes = set()
    for snapshot_id in snapshot_ids:
        catalog = await client.get(
            "/api/v1/indicators",
            params={"mode": "live", "snapshot_id": snapshot_id},
        )
        assert catalog.status_code == 200, catalog.text
        body = catalog.json()
        assert body["meta"]["reference_version"] == REFERENCE_VERSION
        observed_hashes.add(body["meta"]["content_sha256"])

        datasets = await client.get(
            "/api/v1/datasets",
            params={"mode": "live", "snapshot_id": snapshot_id},
        )
        assert datasets.status_code == 200
        assert datasets.json()["meta"]["reference_version"] == REFERENCE_VERSION

        region = await client.get(
            "/api/v1/regions/3201",
            params={"mode": "live", "snapshot_id": snapshot_id},
        )
        assert region.status_code == 200
        assert region.json()["meta"]["reference_version"] == REFERENCE_VERSION

    assert len(observed_hashes) == 1


def test_live_snapshots_keep_their_digests():
    if not LIVE_DB.exists():
        pytest.skip("LIVE database not generated")

    conn = sqlite3.connect(LIVE_DB)
    snapshots = [
        row[0]
        for row in conn.execute(
            "SELECT snapshot_id FROM data_snapshots WHERE content_sha256 IS NOT NULL"
        ).fetchall()
    ]
    if len(snapshots) < 5:
        pytest.skip("five snapshots are only present on the persistent LIVE database")
    for snapshot_id in snapshots:
        assert verify_content_digest(conn, snapshot_id) is True, snapshot_id
    conn.close()
