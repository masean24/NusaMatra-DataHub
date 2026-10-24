"""
Tests for GET /api/v1/health
"""

import sqlite3
from pathlib import Path

import pytest

LIVE_DB = Path(__file__).parent.parent / "data" / "nusa_matra_live.db"


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health endpoint should return 200 with status healthy."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["version"] == "0.1.0"
    assert data["mode"] == "DEMO"
    assert "database" in data


@pytest.mark.asyncio
async def test_health_has_standard_headers(client):
    """Response should include standard Nusa Matra headers."""
    resp = await client.get("/api/v1/health")
    assert resp.headers.get("X-NusaMatra-Mode") == "DEMO"
    assert resp.headers.get("X-NusaMatra-Snapshot") == "2026.10.0-wia-demo"
    assert resp.headers.get("X-Data-Fallback") == "NONE"


@pytest.mark.asyncio
async def test_invalid_mode_returns_422(client):
    """C1: Invalid mode query param must return 422."""
    resp = await client.get("/api/v1/health?mode=foo")
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_MODE"


@pytest.mark.asyncio
async def test_nonexistent_snapshot_returns_404(client):
    """C1: Unknown snapshot_id must return 404."""
    resp = await client.get("/api/v1/health?snapshot_id=does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "SNAPSHOT_NOT_FOUND"


@pytest.mark.asyncio
async def test_mismatched_snapshot_returns_422(client):
    """C1: Snapshot mismatch with environment must return 422."""
    if not LIVE_DB.exists():
        pytest.skip("LIVE database not generated")
    connection = sqlite3.connect(LIVE_DB)
    row = connection.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag = 'LIVE' AND is_active_default = 1 LIMIT 1"
    ).fetchone()
    connection.close()
    if row is None:
        pytest.skip("No active LIVE snapshot")
    resp = await client.get(
        f"/api/v1/health?mode=demo&snapshot_id={row[0]}"
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "SNAPSHOT_MODE_MISMATCH"


@pytest.mark.asyncio
async def test_boundary_caching_headers(client):
    """C2: Boundaries endpoint must return 7-day immutable Cache-Control."""
    resp = await client.get("/api/v1/boundaries/provinsi")
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "public, max-age=604800, immutable"


@pytest.mark.asyncio
async def test_openapi_alias_endpoint(client):
    """B3: /openapi.json alias must return valid OpenAPI 3.1 specification."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert "openapi" in resp.json()


@pytest.mark.asyncio
async def test_live_mode_returns_503(client):
    """LIVE mode must fail closed with 503 (Blocker #1)."""
    resp = await client.get("/api/v1/health?mode=live")
    assert resp.status_code == 503

    data = resp.json()
    assert data["code"] == "LIVE_UNAVAILABLE"
    assert resp.headers.get("X-NusaMatra-Mode") == "LIVE"
    assert resp.headers.get("X-Data-Fallback") == "UNAVAILABLE"
