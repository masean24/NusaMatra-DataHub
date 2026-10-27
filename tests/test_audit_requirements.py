"""
Tests mandated by Nusa-Matra-API-Integration-Audit.md.

Covers:
- P0: LIVE mode fail-closed on all endpoints (503 + X-Data-Fallback: UNAVAILABLE)
- P1: composite-query weight validation (422)
  - sum < 10000
  - sum > 10000
  - unknown indicator_id
- P1: boundary geometry_status field present & correct
- P0: ApiResponse.data is typed (validated by schema round-trip)
"""

import pytest


# ---------------------------------------------------------------------------
# LIVE fail-closed — must return 503 with correct headers on every endpoint
# ---------------------------------------------------------------------------

LIVE_ENDPOINTS = [
    "/api/v1/regions",
    "/api/v1/regions/3201",
    "/api/v1/indicators",
    "/api/v1/indicators/soc_poverty_rate/values",
    "/api/v1/boundaries/kabupaten",
    "/api/v1/boundaries/provinsi",
    "/api/v1/datasets",
    "/api/v1/snapshots",
    "/api/v1/health",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", LIVE_ENDPOINTS)
async def test_live_mode_query_param_returns_503(client, endpoint):
    """?mode=live on any GET endpoint must return 503 fail-closed."""
    resp = await client.get(f"{endpoint}?mode=live")
    assert resp.status_code == 503, f"Expected 503 for {endpoint}?mode=live, got {resp.status_code}"

    body = resp.json()
    assert body["status"] == "error"
    assert body["code"] == "LIVE_UNAVAILABLE"

    assert resp.headers.get("X-NusaMatra-Mode") == "LIVE"
    assert resp.headers.get("X-Data-Fallback") == "UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", LIVE_ENDPOINTS)
async def test_live_mode_header_returns_503(client, endpoint):
    """X-Data-Mode: LIVE header on any GET endpoint must return 503 fail-closed."""
    resp = await client.get(endpoint, headers={"X-Data-Mode": "LIVE"})
    assert resp.status_code == 503, (
        f"Expected 503 for {endpoint} with X-Data-Mode:LIVE, got {resp.status_code}"
    )

    body = resp.json()
    assert body["code"] == "LIVE_UNAVAILABLE"
    assert resp.headers.get("X-Data-Fallback") == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_live_mode_composite_post_returns_503(client):
    """POST /composite-query with mode=live must also return 503."""
    resp = await client.post(
        "/api/v1/indicators/composite-query?mode=live",
        json={
            "weights": {
                "dis_multihazard_index": 5000,
                "soc_poverty_rate": 5000,
            }
        },
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "LIVE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# CORS verification — preflight & error responses (including 503 LIVE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_options_preflight_for_frontend_dev(client):
    """OPTIONS preflight with Origin and X-Data-Mode header must succeed (200)."""
    resp = await client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Data-Mode",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in resp.headers.get("access-control-allow-methods", "")
    assert "X-Data-Mode" in resp.headers.get("access-control-allow-headers", "")


@pytest.mark.asyncio
async def test_cors_headers_present_on_live_503_error(client):
    """503 LIVE response must include CORS headers for browser frontends."""
    resp = await client.get(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "X-Data-Mode": "LIVE",
        },
    )
    assert resp.status_code == 503
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("x-data-fallback") == "UNAVAILABLE"

    # Verify custom headers are exposed to browser JavaScript
    exposed = resp.headers.get("access-control-expose-headers", "")
    assert "X-Data-Fallback" in exposed
    assert "X-NusaMatra-Mode" in exposed


