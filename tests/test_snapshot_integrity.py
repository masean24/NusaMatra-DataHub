"""Immutable snapshot digest, pinning, and metadata consistency tests."""

import sqlite3
from pathlib import Path

import pytest

from app.services.snapshot_integrity import (
    SNAPSHOT_ID_PREFIX,
    compute_content_digest,
    compute_metadata_checksum,
    ensure_snapshot_schema,
    finalize_staging_snapshot,
    mark_legacy_snapshots,
    populate_snapshot_indicators,
    verify_content_digest,
)

MIGRATION = Path(__file__).parent.parent / "migrations" / "001_init_schema.sql"
STAGING = "__test_staging__"


def _new_staging(conn: sqlite3.Connection, staging_id: str) -> None:
    conn.execute(
        """
        INSERT INTO data_snapshots (
            snapshot_id, label, environment_tag, is_active_default,
            boundary_version, manifest_checksum, notes, published_at,
            content_hash_spec, is_immutable, is_reproducible, methodology_version
        ) VALUES (?, 'test', 'LIVE', 0, 'BIG-TEST', 'metadata-placeholder',
                  'test staging', datetime('now'), 'canonical-json-v1', 0, 0,
                  'v2.2-minmax-full-range')
        """,
        (staging_id,),
    )


def _add_fact(
    conn: sqlite3.Connection,
    staging_id: str,
    raw_value: float,
    normalized_score: float = 50.0,
) -> None:
    conn.execute(
        """
        INSERT INTO fact_indicator_values (
            snapshot_id, region_id, indicator_id, reference_year, raw_value,
            normalized_score, national_percentile, national_rank, quality_flag,
            dataset_id, source_record_ref
        ) VALUES (?, '1101', 'test_indicator', 2025, ?, ?, 50.0, 1,
                  'VERIFIED', 'test_dataset', 'unit-test')
        """,
        (staging_id, raw_value, normalized_score),
    )


def _new_database(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "snapshot.db")
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    ensure_snapshot_schema(conn)
    conn.execute(
        """INSERT INTO dim_datasets
           (dataset_id, agency_code, agency_name, dataset_title,
            official_portal_url, api_or_download_url, access_method,
            license_name, update_frequency, last_ingested_at,
            raw_archive_uri, raw_sha256)
           VALUES ('test_dataset', 'TEST', 'Test Agency', 'Test Dataset',
                   'https://example.test', 'https://example.test/api',
                   'REST_API', 'Open', 'Tahunan', '2026-01-01',
                   '/raw/test', 'raw-sha256')"""
    )
    conn.execute(
        """INSERT INTO dim_regions
           (region_id, parent_region_id, level, name, short_name,
            kemendagri_code, bps_code, island_group, area_km2,
            label_lat, label_lng, boundary_version)
           VALUES ('1101', NULL, 'kabupaten', 'Test Region', 'Test',
                   '11.01', '1101', 'Sumatera', 100.0, 4.0, 96.0, 'BIG-TEST')"""
    )
    conn.execute(
        """INSERT INTO dim_indicators
           (indicator_id, indicator_name, category, unit, polarity,
            availability_status, primary_dataset_id, derivation_formula,
            description)
           VALUES ('test_indicator', 'Test Indicator', 'socioeconomic',
                   'percent (%)', 'positive', 'DIRECT', 'test_dataset',
                   'raw value', 'Test Indicator')"""
    )
    conn.commit()
    return conn


def _finalize(conn: sqlite3.Connection, staging_id: str) -> dict:
    populate_snapshot_indicators(conn, staging_id)
    return finalize_staging_snapshot(
        conn,
        staging_id,
        label="Test immutable snapshot",
        boundary_version="BIG-TEST",
        notes="unit test",
        supersedes=None,
    )


def test_digest_is_stable_and_changes_when_observation_changes(tmp_path):
    conn = _new_database(tmp_path)
    _new_staging(conn, STAGING)
    _add_fact(conn, STAGING, raw_value=10.0, normalized_score=90.0)
    conn.commit()

    result = _finalize(conn, STAGING)
    snapshot_id = result["snapshot_id"]
    digest = result["content_sha256"]
    metadata = result["metadata_checksum"]

    assert snapshot_id.startswith(SNAPSHOT_ID_PREFIX)
    assert snapshot_id.endswith(digest[:16])
    assert verify_content_digest(conn, snapshot_id)

    # Same canonical state -> same digest.
    assert compute_content_digest(conn, snapshot_id) == digest
    assert compute_metadata_checksum(conn, snapshot_id) == metadata

    conn.execute(
        "UPDATE fact_indicator_values SET raw_value = 11.0, normalized_score = 80.0 "
        "WHERE snapshot_id = ?",
        (snapshot_id,),
    )
    conn.commit()
    populate_snapshot_indicators(conn, snapshot_id)

    changed_digest = compute_content_digest(conn, snapshot_id)
    assert changed_digest != digest
    assert compute_metadata_checksum(conn, snapshot_id) == metadata
    assert not verify_content_digest(conn, snapshot_id)
    conn.close()


def test_two_snapshots_can_differ_and_remain_pinned(tmp_path):
    conn = _new_database(tmp_path)
    _new_staging(conn, STAGING)
    _add_fact(conn, STAGING, raw_value=10.0, normalized_score=90.0)
    conn.commit()
    first = _finalize(conn, STAGING)

    _new_staging(conn, STAGING)
    _add_fact(conn, STAGING, raw_value=20.0, normalized_score=10.0)
    conn.commit()
    second = _finalize(conn, STAGING)

    assert first["snapshot_id"] != second["snapshot_id"]
    first_value = conn.execute(
        "SELECT raw_value, normalized_score FROM fact_indicator_values "
        "WHERE snapshot_id = ?",
        (first["snapshot_id"],),
    ).fetchone()
    second_value = conn.execute(
        "SELECT raw_value, normalized_score FROM fact_indicator_values "
        "WHERE snapshot_id = ?",
        (second["snapshot_id"],),
    ).fetchone()
    assert first_value == (10.0, 90.0)
    assert second_value == (20.0, 10.0)
    assert verify_content_digest(conn, first["snapshot_id"])
    assert verify_content_digest(conn, second["snapshot_id"])
    conn.close()


