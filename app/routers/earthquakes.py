"""
Earthquakes router — BMKG Real-Time Seismic Activity Integration.

Provides live and cached earthquake feeds sourced from BMKG (Badan Meteorologi,
Klimatologi, dan Geofisika) Open Data portal.

Endpoints:
- GET /api/v1/earthquakes/latest   — Single latest earthquake + Shakemap
- GET /api/v1/earthquakes/recent   — 15 recent earthquakes with M >= 5.0
- GET /api/v1/earthquakes/felt     — 15 recent felt earthquakes with MMI intensities
- GET /api/v1/earthquakes/geojson  — RFC 7946 GeoJSON FeatureCollection for 3D map layers
- GET /api/v1/earthquakes/summary  — Executive national seismic activity summary
"""

from typing import Literal, Optional
from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from app.models.common import ApiResponse, ResponseMeta
from app.models.earthquakes import (
    EarthquakeEvent,
    EarthquakeGeoJsonCollection,
    EarthquakeSummary,
)
from app.services.bmkg_service import (
    UpstreamUnavailableError,
    get_earthquake_summary,
    get_felt_earthquakes,
    get_latest_earthquake,
    get_merged_geojson,
    get_recent_m5_earthquakes,
)

router = APIRouter(prefix="/earthquakes", tags=["Disaster & Climate (BMKG)"])


def _check_simulation(request: Request) -> bool:
    """Helper to detect upstream failure simulation requested by audit/test clients."""
    sim_query = request.query_params.get("simulate_upstream_failure", "").lower()
    sim_header = request.headers.get("x-simulate-upstream-failure", "").lower()
    return sim_query in ("true", "1") or sim_header in ("true", "1")


def _upstream_503_response(exc: Exception) -> JSONResponse:
    """Standard fail-closed 503 response when BMKG upstream live service is unreachable."""
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "code": "UPSTREAM_UNAVAILABLE",
            "message": (
                "BMKG live earthquake upstream service is currently unreachable. "
                "LIVE mode fails closed to prevent presenting unverified or synthetic data as official events."
            ),
            "detail": str(exc),
        },
        headers={
            "X-NusaMatra-Mode": "LIVE",
            "X-Data-Fallback": "UNAVAILABLE",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get(
    "/latest",
    response_model=ApiResponse[Optional[EarthquakeEvent]],
    summary="Get single latest earthquake event",
)
async def get_latest(
    request: Request,
    response: Response,
    mode: Optional[Literal["demo", "live"]] = Query(None, pattern="^(demo|live)$", description="Data mode: demo or live"),
    simulate_upstream_failure: Optional[bool] = Query(False, description="Simulate upstream BMKG outage"),
):
    """
    Fetch the latest recorded earthquake event published by BMKG.
    Includes Shakemap image URL, epicenter coordinates, depth, and tsunami potential.
    """
    data_mode = getattr(request.state, "data_mode", "LIVE")
    snapshot_id = getattr(request.state, "snapshot_id", "2026.10.0-official-live")
    simulate = _check_simulation(request) or bool(simulate_upstream_failure)

    try:
        latest, feed_res = await get_latest_earthquake(mode=data_mode, simulate_failure=simulate)
    except UpstreamUnavailableError as exc:
        return _upstream_503_response(exc)

    response.headers["X-Data-Fallback"] = feed_res.fallback_header

    return ApiResponse(
        status="success",
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=data_mode,
            total_count=1 if latest else 0,
            data_origin=feed_res.data_origin,
            last_success_at=feed_res.last_success_at,
            is_stale=feed_res.is_stale,
        ),
        data=latest,
    )


@router.get(
    "/recent",
    response_model=ApiResponse[list[EarthquakeEvent]],
    summary="Get 15 recent earthquakes with M >= 5.0",
)
async def get_recent_m5(
    request: Request,
    response: Response,
    mode: Optional[Literal["demo", "live"]] = Query(None, pattern="^(demo|live)$", description="Data mode: demo or live"),
    simulate_upstream_failure: Optional[bool] = Query(False, description="Simulate upstream BMKG outage"),
):
    """
    Fetch up to 15 recent significant earthquakes (magnitude >= 5.0) across Indonesia.
    """
    data_mode = getattr(request.state, "data_mode", "LIVE")
    snapshot_id = getattr(request.state, "snapshot_id", "2026.10.0-official-live")
    simulate = _check_simulation(request) or bool(simulate_upstream_failure)

    try:
        events, feed_res = await get_recent_m5_earthquakes(mode=data_mode, simulate_failure=simulate)
    except UpstreamUnavailableError as exc:
        return _upstream_503_response(exc)

    response.headers["X-Data-Fallback"] = feed_res.fallback_header

    return ApiResponse(
        status="success",
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=data_mode,
            total_count=len(events),
            data_origin=feed_res.data_origin,
            last_success_at=feed_res.last_success_at,
            is_stale=feed_res.is_stale,
        ),
        data=events,
    )


