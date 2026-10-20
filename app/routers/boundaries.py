"""
Boundaries router — GeoJSON/TopoJSON boundary delivery.
Matches API_CONTRACT_DRAFT.md Section 3.

For MVP DEMO, boundaries return a placeholder GeoJSON FeatureCollection
with region metadata but no actual geometry polygons.
Real geometries require BIG source data and PostGIS processing.
"""

from fastapi import APIRouter, Depends, Query, Request
from typing import Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta
from app.config import settings

router = APIRouter(prefix="/boundaries", tags=["Boundaries"])


@router.get("/kabupaten", response_model=ApiResponse)
async def get_kabupaten_boundaries(
    request: Request,
    format: str = Query("geojson", pattern="^(geojson|topojson)$"),
    resolution: str = Query("low", pattern="^(low|high)$"),
    province_id: Optional[str] = Query(None, description="2-digit province filter"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Serve kabupaten/kota boundary geometries.

    Default format is GeoJSON (Blocker #8 — compatible with 3D renderer).
    TopoJSON available via ?format=topojson.

    Note: MVP DEMO returns placeholder features without actual polygon geometry.
    """
    snapshot_id = request.state.snapshot_id

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
        "_note": (
            "DEMO MVP: Geometries are placeholder Points (label coordinates). "
            "Actual polygon boundaries require BIG source data and PostGIS processing. "
            f"Requested format='{format}', resolution='{resolution}'."
        ),
    }

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            boundary_version=settings.boundary_version,
            total_count=len(features),
        ),
        data=geojson,
    )


@router.get("/provinsi", response_model=ApiResponse)
async def get_provinsi_boundaries(
    request: Request,
    format: str = Query("geojson", pattern="^(geojson|topojson)$"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Serve province boundary geometries (placeholder for DEMO)."""
    snapshot_id = request.state.snapshot_id

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
        "_note": "DEMO MVP: Placeholder point geometries.",
    }

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            boundary_version=settings.boundary_version,
            total_count=len(features),
        ),
        data=geojson,
    )
