"""
Tests for POST /api/v1/indicators/composite-query
Validates basis-point weighting (Blocker #4).
"""

import pytest


@pytest.mark.asyncio
async def test_composite_query_valid(client):
    """Valid composite query with basis points summing to 10000."""
    body = {
        "weights": {
            "dis_multihazard_index": 3500,
            "soc_poverty_rate": 2500,
            "edu_damaged_classrooms_pct": 2000,
            "hlt_stunting_prevalence": 2000,
        },
        "filter_province_id": None,
    }

    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["total_regions"] == 514
    assert data["weights_basis_points"]["dis_multihazard_index"] == 3500

    # Check regions are ranked
    regions = data["regions"]
    assert len(regions) == 514
    assert regions[0]["rank"] == 1
    assert regions[-1]["rank"] == 514

    # Composite score should be between 0 and 100
    for r in regions:
        assert 0 <= r["composite_score"] <= 100


@pytest.mark.asyncio
async def test_composite_query_unavailable_indicator_transparency(client):
    """BE-03 & BE-08: Indicators with no observations must be listed in unavailable_indicators and renormalized."""
    body = {
        "weights": {
            "dis_multihazard_index": 5000,
            "edu_school_travel_time_p90": 5000,
        }
    }
    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "edu_school_travel_time_p90" in data["unavailable_indicators"]
    assert "edu_school_travel_time_p90" not in data["effective_weights"]
    assert data["renormalized"] is True
    # Scaled to full 10,000 bp
    assert data["effective_weights"]["dis_multihazard_index"] == 10000

    # Also compare with single 10000 query to ensure scores are equal
    single_resp = await client.post(
        "/api/v1/indicators/composite-query",
        json={"weights": {"dis_multihazard_index": 10000}},
    )
    assert single_resp.status_code == 200
    single_data = single_resp.json()["data"]
    assert data["regions"][0]["composite_score"] == single_data["regions"][0]["composite_score"]


@pytest.mark.asyncio
async def test_composite_query_all_indicators_unavailable_rejected(client):
    """BE-08: If all requested indicators have no data in snapshot, return 422."""
    body = {
        "weights": {
            "edu_school_travel_time_p90": 5000,
            "hlt_realtime_icu_occupancy": 5000,
        }
    }
    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 422
    assert "unavailable" in resp.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_composite_query_invalid_sum(client):
    """Weights not summing to 10000 should return 422."""
    body = {
        "weights": {
            "dis_multihazard_index": 5000,
            "soc_poverty_rate": 3000,
            # Sum = 8000, not 10000
        },
    }

    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_composite_query_province_filter(client):
    """Filtering by province should return fewer regions."""
    body = {
        "weights": {
            "dis_multihazard_index": 5000,
            "soc_poverty_rate": 5000,
        },
        "filter_province_id": "32",
    }

    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 200

    data = resp.json()["data"]
    # Province 32 (Jawa Barat) has 27 kab/kota
    assert data["total_regions"] == 27
    assert len(data["regions"]) == 27


@pytest.mark.asyncio
async def test_composite_query_negative_weight_rejected(client):
    """BE-01: Negative weights must return 422 even if sum equals 10000."""
    body = {
        "weights": {
            "soc_poverty_rate": 20000,
            "dis_multihazard_index": -10000,
        }
    }
    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_composite_query_empty_weights_rejected(client):
    """BE-01: Empty weights dictionary must return 422."""
    body = {"weights": {}}
    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_composite_query_weight_above_max_rejected(client):
    """BE-01: Weight exceeding 10000 must return 422."""
    body = {
        "weights": {
            "soc_poverty_rate": 15000,
            "dis_multihazard_index": -5000,
        }
    }
    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_composite_query_invalid_province_filter(client):
    """BE-07.2: Non-2-digit province filter must return 422."""
    body = {
        "weights": {
            "dis_multihazard_index": 5000,
            "soc_poverty_rate": 5000,
        },
        "filter_province_id": "invalid_province_abc",
    }
    resp = await client.post("/api/v1/indicators/composite-query", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_composite_presets(client):
    """GET /api/v1/indicators/composite-presets must return valid policy presets."""
    resp = await client.get("/api/v1/indicators/composite-presets")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"
    presets = body["data"]
    assert len(presets) >= 4

    for p in presets:
        assert "preset_id" in p
        assert "title" in p
        assert "weights" in p
        # Every preset must have weights summing to exactly 10,000 basis points
        weights = p["weights"]
        assert sum(weights.values()) == 10000, f"Preset {p['preset_id']} does not sum to 10000"

        # Verify executing query with this preset succeeds (status 200)
        query_resp = await client.post(
            "/api/v1/indicators/composite-query",
            json={"weights": weights},
        )
        assert query_resp.status_code == 200
        assert query_resp.json()["data"]["total_regions"] == 514
