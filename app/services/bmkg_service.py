"""
BMKG Earthquake Ingestion Service with in-memory caching and strict provenance tracking.

Sources:
- autogempa.json: Latest single earthquake published by BMKG
- gempaterkini.json: 15 recent earthquakes with M >= 5.0
- gempadirasakan.json: 15 recent earthquakes felt by the public
- Shakemap images hosted at https://data.bmkg.go.id/DataMKG/TEWS/

Features:
- In-memory cache with 60s TTL to strictly respect BMKG rate limits (60 req/min/IP).
- Strict provenance tracking: data_origin ("bmkg_live" | "bmkg_cache" | "fixture"),
  last_success_at, and is_stale.
- Fail-closed in LIVE mode: NEVER substitute local fixture data for official live requests.
- Automatic coordinate normalization from BMKG "lat,lon" to GeoJSON [lon, lat].
- Deduplication and enrichment across feeds for 3D map layers.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from app.models.earthquakes import (
    EarthquakeEvent,
    EarthquakeGeoJsonCollection,
    EarthquakeMetadata,
    EarthquakeSummary,
    GeoJsonFeature,
    GeoJsonGeometry,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "data" / "bmkg_earthquakes_fixture.json"

BMKG_BASE_URL = "https://data.bmkg.go.id/DataMKG/TEWS"
ENDPOINTS = {
    "autogempa": f"{BMKG_BASE_URL}/autogempa.json",
    "gempaterkini": f"{BMKG_BASE_URL}/gempaterkini.json",
    "gempadirasakan": f"{BMKG_BASE_URL}/gempadirasakan.json",
}

CACHE_TTL_SECONDS = 60


class UpstreamUnavailableError(Exception):
    """Raised when BMKG live upstream is unreachable and no verified live cache exists."""
    pass


class BmkgFeedResult:
    """Internal container capturing parsed feed payload and exact pipeline provenance."""

    def __init__(
        self,
        data: dict[str, Any],
        data_origin: str,
        last_success_at: Optional[str],
        is_stale: bool,
        fallback_header: str,
    ):
        self.data = data
        self.data_origin = data_origin  # "bmkg_live" | "bmkg_cache" | "fixture"
        self.last_success_at = last_success_at
        self.is_stale = is_stale
        self.fallback_header = fallback_header  # "NONE" | "DEMO_FIXTURE" | "STALE_CACHE"


class BmkgEarthquakeCache:
    """Thread-safe in-memory cache for BMKG earthquake feeds."""

    def __init__(self):
        self._live_cache: dict[str, Any] = {}
        self._cached_at: Optional[float] = None
        self._last_success_at: Optional[float] = None
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        if self._cached_at is None:
            return False
        return (time.time() - self._cached_at) < CACHE_TTL_SECONDS

    def has_live_cache(self) -> bool:
        return bool(self._live_cache and self._last_success_at is not None)

    @property
    def last_success_at_iso(self) -> Optional[str]:
        if self._last_success_at:
            return datetime.fromtimestamp(self._last_success_at, tz=timezone.utc).isoformat()
        return None

    @property
    def cached_at_iso(self) -> str:
        if self._cached_at:
            return datetime.fromtimestamp(self._cached_at, tz=timezone.utc).isoformat()
        return datetime.now(timezone.utc).isoformat()


_cache = BmkgEarthquakeCache()


def _load_local_fixture() -> dict[str, Any]:
    """Load bundled earthquake fixture for offline fallback / DEMO mode."""
    if FIXTURE_PATH.exists():
        try:
            with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load BMKG fixture: %s", exc)
    return {
        "autogempa": {"Infogempa": {"gempa": {}}},
        "gempaterkini": {"Infogempa": {"gempa": []}},
        "gempadirasakan": {"Infogempa": {"gempa": []}},
    }


def parse_raw_gempa(item: dict[str, Any]) -> Optional[EarthquakeEvent]:
    """Parse a single raw BMKG dictionary into a structured EarthquakeEvent."""
    if not item or not isinstance(item, dict):
        return None

    coords_str = item.get("Coordinates", "")
    parts = coords_str.split(",")
    if len(parts) == 2:
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except ValueError:
            lat, lon = 0.0, 0.0
    else:
        lat, lon = 0.0, 0.0

    mag_str = item.get("Magnitude", "0")
    try:
        magnitude = float(mag_str)
    except ValueError:
        magnitude = 0.0

    depth_str = item.get("Kedalaman", "")
    depth_match = re.search(r"[\d.]+", depth_str)
    depth_km = float(depth_match.group()) if depth_match else None

    dt_str = item.get("DateTime") or ""
    # Deterministic event ID
    clean_dt = dt_str.replace(":", "").replace("-", "").replace("+", "Z")
    event_id = f"bmkg-{clean_dt}-{lat:.2f}-{lon:.2f}"

    shakemap = item.get("Shakemap")
    shakemap_url = f"{BMKG_BASE_URL}/{shakemap}" if shakemap else None

    return EarthquakeEvent(
        id=event_id,
        datetime=dt_str,
        date=item.get("Tanggal", ""),
        time=item.get("Jam", ""),
        magnitude=magnitude,
        depth=depth_str,
        depth_km=depth_km,
        latitude=lat,
        longitude=lon,
        coordinates=[lon, lat],  # Standard GeoJSON order
        area=item.get("Wilayah", ""),
        potency=item.get("Potensi"),
        felt=item.get("Dirasakan"),
        shakemap_url=shakemap_url,
        source="BMKG",
    )


async def fetch_bmkg_feeds(
    mode: str = "LIVE",
    force_refresh: bool = False,
    simulate_failure: bool = False,
) -> BmkgFeedResult:
    """
    Fetch all 3 BMKG feeds concurrently, respecting caching and strict provenance.

    - In DEMO mode: Always returns deterministic local fixture (data_origin: 'fixture').
    - In LIVE mode:
        * Returns 'bmkg_cache' if in-memory cache is fresh (< 60s).
        * Otherwise fetches upstream 'bmkg_live'.
        * If upstream fails, fails closed (503) unless a recent cache exists.
        * NEVER substitutes local fixture for official LIVE mode.
    """
    # 1. DEMO mode: strictly use fixture
    if mode == "DEMO":
        fixture = _load_local_fixture()
        return BmkgFeedResult(
            data=fixture,
            data_origin="fixture",
            last_success_at=None,
            is_stale=False,
            fallback_header="DEMO_FIXTURE",
        )

    # 2. Simulated failure for audit and testing
    if simulate_failure:
        logger.info("Simulating BMKG upstream failure requested by client")
        raise UpstreamUnavailableError("Simulated upstream BMKG failure for fail-closed verification.")

    # 3. Check fresh in-memory cache
    if not force_refresh and _cache.is_fresh():
        return BmkgFeedResult(
            data=_cache._live_cache,
            data_origin="bmkg_cache",
            last_success_at=_cache.last_success_at_iso,
            is_stale=False,
            fallback_header="NONE",
        )

    # 4. Fetch live from upstream with concurrency lock
    async with _cache._lock:
        if not force_refresh and _cache.is_fresh():
            return BmkgFeedResult(
                data=_cache._live_cache,
                data_origin="bmkg_cache",
                last_success_at=_cache.last_success_at_iso,
                is_stale=False,
                fallback_header="NONE",
            )

        results: dict[str, Any] = {}
        headers = {
            "User-Agent": "NusaMatra-DataHub/0.1.0 (WIA 2026; OpenData Integration)",
            "Accept": "application/json",
        }

        upstream_ok = False
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                tasks = {key: client.get(url) for key, url in ENDPOINTS.items()}
                responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

                for key, resp in zip(tasks.keys(), responses):
                    if isinstance(resp, httpx.Response) and resp.status_code == 200:
                        results[key] = resp.json()
                    else:
                        logger.warning("Failed to fetch BMKG %s feed: %s", key, resp)

            if len(results) == len(ENDPOINTS):
                upstream_ok = True
        except Exception as exc:
            logger.error("Error fetching BMKG upstream: %s", exc)
            upstream_ok = False

        if upstream_ok:
            now = time.time()
            _cache._live_cache = results
            _cache._cached_at = now
            _cache._last_success_at = now
            return BmkgFeedResult(
                data=results,
                data_origin="bmkg_live",
                last_success_at=_cache.last_success_at_iso,
                is_stale=False,
                fallback_header="NONE",
            )

        # Upstream failed: check if recent live cache can be served as stale (< 10 minutes)
        if _cache.has_live_cache() and (time.time() - (_cache._last_success_at or 0)) < 600:
            logger.warning("Serving stale BMKG live cache due to upstream failure")
            return BmkgFeedResult(
                data=_cache._live_cache,
                data_origin="bmkg_cache",
                last_success_at=_cache.last_success_at_iso,
                is_stale=True,
                fallback_header="STALE_CACHE",
            )

        # FAIL CLOSED: Never substitute fixture in LIVE mode!
        logger.error("BMKG upstream unavailable and no valid live cache. Failing closed (503).")
        raise UpstreamUnavailableError("BMKG upstream live endpoints are unreachable, and no verified live cache exists.")


def determine_severity(mag: float) -> str:
    """Classify earthquake strength for styling."""
    if mag >= 6.0:
        return "SEVERE"
    if mag >= 5.0:
        return "HIGH"
    if mag >= 4.0:
        return "MODERATE"
    return "LOW"


async def get_latest_earthquake(
    mode: str = "LIVE",
    simulate_failure: bool = False,
) -> tuple[Optional[EarthquakeEvent], BmkgFeedResult]:
    """Retrieve the single latest earthquake event and pipeline metadata."""
    feed_res = await fetch_bmkg_feeds(mode=mode, simulate_failure=simulate_failure)
    raw_item = feed_res.data.get("autogempa", {}).get("Infogempa", {}).get("gempa", {})
    return parse_raw_gempa(raw_item), feed_res


async def get_recent_m5_earthquakes(
    mode: str = "LIVE",
    simulate_failure: bool = False,
) -> tuple[list[EarthquakeEvent], BmkgFeedResult]:
    """Retrieve up to 15 recent earthquakes with M >= 5.0 and pipeline metadata."""
    feed_res = await fetch_bmkg_feeds(mode=mode, simulate_failure=simulate_failure)
    raw_list = feed_res.data.get("gempaterkini", {}).get("Infogempa", {}).get("gempa", [])
    events = []
    for item in raw_list:
        parsed = parse_raw_gempa(item)
        if parsed:
            events.append(parsed)
    return events, feed_res


async def get_felt_earthquakes(
    mode: str = "LIVE",
    simulate_failure: bool = False,
) -> tuple[list[EarthquakeEvent], BmkgFeedResult]:
    """Retrieve up to 15 recent earthquakes felt by communities and pipeline metadata."""
    feed_res = await fetch_bmkg_feeds(mode=mode, simulate_failure=simulate_failure)
    raw_list = feed_res.data.get("gempadirasakan", {}).get("Infogempa", {}).get("gempa", [])
    events = []
    for item in raw_list:
        parsed = parse_raw_gempa(item)
        if parsed:
            events.append(parsed)
    return events, feed_res


async def get_earthquake_summary(
    mode: str = "LIVE",
    simulate_failure: bool = False,
) -> tuple[EarthquakeSummary, BmkgFeedResult]:
    """Generate executive summary of current seismic activity with provenance."""
    latest, feed_res = await get_latest_earthquake(mode=mode, simulate_failure=simulate_failure)
    recent_m5, _ = await get_recent_m5_earthquakes(mode=mode, simulate_failure=simulate_failure)
    felt, _ = await get_felt_earthquakes(mode=mode, simulate_failure=simulate_failure)

    max_mag = None
    if recent_m5:
        max_mag = max(e.magnitude for e in recent_m5)

    summary = EarthquakeSummary(
        latest=latest,
        recent_m5_count=len(recent_m5),
        felt_count=len(felt),
        max_magnitude_recent=max_mag,
        data_origin=feed_res.data_origin,
        last_success_at=feed_res.last_success_at,
        is_stale=feed_res.is_stale,
        cached_at=_cache.cached_at_iso,
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        agency="BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)",
        official_portal="https://data.bmkg.go.id/gempabumi/",
    )
    return summary, feed_res


async def get_merged_geojson(
    mode: str = "LIVE",
    simulate_failure: bool = False,
) -> tuple[EarthquakeGeoJsonCollection, BmkgFeedResult]:
    """
    Generate an RFC 7946 GeoJSON FeatureCollection merging all three feeds.
    Deduplicates events by timestamp/coordinates and includes rich properties
    for instant 3D rendering (pulse radius, severity, tsunami status, shakemap).
    """
    latest, feed_res = await get_latest_earthquake(mode=mode, simulate_failure=simulate_failure)
    recent_m5, _ = await get_recent_m5_earthquakes(mode=mode, simulate_failure=simulate_failure)
    felt, _ = await get_felt_earthquakes(mode=mode, simulate_failure=simulate_failure)

    # Deduplicate into dict keyed by (date, time, lat, lon)
    dedup: dict[str, EarthquakeEvent] = {}

    all_events = []
    if latest:
        all_events.append(latest)
    all_events.extend(recent_m5)
    all_events.extend(felt)

    for ev in all_events:
        key = f"{ev.datetime}_{ev.latitude:.2f}_{ev.longitude:.2f}"
        if key not in dedup:
            dedup[key] = ev
        else:
            # Enrich existing record with any missing fields
            existing = dedup[key]
            if not existing.felt and ev.felt:
                existing.felt = ev.felt
            if not existing.potency and ev.potency:
                existing.potency = ev.potency
            if not existing.shakemap_url and ev.shakemap_url:
                existing.shakemap_url = ev.shakemap_url

    features: list[GeoJsonFeature] = []
    for ev in dedup.values():
        tsunami_risk = False
        if ev.potency and "potensi tsunami" in ev.potency.lower() and "tidak" not in ev.potency.lower():
            tsunami_risk = True

        props = {
            "id": ev.id,
            "datetime": ev.datetime,
            "date": ev.date,
            "time": ev.time,
            "magnitude": ev.magnitude,
            "depth": ev.depth,
            "depth_km": ev.depth_km,
            "area": ev.area,
            "potency": ev.potency,
            "felt": ev.felt,
            "shakemap_url": ev.shakemap_url,
            "severity": determine_severity(ev.magnitude),
            "tsunami_risk": tsunami_risk,
            "source": ev.source,
            "data_origin": feed_res.data_origin,
            # Visualization helpers for 3D map engines:
            "visual_radius_px": max(6.0, (ev.magnitude ** 1.8) * 1.5),
            "visual_color": (
                "#ef4444" if ev.magnitude >= 6.0
                else "#f97316" if ev.magnitude >= 5.0
                else "#eab308" if ev.magnitude >= 4.0
                else "#3b82f6"
            ),
        }

        feature = GeoJsonFeature(
            id=ev.id,
            geometry=GeoJsonGeometry(coordinates=ev.coordinates),
            properties=props,
        )
        features.append(feature)

    # Sort descending by datetime (newest events first)
    features.sort(key=lambda f: f.properties.get("datetime", ""), reverse=True)

    metadata = EarthquakeMetadata(
        agency="BMKG",
        description="Indonesian Seismic Monitoring Epicenters (Unified Live Feed)",
        total_features=len(features),
        data_origin=feed_res.data_origin,
        last_success_at=feed_res.last_success_at,
        is_stale=feed_res.is_stale,
        cached_at=_cache.cached_at_iso,
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        source_portal="https://data.bmkg.go.id/gempabumi/",
    )

    return (
        EarthquakeGeoJsonCollection(
            metadata=metadata,
            features=features,
        ),
        feed_res,
    )