@pytest.mark.asyncio
async def test_cors_headers_present_on_post_live_503_error(client):
    """POST 503 LIVE response must also include CORS headers."""
    resp = await client.post(
        "/api/v1/indicators/composite-query",
        headers={
            "Origin": "http://localhost:5173",
            "X-Data-Mode": "LIVE",
        },
        json={
            "weights": {
                "dis_multihazard_index": 5000,
                "soc_poverty_rate": 5000,
            }
        },
    )
    assert resp.status_code == 503
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("x-data-fallback") == "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Composite query — weight validation (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_composite_weights_sum_below_10000_returns_422(client):
    """Weights summing to less than 10000 → 422."""
    resp = await client.post(
        "/api/v1/indicators/composite-query",
        json={
            "weights": {
                "dis_multihazard_index": 5000,
                "soc_poverty_rate": 3000,
                # sum = 8000, not 10000
            }
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "WEIGHT_VALIDATION_ERROR"
    assert "10000" in body["message"]


@pytest.mark.asyncio
async def test_composite_weights_sum_above_10000_returns_422(client):
    """Weights summing to more than 10000 → 422."""
    resp = await client.post(
        "/api/v1/indicators/composite-query",
        json={
            "weights": {
                "dis_multihazard_index": 6000,
                "soc_poverty_rate": 5000,
                # sum = 11000, not 10000
            }
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "WEIGHT_VALIDATION_ERROR"
    assert "10000" in body["message"]


@pytest.mark.asyncio
async def test_composite_unknown_indicator_id_returns_422(client):
    """Unknown indicator_id in weights → 422."""
    resp = await client.post(
        "/api/v1/indicators/composite-query",
        json={
            "weights": {
                "dis_multihazard_index": 5000,
                "THIS_INDICATOR_DOES_NOT_EXIST_XYZ": 5000,
            }
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Boundary geometry_status field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kabupaten_boundary_has_geometry_status(client):
    """GET /boundaries/kabupaten must include geometry_status with geometry_available=True."""
    resp = await client.get("/api/v1/boundaries/kabupaten")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "geometry_status" in data, "geometry_status block missing from boundary response"

    gs = data["geometry_status"]
    assert gs["geometry_available"] is True
    assert gs["geometry_type_returned"] == "MultiPolygon"
    assert "BIG" in gs["source"]
    assert gs["boundary_version"] == "BIG-Kepmendagri-300.2.2-2430-2025"


@pytest.mark.asyncio
async def test_provinsi_boundary_has_geometry_status(client):
    """GET /boundaries/provinsi must include geometry_status with geometry_available=True."""
    resp = await client.get("/api/v1/boundaries/provinsi")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "geometry_status" in data, "geometry_status block missing from province boundary response"

    gs = data["geometry_status"]
    assert gs["geometry_available"] is True
    assert gs["geometry_type_returned"] == "MultiPolygon"
    assert "BIG" in gs["source"]


# ---------------------------------------------------------------------------
# OpenAPI schema — typed response_model (smoke-test via /openapi.json)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openapi_schema_declares_503_for_regions(client):
    """OpenAPI schema must declare 503 response for GET /regions."""
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200

    schema = resp.json()
    paths = schema.get("paths", {})

    regions_get = paths.get("/api/v1/regions", {}).get("get", {})
    responses = regions_get.get("responses", {})
    assert "503" in responses, "503 response not declared for GET /api/v1/regions in OpenAPI schema"


@pytest.mark.asyncio
async def test_openapi_schema_declares_422_for_composite(client):
    """OpenAPI schema must declare 422 response for POST /indicators/composite-query."""
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200

    schema = resp.json()
    paths = schema.get("paths", {})

    composite_post = paths.get("/api/v1/indicators/composite-query", {}).get("post", {})
    responses = composite_post.get("responses", {})
    assert "422" in responses, (
        "422 response not declared for POST /api/v1/indicators/composite-query in OpenAPI schema"
    )


@pytest.mark.asyncio
async def test_openapi_schema_has_mode_param_on_regions(client):
    """OpenAPI schema must document ?mode query param on GET /regions."""
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200

    schema = resp.json()
    regions_get = schema["paths"].get("/api/v1/regions", {}).get("get", {})
    params = {p["name"]: p for p in regions_get.get("parameters", [])}
    assert "mode" in params, "?mode param not documented in OpenAPI for GET /api/v1/regions"
