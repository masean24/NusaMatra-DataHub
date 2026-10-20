"""
Snapshots router — data version listing.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from fastapi import APIRouter, Depends, Request
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta
from app.services.snapshot_service import list_snapshots

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])


@router.get("", response_model=ApiResponse)
async def get_snapshots(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all available data snapshots (DEMO and LIVE)."""
    snapshot_id = request.state.snapshot_id

    snapshots = await list_snapshots(db)

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            total_count=len(snapshots),
        ),
        data=[s.model_dump() for s in snapshots],
    )
