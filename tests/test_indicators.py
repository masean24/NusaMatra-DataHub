"""
Tests for /api/v1/indicators endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_list_indicators(client):
    """GET /indicators should return grouped indicator catalog."""
    resp = await client.get("/api/v1/indicators")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "success"
    # Total should be 33 indicators
    assert data["meta"]["total_count"] == 33

    # Data should be grouped by category
    categories = data["data"]
    expected_cats = {
        "disaster_risk", "socioeconomic", "education_access",
        "healthcare_access", "infrastructure", "data_reliability",
    }
    assert set(categories.keys()) == expected_cats


@pytest.mark.asyncio
async def test_get_indicator_values(client):
    """GET /indicators/{id}/values should return dict of region values and total_count in meta."""
    resp = await client.get("/api/v1/indicators/soc_poverty_rate/values")
    assert resp.status_code == 200

    body = resp.json()
    assert body["meta"]["total_count"] == 514
    assert "coverage" in body["meta"]
    cov = body["meta"]["coverage"]
    assert cov["available"] == 514
    assert cov["total_regions"] == 514
    assert cov["missing_region_ids"] == []
    data = body["data"]
    assert "indicator" in data
    assert "values_by_region" in data
    assert data["indicator"]["indicator_id"] == "soc_poverty_rate"

    # Should have values for all 514 regions
    values = data["values_by_region"]
    assert len(values) == 514

    # Check structure of a value entry
    first_val = next(iter(values.values()))
    assert "raw" in first_val
    assert "norm" in first_val
    assert "pct" in first_val
    assert "rank" in first_val
    assert first_val["flag"] == "DEMO_EXAMPLE"


@pytest.mark.asyncio
async def test_get_indicator_not_found(client):
    """Non-existent indicator should return 404."""
    resp = await client.get("/api/v1/indicators/nonexistent/values")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unavailable_indicator_no_values(client):
    """UNAVAILABLE indicators should have no fact rows."""
    resp = await client.get("/api/v1/indicators/edu_school_travel_time_p90/values")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert len(data["values_by_region"]) == 0


@pytest.mark.asyncio
async def test_get_indicators_coverage_endpoint(client):
    """B2: GET /api/v1/indicators/coverage must return coverage breakdown for all 33 indicators."""
    resp = await client.get("/api/v1/indicators/coverage")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["total_indicators"] == 33
    assert data["available_indicators_count"] >= 31  # 31 active in DEMO
    assert "indicators" in data
    assert "soc_poverty_rate" in data["indicators"]
    assert data["indicators"]["soc_poverty_rate"]["available"] is True
    assert data["indicators"]["soc_poverty_rate"]["coverage_count"] == 514


@pytest.mark.asyncio
async def test_indicator_values_ranking(client):
    """Ranks should be 1-514 with no duplicates."""
    resp = await client.get("/api/v1/indicators/soc_poverty_rate/values")
    values = resp.json()["data"]["values_by_region"]

    ranks = [v["rank"] for v in values.values()]
    assert min(ranks) == 1
    assert max(ranks) == 514
    assert len(set(ranks)) == 514  # All unique
