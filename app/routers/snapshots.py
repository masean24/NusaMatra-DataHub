"""
Snapshots router — data version listing.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from fastapi import APIRouter, Depends, Query, Request
from typing import Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta, LiveUnavailableError
from app.models.health import SnapshotInfo
from app.services.snapshot_service import list_snapshots

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": "LIVE mode requested but not yet available.",
    }
}


@router.get(
    "",
    response_model=ApiResponse[list[SnapshotInfo]],
    responses=_503_responses,
)
async def get_snapshots(
    request: Request,
    mode: Optional[str] = Query(
        None,
        description=(
            "Data mode: ``demo`` (default) or ``live``. "
            "``live`` currently returns **503** (fail-closed)."
        ),
        include_in_schema=True,
    ),
    snapshot_id: Optional[str] = Query(
        None,
        description="Pin a specific snapshot version.",
        include_in_schema=True,
    ),
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all available data snapshots (DEMO and LIVE)."""
    _snapshot_id = request.state.snapshot_id

    snapshots = await list_snapshots(db)

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(snapshots),
        ),
        data=snapshots,
    )
