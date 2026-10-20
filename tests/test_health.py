"""
Tests for GET /api/v1/health
"""

import pytest


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
async def test_live_mode_returns_503(client):
    """LIVE mode must fail closed with 503 (Blocker #1)."""
    resp = await client.get("/api/v1/health?mode=live")
    assert resp.status_code == 503

    data = resp.json()
    assert data["code"] == "LIVE_UNAVAILABLE"
    assert resp.headers.get("X-NusaMatra-Mode") == "LIVE"
    assert resp.headers.get("X-Data-Fallback") == "UNAVAILABLE"
