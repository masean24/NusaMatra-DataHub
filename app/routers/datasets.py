"""
Datasets router — provenance catalog.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from fastapi import APIRouter, Depends, Request
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta
from app.services.snapshot_service import list_datasets

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("", response_model=ApiResponse)
async def get_datasets(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all registered official government datasets with provenance."""
    snapshot_id = request.state.snapshot_id

    datasets = await list_datasets(db)

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            total_count=len(datasets),
        ),
        data=[d.model_dump() for d in datasets],
    )