def test_finalize_marks_snapshot_immutable_and_reproducible(tmp_path):
    conn = _new_database(tmp_path)
    _new_staging(conn, STAGING)
    _add_fact(conn, STAGING, raw_value=10.0, normalized_score=90.0)
    conn.commit()
    result = _finalize(conn, STAGING)

    row = conn.execute(
        "SELECT is_immutable, is_reproducible, content_sha256, metadata_checksum, "
        "content_hash_spec, observation_count, indicator_count, "
        "available_indicator_count, region_count "
        "FROM data_snapshots WHERE snapshot_id = ?",
        (result["snapshot_id"],),
    ).fetchone()
    assert row[0] == 1
    assert row[1] == 1
    assert row[2] == result["content_sha256"]
    assert row[3] == result["metadata_checksum"]
    assert row[4] == "canonical-json-v1"
    assert row[5] == 1
    assert row[6] == 1
    assert row[7] == 1
    assert row[8] == 1
    conn.close()


def test_legacy_snapshot_is_marked_unreproducible(tmp_path):
    conn = _new_database(tmp_path)
    conn.execute(
        """INSERT INTO data_snapshots
           (snapshot_id, label, environment_tag, is_active_default,
            boundary_version, manifest_checksum, notes, published_at,
            is_immutable, is_reproducible)
           VALUES ('2026.10.0-official-live', 'legacy', 'LIVE', 0,
                   'BIG-LEGACY', 'old-manifest', 'legacy', datetime('now'), 1, 1)"""
    )
    _new_staging(conn, STAGING)
    _add_fact(conn, STAGING, raw_value=10.0, normalized_score=90.0)
    conn.commit()
    result = _finalize(conn, STAGING)

    mark_legacy_snapshots(conn)
    legacy = conn.execute(
        "SELECT is_immutable, is_reproducible, immutability_note FROM data_snapshots "
        "WHERE snapshot_id = '2026.10.0-official-live'"
    ).fetchone()
    assert legacy[0] == 0
    assert legacy[1] == 0
    assert "reused" in legacy[2].lower()

    current = conn.execute(
        "SELECT is_immutable, is_reproducible FROM data_snapshots WHERE snapshot_id = ?",
        (result["snapshot_id"],),
    ).fetchone()
    assert current == (1, 1)
    conn.close()


@pytest.mark.asyncio
async def test_unknown_snapshot_fails_explicitly(client):
    response = await client.get("/api/v1/indicators/coverage?mode=demo&snapshot=missing")
    assert response.status_code == 404
    assert response.json()["code"] == "SNAPSHOT_NOT_FOUND"


@pytest.mark.asyncio
async def test_snapshot_alias_and_snapshot_id_are_equivalent(client):
    alias = await client.get(
        "/api/v1/indicators/coverage?mode=demo&snapshot=2026.10.0-wia-demo"
    )
    legacy = await client.get(
        "/api/v1/indicators/coverage?mode=demo&snapshot_id=2026.10.0-wia-demo"
    )
    assert alias.status_code == 200
    assert legacy.status_code == 200
    assert alias.json()["data"] == legacy.json()["data"]
    assert alias.headers["X-NusaMatra-Snapshot"] == "2026.10.0-wia-demo"


@pytest.mark.asyncio
async def test_snapshot_metadata_and_coverage_are_consistent(client):
    body = (await client.get("/api/v1/snapshots?mode=demo")).json()
    snapshot = body["data"][0]
    assert snapshot["indicator_count"] == 33
    assert snapshot["available_indicator_count"] == 31
    assert snapshot["indicator_completeness_pct"] == 93.9
    assert snapshot["available_indicator_data_pct"] == 100.0
    assert snapshot["region_count"] == 514
    assert snapshot["region_coverage_pct"] == 100.0

    coverage = (await client.get("/api/v1/indicators/coverage?mode=demo")).json()
    data = coverage["data"]
    assert data["total_indicators"] == 33
    assert data["available_indicators_count"] == 31
    assert data["indicator_completeness_pct"] == 93.9
    assert coverage["meta"]["indicator_coverage"]["available_indicators"] == 31
    assert coverage["meta"]["coverage"]["available"] == 514
    assert coverage["meta"]["coverage"]["total_regions"] == 514


@pytest.mark.asyncio
async def test_snapshot_detail_endpoint_and_unknown_detail(client):
    response = await client.get("/api/v1/snapshots/2026.10.0-wia-demo?mode=demo")
    assert response.status_code == 200
    assert response.json()["data"]["snapshot_id"] == "2026.10.0-wia-demo"
    assert response.json()["data"]["manifest_checksum"]

    unknown = await client.get("/api/v1/snapshots/does-not-exist?mode=demo")
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_repeated_pinned_retrieval_is_equivalent(client):
    first = await client.get(
        "/api/v1/indicators/inf_safe_water_pct/values"
        "?mode=demo&snapshot=2026.10.0-wia-demo"
    )
    second = await client.get(
        "/api/v1/indicators/inf_safe_water_pct/values"
        "?mode=demo&snapshot=2026.10.0-wia-demo"
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    assert first.json()["meta"]["snapshot_id"] == second.json()["meta"]["snapshot_id"]
