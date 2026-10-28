"""
Tests for GET /api/v1/regions and GET /api/v1/regions/{region_id}
"""

import pytest


@pytest.mark.asyncio
async def test_list_regions_returns_514(client):
    """Default query should return 514 kabupaten/kota."""
    resp = await client.get("/api/v1/regions")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "success"
    assert data["meta"]["mode"] == "DEMO"
    assert data["meta"]["total_count"] == 514


@pytest.mark.asyncio
async def test_list_regions_provinsi(client):
    """Level=provinsi should return 38 provinces."""
    resp = await client.get("/api/v1/regions?level=provinsi")
    assert resp.status_code == 200

    data = resp.json()
    assert data["meta"]["total_count"] == 38


@pytest.mark.asyncio
async def test_list_regions_parent_filter(client):
    """Filtering by parent_id should return only regions in that province."""
    resp = await client.get("/api/v1/regions?parent_id=32")
    assert resp.status_code == 200

    data = resp.json()
    assert data["meta"]["total_count"] > 0
    for region in data["data"]:
        assert region["parent_region_id"] == "32"


@pytest.mark.asyncio
async def test_list_regions_search(client):
    """Text search should filter results."""
    resp = await client.get("/api/v1/regions?q=3201")
    assert resp.status_code == 200

    data = resp.json()
    assert data["meta"]["total_count"] >= 1


@pytest.mark.asyncio
async def test_list_regions_search_wildcard_escaping(client):
    """BE-07.1: Text search with LIKE wildcards % or _ must be escaped literally."""
    # Since no region has a literal % in its name or ID, this should return 0 results
    resp = await client.get("/api/v1/regions?q=%25")
    assert resp.status_code == 200

    data = resp.json()
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_get_region_detail(client):
    """GET /regions/{id} should return full profile with indicators."""
    # Get first region from list to find a valid ID
    list_resp = await client.get("/api/v1/regions")
    regions = list_resp.json()["data"]
    region_id = regions[0]["region_id"]

    resp = await client.get(f"/api/v1/regions/{region_id}")
    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    assert "region" in data
    assert "composite_scores" in data
    assert "indicators" in data

    # The frontend needs the score direction to interpret national percentiles.
    assert body["meta"]["score_direction"] == "higher_is_need"
    assert data["indicators"]
    for indicator in data["indicators"]:
        assert indicator["polarity"] in {"positive", "negative"}
        assert indicator["national_percentile"] is not None

    # Check indicators have DEMO_EXAMPLE flag
    if data["indicators"]:
        assert data["indicators"][0]["quality_flag"] == "DEMO_EXAMPLE"


@pytest.mark.asyncio
async def test_get_region_not_found(client):
    """Non-existent region should return 404."""
    resp = await client.get("/api/v1/regions/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_region_response_structure(client):
    """Validate response structure matches API contract."""
    list_resp = await client.get("/api/v1/regions")
    regions = list_resp.json()["data"]
    region_id = regions[0]["region_id"]

    resp = await client.get(f"/api/v1/regions/{region_id}")
    data = resp.json()["data"]
    region = data["region"]

    # Check required fields exist
    assert "region_id" in region
    assert "codes" in region
    assert "kemendagri" in region["codes"]
    assert "bps" in region["codes"]
    assert "anchor_point" in region
    assert "lng" in region["anchor_point"]
    assert "lat" in region["anchor_point"]
    assert "bbox" in region
    assert len(region["bbox"]) == 4
