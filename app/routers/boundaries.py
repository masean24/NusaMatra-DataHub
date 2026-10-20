"""
Boundaries router — GeoJSON/TopoJSON boundary delivery.
Matches API_CONTRACT_DRAFT.md Section 3.

For MVP DEMO, boundaries return a placeholder GeoJSON FeatureCollection
with region metadata but no actual geometry polygons.
Real geometries require BIG source data and PostGIS processing.
"""

from fastapi import APIRouter, Depends, Query, Request
from typing import Any, Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta, LiveUnavailableError
from app.config import settings

router = APIRouter(prefix="/boundaries", tags=["Boundaries"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": (
            "LIVE mode requested but not yet available. "
            "Retry with ``?mode=demo``."
        ),
    }
}

# Shared geometry status block injected into every boundary response
_GEOMETRY_STATUS = {
    "geometry_available": False,
    "geometry_type_returned": "Point",
    "source": "DEMO_PLACEHOLDER",
    "boundary_version": "BIG-Kepmendagri-300.2.2-2430-2025",
    "data_mode": "DEMO",
    "note": (
        "MVP DEMO returns label-point geometry only (centroid coordinates). "
        "Actual polygon boundaries require BIG source data "
        "(Ina-Geoportal / TanahAir Indonesia) and PostGIS processing. "
        "DO NOT use these geometries for spatial analysis."
    ),
}

_mode_param = Query(
    None,
    description=(
        "Data mode: ``demo`` (default) or ``live``. "
        "``live`` currently returns **503** (fail-closed)."
    ),
    include_in_schema=True,
)

_snapshot_param = Query(
    None,
    description="Pin a specific snapshot version (e.g. ``2026.10.0-wia-demo``).",
    include_in_schema=True,
)


@router.get(
    "/kabupaten",
    response_model=ApiResponse[dict[str, Any]],
    responses=_503_responses,
)
async def get_kabupaten_boundaries(
    request: Request,
    format: str = Query("geojson", pattern="^(geojson|topojson)$"),
    resolution: str = Query("low", pattern="^(low|high)$"),
    province_id: Optional[str] = Query(None, description="2-digit province filter"),
    mode: Optional[str] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Serve kabupaten/kota boundary geometries.

    Default format is GeoJSON (Blocker #8 — compatible with 3D renderer).
    TopoJSON available via ``?format=topojson``.

    > **⚠ DEMO MVP**: ``geometry_available: false``.
    > Returns **label-point** geometry (centroid coordinates), **not** polygon boundaries.
    > See ``geometry_status`` in the response for details.
    """
    _snapshot_id = request.state.snapshot_id

    conditions = ["r.level IN ('kabupaten', 'kota')"]
    params: list = []

    if province_id:
        conditions.append("r.parent_region_id = ?")
        params.append(province_id)

    where = " WHERE " + " AND ".join(conditions)

    cursor = await db.execute(
        f"""
        SELECT
            r.region_id, r.parent_region_id, r.name,
            r.kemendagri_code, r.bps_code,
            r.label_lng, r.label_lat,
            r.bbox_min_lng, r.bbox_min_lat, r.bbox_max_lng, r.bbox_max_lat
        FROM dim_regions r
        {where}
        ORDER BY r.region_id
        """,
        params,
    )
    rows = await cursor.fetchall()

    # Build GeoJSON FeatureCollection with placeholder point geometry
    features = []
    for r in rows:
        feature = {
            "type": "Feature",
            "properties": {
                "region_id": r["region_id"],
                "parent_region_id": r["parent_region_id"],
                "name": r["name"],
                "kemendagri_code": r["kemendagri_code"],
                "bps_code": r["bps_code"],
                "label_lng": r["label_lng"],
                "label_lat": r["label_lat"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [r["label_lng"], r["label_lat"]],
            },
            "bbox": [
                r["bbox_min_lng"] or 0,
                r["bbox_min_lat"] or 0,
                r["bbox_max_lng"] or 0,
                r["bbox_max_lat"] or 0,
            ],
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "geometry_status": _GEOMETRY_STATUS,
        "request_params": {
            "format": format,
            "resolution": resolution,
        },
    }

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            boundary_version=settings.boundary_version,
            total_count=len(features),
        ),
        data=geojson,
    )


@router.get(
    "/provinsi",
    response_model=ApiResponse[dict[str, Any]],
    responses=_503_responses,
)
async def get_provinsi_boundaries(
    request: Request,
    format: str = Query("geojson", pattern="^(geojson|topojson)$"),
    mode: Optional[str] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Serve province boundary geometries.

    > **⚠ DEMO MVP**: ``geometry_available: false``.
    > Returns **label-point** geometry (centroid coordinates), **not** polygon boundaries.
    > See ``geometry_status`` in the response for details.
    """
    _snapshot_id = request.state.snapshot_id

    cursor = await db.execute(
        """
        SELECT
            r.region_id, r.name,
            r.kemendagri_code, r.bps_code,
            r.label_lng, r.label_lat,
            r.bbox_min_lng, r.bbox_min_lat, r.bbox_max_lng, r.bbox_max_lat
        FROM dim_regions r
        WHERE r.level = 'provinsi'
        ORDER BY r.region_id
        """
    )
    rows = await cursor.fetchall()

    features = []
    for r in rows:
        feature = {
            "type": "Feature",
            "properties": {
                "region_id": r["region_id"],
                "name": r["name"],
                "kemendagri_code": r["kemendagri_code"],
                "bps_code": r["bps_code"],
                "label_lng": r["label_lng"],
                "label_lat": r["label_lat"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [r["label_lng"], r["label_lat"]],
            },
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "geometry_status": _GEOMETRY_STATUS,
        "request_params": {
            "format": format,
        },
    }

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            boundary_version=settings.boundary_version,
            total_count=len(features),
        ),
        data=geojson,
    )
