"""
Boundaries router — GeoJSON/TopoJSON boundary delivery.
Matches API_CONTRACT_DRAFT.md Section 3.

Backed by official Badan Informasi Geospasial (BIG) 2026 polygon geometries:
- 38 Provinsi (including 4 new Papua provinces)
- 514 Kabupaten / Kota
- Optimized with 'low' (~6MB / ~1.6MB gzipped) and 'high' resolutions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pathlib import Path
from typing import Any, Literal, Optional
import aiosqlite
import json

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta, LiveUnavailableError
from app.services.snapshot_registry import snapshot_meta_fields

router = APIRouter(prefix="/boundaries", tags=["Boundaries"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": "LIVE mode requested but verified database unavailable.",
    }
}

# Official geometry status block injected into every boundary response
_GEOMETRY_STATUS = {
    "geometry_available": True,
    "geometry_type_returned": "MultiPolygon",
    "source": "Badan Informasi Geospasial (BIG) 2026",
    "boundary_version": "BIG-Kepmendagri-300.2.2-2430-2025",
    "data_mode": "REAL_OFFICIAL",
    "note": (
        "Official 2026 administrative boundary polygons from Badan Informasi Geospasial (BIG). "
        "Topologically dissolved and simplified for web 3D GIS visualization."
    ),
}

_FALLBACK_GEOMETRY_STATUS = {
    "geometry_available": False,
    "geometry_type_returned": "Point",
    "source": "DEMO_PLACEHOLDER",
    "boundary_version": "BIG-Kepmendagri-300.2.2-2430-2025",
    "data_mode": "DEMO",
    "note": (
        "MVP DEMO returns label-point geometry only (centroid coordinates). "
        "Polygon source file missing, fallback in effect."
    ),
}

_mode_param = Query(
    None,
    pattern="^(demo|live)$",
    description="Data mode: ``demo`` (default) or ``live``.",
    include_in_schema=True,
)

_snapshot_param = Query(
    None,
    description="Pin a specific snapshot version (e.g. ``2026.10.0-wia-demo``).",
    include_in_schema=True,
)

_BOUNDARIES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "boundaries"
_CACHE: dict[str, dict[str, Any]] = {}


def _load_boundary_geojson(filename: str) -> Optional[dict[str, Any]]:
    """Load and cache boundary GeoJSON files in memory."""
    if filename in _CACHE:
        return _CACHE[filename]
    path = _BOUNDARIES_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _CACHE[filename] = data
            return data
    return None


@router.get(
    "/kabupaten",
    response_model=ApiResponse[dict[str, Any]],
    responses=_503_responses,
)
async def get_kabupaten_boundaries(
    request: Request,
    format: str = Query("geojson", pattern="^(geojson)$", description="Output format. Only ``geojson`` is currently supported."),
    resolution: str = Query("low", pattern="^(low|high)$"),
    province_id: Optional[str] = Query(None, description="2-digit province filter"),
    mode: Optional[Literal["demo", "live"]] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Serve kabupaten/kota boundary geometries.

    Default format is GeoJSON (compatible with 3D renderer).
    Supports 'low' (fast web 3D map) and 'high' (detailed zoom) resolutions.
    Backed by official 2026 Badan Informasi Geospasial (BIG) polygon boundaries.

    > **Note:** ``topojson`` format is not yet implemented. Use ``geojson``.
    """
    _snapshot_id = request.state.snapshot_id

    filename = f"indonesia_kabupaten_{resolution}.geojson"
    raw_geojson = _load_boundary_geojson(filename)

    if raw_geojson:
        features = raw_geojson.get("features", [])
        if province_id:
            features = [
                f for f in features
                if f.get("properties", {}).get("parent_region_id") == province_id
                or f.get("properties", {}).get("province_id") == province_id
            ]

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
                **snapshot_meta_fields(request),
                total_count=len(features),
            ),
            data=geojson,
        )

    # Fallback to database point query if geojson file not found
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
        "geometry_status": _FALLBACK_GEOMETRY_STATUS,
        "request_params": {
            "format": format,
            "resolution": resolution,
        },
    }

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            **snapshot_meta_fields(request),
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
    format: str = Query("geojson", pattern="^(geojson)$", description="Output format. Only ``geojson`` is currently supported."),
    resolution: str = Query("low", pattern="^(low|high)$"),
    mode: Optional[Literal["demo", "live"]] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Serve province boundary geometries.

    Default format is GeoJSON (38 provinces including 4 new Papua provinces).
    Backed by official 2026 Badan Informasi Geospasial (BIG) polygon boundaries.

    > **Note:** ``topojson`` format is not yet implemented. Use ``geojson``.
    """
    _snapshot_id = request.state.snapshot_id

    filename = f"indonesia_provinsi_{resolution}.geojson"
    raw_geojson = _load_boundary_geojson(filename)

    if raw_geojson:
        features = raw_geojson.get("features", [])
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
                **snapshot_meta_fields(request),
                total_count=len(features),
            ),
            data=geojson,
        )

    # Fallback to database point query if geojson file not found
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
        "geometry_status": _FALLBACK_GEOMETRY_STATUS,
        "request_params": {
            "format": format,
        },
    }

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            **snapshot_meta_fields(request),
            total_count=len(features),
        ),
        data=geojson,
    )