@router.get(
    "/felt",
    response_model=ApiResponse[list[EarthquakeEvent]],
    summary="Get 15 recent earthquakes felt by communities",
)
async def get_felt(
    request: Request,
    response: Response,
    mode: Optional[Literal["demo", "live"]] = Query(None, pattern="^(demo|live)$", description="Data mode: demo or live"),
    simulate_upstream_failure: Optional[bool] = Query(False, description="Simulate upstream BMKG outage"),
):
    """
    Fetch up to 15 recent earthquakes reported felt by communities,
    including Modified Mercalli Intensity (MMI) levels and affected regencies.
    """
    data_mode = getattr(request.state, "data_mode", "LIVE")
    snapshot_id = getattr(request.state, "snapshot_id", "2026.10.0-official-live")
    simulate = _check_simulation(request) or bool(simulate_upstream_failure)

    try:
        events, feed_res = await get_felt_earthquakes(mode=data_mode, simulate_failure=simulate)
    except UpstreamUnavailableError as exc:
        return _upstream_503_response(exc)

    response.headers["X-Data-Fallback"] = feed_res.fallback_header

    return ApiResponse(
        status="success",
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=data_mode,
            total_count=len(events),
            data_origin=feed_res.data_origin,
            last_success_at=feed_res.last_success_at,
            is_stale=feed_res.is_stale,
        ),
        data=events,
    )


@router.get(
    "/geojson",
    response_model=EarthquakeGeoJsonCollection,
    summary="Get GeoJSON FeatureCollection of epicenters for 3D maps",
)
async def get_geojson(
    request: Request,
    response: Response,
    mode: Optional[Literal["demo", "live"]] = Query(None, pattern="^(demo|live)$", description="Data mode: demo or live"),
    simulate_upstream_failure: Optional[bool] = Query(False, description="Simulate upstream BMKG outage"),
):
    """
    Returns an RFC 7946 standard GeoJSON FeatureCollection merging all recent and felt
    earthquake epicenters.

    Ready for direct consumption by 3D map engines (Mapbox GL, Deck.gl, MapLibre, Cesium).
    Features include visual properties:
    - ``visual_radius_px``: dynamically scaled circle size based on magnitude
    - ``visual_color``: hex color code categorized by severity (yellow to deep red)
    - ``severity``: LOW, MODERATE, HIGH, SEVERE
    - ``depth_km``: numeric depth for 3D extrusion/elevation
    - ``tsunami_risk``: boolean alert indicator
    """
    data_mode = getattr(request.state, "data_mode", "LIVE")
    simulate = _check_simulation(request) or bool(simulate_upstream_failure)

    try:
        geojson_data, feed_res = await get_merged_geojson(mode=data_mode, simulate_failure=simulate)
    except UpstreamUnavailableError as exc:
        return _upstream_503_response(exc)

    response.headers["X-Data-Fallback"] = feed_res.fallback_header

    return geojson_data


@router.get(
    "/summary",
    response_model=ApiResponse[EarthquakeSummary],
    summary="Get executive summary of national earthquake activity",
)
async def get_summary(
    request: Request,
    response: Response,
    mode: Optional[Literal["demo", "live"]] = Query(None, pattern="^(demo|live)$", description="Data mode: demo or live"),
    simulate_upstream_failure: Optional[bool] = Query(False, description="Simulate upstream BMKG outage"),
):
    """
    Get executive summary of current seismic status in Indonesia:
    latest event, total count of M5+ events, count of felt events, and cache TTL.
    """
    data_mode = getattr(request.state, "data_mode", "LIVE")
    snapshot_id = getattr(request.state, "snapshot_id", "2026.10.0-official-live")
    simulate = _check_simulation(request) or bool(simulate_upstream_failure)

    try:
        summary, feed_res = await get_earthquake_summary(mode=data_mode, simulate_failure=simulate)
    except UpstreamUnavailableError as exc:
        return _upstream_503_response(exc)

    response.headers["X-Data-Fallback"] = feed_res.fallback_header

    return ApiResponse(
        status="success",
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=data_mode,
            total_count=1,
            data_origin=feed_res.data_origin,
            last_success_at=feed_res.last_success_at,
            is_stale=feed_res.is_stale,
        ),
        data=summary,
    )
