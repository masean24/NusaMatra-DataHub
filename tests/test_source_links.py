"""Contract tests for the source-link reference overlay."""

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


def test_registry_contract_exceptions():
    assert indicator_source("hlt_facilities_per_10k").url is None
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
    assert len(snapshots) >= 5
    for snapshot_id in snapshots:
        assert verify_content_digest(conn, snapshot_id) is True, snapshot_id
    conn.close()
