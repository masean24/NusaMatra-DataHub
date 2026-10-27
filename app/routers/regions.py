"""
Regions router — GET /api/v1/regions and GET /api/v1/regions/{region_id}
Matches API_CONTRACT_DRAFT.md Section 2.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Literal, Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta, LiveUnavailableError
from app.models.regions import RegionSummary, RegionDetail
from app.services.region_service import list_regions, get_region_detail
from app.services.snapshot_registry import snapshot_meta_fields

router = APIRouter(prefix="/regions", tags=["Regions"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": "LIVE mode requested but verified database unavailable.",
    }
}


@router.get(
    "",
    response_model=ApiResponse[list[RegionSummary]],
    responses=_503_responses,
)
async def get_regions(
    request: Request,
    level: str = Query("kabupaten_kota", pattern="^(kabupaten_kota|provinsi|all)$"),
    parent_id: Optional[str] = Query(None, description="2-digit province code filter"),
    q: Optional[str] = Query(None, description="Text search on name or code"),
    mode: Optional[Literal["demo", "live"]] = Query(
        None,
        pattern="^(demo|live)$",
        description="Data mode: ``demo`` (default) or ``live``.",
        include_in_schema=True,
    ),
    snapshot_id: Optional[str] = Query(
        None,
        description="Pin a specific snapshot version (e.g. ``2026.10.0-wia-demo``).",
        include_in_schema=True,
    ),
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all administrative regions with optional filters."""
    snapshot_id = request.state.snapshot_id

    regions = await list_regions(
        db, level=level, parent_id=parent_id, q=q, snapshot_id=snapshot_id,
    )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            total_count=len(regions),
            **snapshot_meta_fields(request),
        ),
        data=regions,
    )


@router.get(
    "/{region_id}",
    response_model=ApiResponse[RegionDetail],
    responses=_503_responses,
)
async def get_region(
    request: Request,
    region_id: str,
    mode: Optional[Literal["demo", "live"]] = Query(
        None,
        pattern="^(demo|live)$",
        description="Data mode: ``demo`` (default) or ``live``.",
        include_in_schema=True,
    ),
    snapshot_id: Optional[str] = Query(
        None,
        description="Pin a specific snapshot version.",
        include_in_schema=True,
    ),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get full profile for a single region, including all indicator values."""
    _snapshot_id = request.state.snapshot_id

    detail = await get_region_detail(db, region_id, snapshot_id=_snapshot_id)

    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region_id}' not found.",
        )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            **snapshot_meta_fields(request),
        ),
        data=detail,
    )
