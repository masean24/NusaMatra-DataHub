"""
Unit tests for BMKG Earthquake Endpoints.
Covers latest, recent M5+, felt, GeoJSON FeatureCollection, summary,
provenance metadata, cache policies, and fail-closed upstream simulations.
"""

import time

import pytest
import httpx
from app.main import app
from app.config import settings
from app.services import bmkg_service


@pytest.fixture(autouse=True)
def reset_earthquake_cache():
    """Ensure clean cache and live mode enabled before each test run."""
    bmkg_service._cache._live_cache = {}
    bmkg_service._cache._cached_at = None
    bmkg_service._cache._last_success_at = None
    original_live = settings.enable_live_mode
    settings.enable_live_mode = True
    yield
    settings.enable_live_mode = original_live
    bmkg_service._cache._live_cache = {}
    bmkg_service._cache._cached_at = None
    bmkg_service._cache._last_success_at = None


@pytest.fixture
def mock_bmkg_upstream(monkeypatch):
    """Deterministic BMKG live payload built from the bundled official fixture."""
    result = bmkg_service.BmkgFeedResult(
        data=bmkg_service._load_local_fixture(),
        data_origin="bmkg_live",
        last_success_at="2026-10-23T00:00:00+00:00",
        is_stale=False,
        fallback_header="NONE",
    )

    async def fake_fetch(*args, **kwargs):
        return result

    monkeypatch.setattr(bmkg_service, "fetch_bmkg_feeds", fake_fetch)
    return result


@pytest.mark.asyncio
async def test_get_earthquakes_latest(mock_bmkg_upstream):
    """Verify latest earthquake endpoint returns 200 and standard event format."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/latest?mode=live")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "success"
        assert "meta" in body
        assert "data" in body
        assert body["meta"]["data_origin"] in ("bmkg_live", "bmkg_cache")
        assert body["meta"]["is_stale"] is False
        assert body["meta"]["last_success_at"] is not None

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
async def test_get_earthquakes_recent_m5(mock_bmkg_upstream):
    """Verify recent M5+ earthquakes endpoint returns list of significant events."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/recent?mode=live")
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
async def test_get_earthquakes_felt(mock_bmkg_upstream):
    """Verify felt earthquakes endpoint returns events with intensity notes."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/felt?mode=live")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "success"
        events = body["data"]
        assert isinstance(events, list)
        assert len(events) > 0
        assert len(events) <= 15

        for ev in events:
            assert ev["felt"] is not None
            assert len(ev["felt"]) > 0


@pytest.mark.asyncio
async def test_get_earthquakes_geojson_live_provenance(mock_bmkg_upstream):
    """Verify GeoJSON FeatureCollection metadata, origin, and headers in LIVE mode."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/geojson?mode=live")
        assert resp.status_code == 200

        # Check HTTP Headers
        assert resp.headers.get("X-NusaMatra-Mode") == "LIVE"
        assert resp.headers.get("X-Data-Fallback") == "NONE"
        assert "no-cache" in resp.headers.get("Cache-Control", "")
        assert "must-revalidate" in resp.headers.get("Cache-Control", "")

        geojson = resp.json()
        assert geojson["type"] == "FeatureCollection"
        assert "metadata" in geojson
        assert "features" in geojson
        assert isinstance(geojson["features"], list)
        assert len(geojson["features"]) > 0

        # Validate metadata pipeline provenance
        meta = geojson["metadata"]
        assert meta["data_origin"] in ("bmkg_live", "bmkg_cache")
        assert meta["last_success_at"] is not None
        assert meta["is_stale"] is False
        assert meta["cache_ttl_seconds"] == 60

        first = geojson["features"][0]
        assert first["type"] == "Feature"
        assert first["geometry"]["type"] == "Point"
        assert len(first["geometry"]["coordinates"]) == 2

        props = first["properties"]
        assert "magnitude" in props
        assert "depth_km" in props
        assert "area" in props
        assert "severity" in props
        assert props["data_origin"] in ("bmkg_live", "bmkg_cache")
        assert props["severity"] in ("LOW", "MODERATE", "HIGH", "SEVERE")
        assert "visual_color" in props
        assert props["visual_color"].startswith("#")
        assert "visual_radius_px" in props
        assert props["visual_radius_px"] > 0


@pytest.mark.asyncio
async def test_get_earthquakes_geojson_demo_fixture():
    """Verify DEMO mode returns fixture provenance and DEMO_FIXTURE header."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/geojson?mode=demo")
        assert resp.status_code == 200

        # In DEMO mode:
        assert resp.headers.get("X-NusaMatra-Mode") == "DEMO"
        assert resp.headers.get("X-Data-Fallback") == "DEMO_FIXTURE"

        geojson = resp.json()
        assert geojson["metadata"]["data_origin"] == "fixture"
        assert geojson["metadata"]["last_success_at"] is None
        assert geojson["metadata"]["is_stale"] is False


@pytest.mark.asyncio
async def test_earthquakes_live_cache_hit_avoids_upstream():
    """A fresh in-memory cache must be served without touching BMKG upstream."""
    now = time.time()
    bmkg_service._cache._live_cache = bmkg_service._load_local_fixture()
    bmkg_service._cache._cached_at = now
    bmkg_service._cache._last_success_at = now

    result = await bmkg_service.fetch_bmkg_feeds(mode="LIVE")

    assert result.data_origin == "bmkg_cache"
    assert result.is_stale is False
    assert result.last_success_at is not None


@pytest.mark.asyncio
async def test_earthquakes_live_upstream_failure_simulation():
    """Verify fail-closed 503 behavior when BMKG live upstream is unreachable."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/geojson?mode=live&simulate_upstream_failure=true")
        assert resp.status_code == 503

        # Header checks
        assert resp.headers.get("X-NusaMatra-Mode") == "LIVE"
        assert resp.headers.get("X-Data-Fallback") == "UNAVAILABLE"
        assert "no-cache" in resp.headers.get("Cache-Control", "")

        body = resp.json()
        assert body["status"] == "error"
        assert body["code"] == "UPSTREAM_UNAVAILABLE"
        assert "LIVE mode fails closed" in body["message"]


@pytest.mark.asyncio
async def test_get_earthquakes_summary(mock_bmkg_upstream):
    """Verify earthquake activity summary endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/earthquakes/summary?mode=live")
        assert resp.status_code == 200

        body = resp.json()
        summary = body["data"]
        assert "latest" in summary
        assert "recent_m5_count" in summary
        assert "felt_count" in summary
        assert "cache_ttl_seconds" in summary
        assert summary["cache_ttl_seconds"] == 60
        assert summary["data_origin"] in ("bmkg_live", "bmkg_cache")
        assert summary["is_stale"] is False
        assert "BMKG" in summary["agency"]
