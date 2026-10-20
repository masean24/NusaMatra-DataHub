"""
Regions router — GET /api/v1/regions and GET /api/v1/regions/{region_id}
Matches API_CONTRACT_DRAFT.md Section 2.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta
from app.services.region_service import list_regions, get_region_detail
from app.config import settings

router = APIRouter(prefix="/regions", tags=["Regions"])


@router.get("", response_model=ApiResponse)
async def get_regions(
    request: Request,
    level: str = Query("kabupaten_kota", pattern="^(kabupaten_kota|provinsi|all)$"),
    parent_id: Optional[str] = Query(None, description="2-digit province code filter"),
    q: Optional[str] = Query(None, description="Text search on name or code"),
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
            boundary_version=settings.boundary_version,
            total_count=len(regions),
        ),
        data=[r.model_dump() for r in regions],
    )


@router.get("/{region_id}", response_model=ApiResponse)
async def get_region(
    request: Request,
    region_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get full profile for a single region, including all indicator values."""
    snapshot_id = request.state.snapshot_id

    detail = await get_region_detail(db, region_id, snapshot_id=snapshot_id)

    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region_id}' not found.",
        )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
        ),
        data=detail.model_dump(),
    )
