"""
Snapshots router — data version listing.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Literal, Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta, LiveUnavailableError
from app.models.health import SnapshotInfo
from app.services.snapshot_registry import snapshot_meta_fields
from app.services.snapshot_service import get_snapshot, list_snapshots

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": "LIVE mode requested but verified database unavailable.",
    }
}


@router.get(
    "",
    response_model=ApiResponse[list[SnapshotInfo]],
    responses=_503_responses,
)
async def get_snapshots(
    request: Request,
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
    """List all available data snapshots (DEMO and LIVE)."""
    _snapshot_id = request.state.snapshot_id

    snapshots = await list_snapshots(db)

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(snapshots),
            **snapshot_meta_fields(request),
        ),
        data=snapshots,
    )


@router.get(
    "/{snapshot_id}",
    response_model=ApiResponse[SnapshotInfo],
    responses=_503_responses,
)
async def get_snapshot_detail(
    request: Request,
    snapshot_id: str,
    mode: Optional[Literal["demo", "live"]] = Query(
        None,
        pattern="^(demo|live)$",
        description="Data mode: ``demo`` (default) or ``live``.",
        include_in_schema=True,
    ),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return immutable metadata for one exact snapshot ID."""
    snapshot = await get_snapshot(db, snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "SNAPSHOT_NOT_FOUND",
                "message": f"Snapshot '{snapshot_id}' was not found.",
            },
        )
    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            **snapshot_meta_fields(request),
        ),
        data=snapshot,
    )
