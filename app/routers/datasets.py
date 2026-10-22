"""
Datasets router — provenance catalog.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from fastapi import APIRouter, Depends, Query, Request
from typing import Optional
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta, LiveUnavailableError
from app.models.health import DatasetInfo
from app.services.snapshot_service import list_datasets

router = APIRouter(prefix="/datasets", tags=["Datasets"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": "LIVE mode requested but verified database unavailable.",
    }
}


@router.get(
    "",
    response_model=ApiResponse[list[DatasetInfo]],
    responses=_503_responses,
)
async def get_datasets(
    request: Request,
    mode: Optional[str] = Query(
        None,
        description=(
            "Data mode: ``demo`` (default) or ``live``. "
            "``live`` serves verified official government data."
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
    """List all registered official government datasets with provenance."""
    _snapshot_id = request.state.snapshot_id

    datasets = await list_datasets(db)

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(datasets),
        ),
        data=datasets,
    )
