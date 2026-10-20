"""
Tests for boundaries, datasets, snapshots, and root endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """GET / should return service info and endpoint list."""
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "Nusa Matra Data Hub"
    assert data["mode"] == "DEMO"
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_boundaries_kabupaten_default_geojson(client):
    """GET /boundaries/kabupaten should default to GeoJSON format."""
    resp = await client.get("/api/v1/boundaries/kabupaten")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"
    assert body["meta"]["total_count"] == 514

    geojson = body["data"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 514

    # Verify feature structure
    first_feature = geojson["features"][0]
    assert first_feature["type"] == "Feature"
    assert "geometry" in first_feature
    assert "properties" in first_feature
    assert "region_id" in first_feature["properties"]
    assert "kemendagri_code" in first_feature["properties"]
    assert "bps_code" in first_feature["properties"]


@pytest.mark.asyncio
async def test_boundaries_kabupaten_province_filter(client):
    """GET /boundaries/kabupaten?province_id=32 should filter to Jawa Barat."""
    resp = await client.get("/api/v1/boundaries/kabupaten?province_id=32")
    assert resp.status_code == 200

    body = resp.json()
    assert body["meta"]["total_count"] == 27
    features = body["data"]["features"]
    assert len(features) == 27
    for f in features:
        assert f["properties"]["parent_region_id"] == "32"


@pytest.mark.asyncio
async def test_boundaries_provinsi(client):
    """GET /boundaries/provinsi should return 38 province boundaries."""
    resp = await client.get("/api/v1/boundaries/provinsi")
    assert resp.status_code == 200

    body = resp.json()
    assert body["meta"]["total_count"] == 38
    features = body["data"]["features"]
    assert len(features) == 38


@pytest.mark.asyncio
async def test_datasets_endpoint(client):
    """GET /datasets should return registered government datasets."""
    resp = await client.get("/api/v1/datasets")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"
    assert body["meta"]["total_count"] == 13

    datasets = body["data"]
    assert len(datasets) == 13

    # Check provenance properties
    first = datasets[0]
    assert "dataset_id" in first
    assert "agency_code" in first
    assert "official_portal_url" in first
    assert "raw_sha256" in first


@pytest.mark.asyncio
async def test_snapshots_endpoint(client):
    """GET /snapshots should list data snapshots with completeness."""
    resp = await client.get("/api/v1/snapshots")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"
    assert body["meta"]["total_count"] == 1

    snapshots = body["data"]
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap["snapshot_id"] == "2026.10.0-wia-demo"
    assert snap["environment_tag"] == "DEMO"
    assert snap["is_active_default"] is True
    assert snap["indicator_completeness_pct"] == 100.0
