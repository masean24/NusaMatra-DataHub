"""
Unit tests for BMKG Earthquake Endpoints.
Covers latest, recent M5+, felt, GeoJSON FeatureCollection, and summary.
"""

import pytest
import httpx
from app.main import app
from app.services import bmkg_service


@pytest.fixture(autouse=True)
def reset_earthquake_cache():
    """Ensure clean cache before each test run."""
    bmkg_service._cache._cache = {}
    bmkg_service._cache._cached_at = None


@pytest.mark.asyncio
async def test_get_earthquakes_latest():
    """Verify latest earthquake endpoint returns 200 and standard event format."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/latest")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "success"
        assert "meta" in body
        assert "data" in body

        event = body["data"]
        assert event is not None
        assert "magnitude" in event
        assert isinstance(event["magnitude"], (int, float))
        assert "coordinates" in event
        assert len(event["coordinates"]) == 2
        assert -180.0 <= event["coordinates"][0] <= 180.0  # Longitude
        assert -90.0 <= event["coordinates"][1] <= 90.0    # Latitude
        assert event["source"] == "BMKG"
        assert "area" in event
        assert "datetime" in event


@pytest.mark.asyncio
async def test_get_earthquakes_recent_m5():
    """Verify recent M5+ earthquakes endpoint returns list of significant events."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/recent")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "success"
        events = body["data"]
        assert isinstance(events, list)
        assert len(events) > 0
        assert len(events) <= 15

        # All events in gempaterkini should have magnitude >= 5.0
        for ev in events:
            assert ev["magnitude"] >= 5.0
            assert len(ev["coordinates"]) == 2
            assert ev["coordinates"][0] == ev["longitude"]
            assert ev["coordinates"][1] == ev["latitude"]


@pytest.mark.asyncio
async def test_get_earthquakes_felt():
    """Verify felt earthquakes endpoint returns events with intensity notes."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/felt")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "success"
        events = body["data"]
        assert isinstance(events, list)
        assert len(events) > 0
        assert len(events) <= 15

        # All felt events should have felt intensity description
        for ev in events:
            assert ev["felt"] is not None
            assert len(ev["felt"]) > 0


@pytest.mark.asyncio
async def test_get_earthquakes_geojson():
    """Verify RFC 7946 GeoJSON FeatureCollection format for 3D map engines."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/geojson")
        assert resp.status_code == 200

        geojson = resp.json()
        assert geojson["type"] == "FeatureCollection"
        assert "metadata" in geojson
        assert "features" in geojson
        assert isinstance(geojson["features"], list)
        assert len(geojson["features"]) > 0

        first = geojson["features"][0]
        assert first["type"] == "Feature"
        assert first["geometry"]["type"] == "Point"
        assert len(first["geometry"]["coordinates"]) == 2

        props = first["properties"]
        assert "magnitude" in props
        assert "depth_km" in props
        assert "area" in props
        assert "severity" in props
        assert props["severity"] in ("LOW", "MODERATE", "HIGH", "SEVERE")
        assert "visual_color" in props
        assert props["visual_color"].startswith("#")
        assert "visual_radius_px" in props
        assert props["visual_radius_px"] > 0


@pytest.mark.asyncio
async def test_get_earthquakes_summary():
    """Verify earthquake activity summary endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/summary")
        assert resp.status_code == 200

        body = resp.json()
        summary = body["data"]
        assert "latest" in summary
        assert "recent_m5_count" in summary
        assert "felt_count" in summary
        assert "cache_ttl_seconds" in summary
        assert summary["cache_ttl_seconds"] == 60
        assert "agency" in summary
        assert "BMKG" in summary["agency"]


@pytest.mark.asyncio
async def test_earthquakes_cache_preserves_rate_limits():
    """Verify that multiple consecutive calls hit in-memory cache."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # First call populates cache
        resp1 = await client.get("/api/v1/earthquakes/summary")
        cached_at1 = resp1.json()["data"]["cached_at"]

        # Second call immediately should return identical cached_at
        resp2 = await client.get("/api/v1/earthquakes/summary")
        cached_at2 = resp2.json()["data"]["cached_at"]

        assert cached_at1 == cached_at2
        assert bmkg_service._cache.is_fresh() is True
