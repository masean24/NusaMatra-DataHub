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
async def test_favicon_and_docs_custom_icon(client):
    """GET /favicon.ico and /api/v1/docs should serve custom favicon and Scalar docs."""
    resp = await client.get("/favicon.ico")
    assert resp.status_code == 200

    docs_resp = await client.get("/api/v1/docs")
    assert docs_resp.status_code == 200
    assert "/static/favicon.png" in docs_resp.text
    assert "@scalar/api-reference" in docs_resp.text


@pytest.mark.asyncio
async def test_scalar_docs_endpoints(client):
    """GET /docs, /api/v1/docs, /scalar should all serve Scalar API Reference."""
    for path in ("/docs", "/api/v1/docs", "/scalar", "/api/v1/scalar"):
        resp = await client.get(path)
        assert resp.status_code == 200
        assert "api-reference" in resp.text
        assert "@scalar/api-reference" in resp.text
        assert "deepSpace" in resp.text


@pytest.mark.asyncio
async def test_unique_operation_id_function(client):
    """OpenAPI schema must use the endpoint function name as operationId."""
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]

    # Check known endpoints have clean operationIds
    assert paths["/api/v1/health"]["get"]["operationId"] == "health_check"
    assert paths["/api/v1/regions"]["get"]["operationId"] == "get_regions"
    assert paths["/api/v1/indicators"]["get"]["operationId"] == "get_indicators"
    assert paths["/api/v1/indicators/composite-query"]["post"]["operationId"] == "composite_query"


@pytest.mark.asyncio
async def test_docs_disabled_when_enable_docs_is_false(monkeypatch):
    """When ENABLE_DOCS=false, docs endpoints and openapi.json should return 404."""
    import importlib
    from httpx import AsyncClient, ASGITransport
    import app.config
    import app.main

    monkeypatch.setenv("ENABLE_DOCS", "false")
    reloaded_config = importlib.reload(app.config)
    assert reloaded_config.settings.enable_docs is False

    reloaded_main = importlib.reload(app.main)
    transport = ASGITransport(app=reloaded_main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (await ac.get("/docs")).status_code == 404
        assert (await ac.get("/api/v1/docs")).status_code == 404
        assert (await ac.get("/scalar")).status_code == 404
        assert (await ac.get("/api/v1/scalar")).status_code == 404
        assert (await ac.get("/redoc")).status_code == 404
        assert (await ac.get("/api/v1/redoc")).status_code == 404
        assert (await ac.get("/api/v1/openapi.json")).status_code == 404

    # Restore default
    monkeypatch.delenv("ENABLE_DOCS", raising=False)
    importlib.reload(app.config)
    importlib.reload(app.main)


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
async def test_boundaries_topojson_format_rejected(client):
    """BE-04: format=topojson must return 422 as it is not yet supported."""
    resp_kab = await client.get("/api/v1/boundaries/kabupaten?format=topojson")
    assert resp_kab.status_code == 422

    resp_prov = await client.get("/api/v1/boundaries/provinsi?format=topojson")
    assert resp_prov.status_code == 422


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
