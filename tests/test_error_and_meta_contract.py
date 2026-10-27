"""
Contract tests for the shared error envelope and snapshot metadata.
"""

import pytest


@pytest.mark.asyncio
async def test_request_validation_error_uses_standard_envelope(client):
    """FastAPI query validation failures must not leak the default detail list."""
    resp = await client.get("/api/v1/regions", params={"level": "invalid"})

    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "error"
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed."
    assert isinstance(body["detail"], str)
    assert "level" in body["detail"]


@pytest.mark.asyncio
async def test_path_validation_error_uses_standard_envelope(client):
    """Boundary format validation must use the same error envelope."""
    resp = await client.get("/api/v1/boundaries/kabupaten", params={"format": "topojson"})

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["detail"], str)
    assert "format" in body["detail"]


@pytest.mark.asyncio
async def test_composite_validation_error_uses_standard_envelope(client):
    """Structured weight errors must be top-level, not nested under detail."""
    resp = await client.post(
        "/api/v1/indicators/composite-query",
        json={
            "weights": {
                "dis_multihazard_index": 5000,
                "soc_poverty_rate": 3000,
            }
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "error"
    assert body["code"] == "WEIGHT_VALIDATION_ERROR"
    assert "10000" in body["message"]
    assert not isinstance(body.get("detail"), dict)


@pytest.mark.asyncio
async def test_http_exception_uses_standard_envelope(client):
    """Route-level HTTPException responses must use the shared envelope."""
    resp = await client.get("/api/v1/indicators/does_not_exist/values")

    assert resp.status_code == 404
    body = resp.json()
    assert body["status"] == "error"
    assert body["code"] == "NOT_FOUND"
    assert "not found" in body["message"].lower()


@pytest.mark.asyncio
async def test_boundary_version_is_consistent_across_data_endpoints(client):
    """Every snapshot-backed response must expose the same boundary version."""
    snapshots = (await client.get("/api/v1/snapshots")).json()
    expected = snapshots["data"][0]["boundary_version"]
    assert expected

    endpoints = [
        "/api/v1/regions",
        "/api/v1/datasets",
        "/api/v1/indicators/coverage",
        "/api/v1/indicators/soc_poverty_rate/values",
        "/api/v1/boundaries/kabupaten",
        "/api/v1/snapshots",
    ]

    for endpoint in endpoints:
        resp = await client.get(endpoint)
        assert resp.status_code == 200, endpoint
        assert resp.json()["meta"]["boundary_version"] == expected, endpoint

    composite = await client.post(
        "/api/v1/indicators/composite-query",
        json={
            "weights": {
                "dis_multihazard_index": 5000,
                "soc_poverty_rate": 5000,
            }
        },
    )
    assert composite.status_code == 200
    assert composite.json()["meta"]["boundary_version"] == expected
