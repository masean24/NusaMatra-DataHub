"""
Indicators router — catalog, values, and composite query.
Matches API_CONTRACT_DRAFT.md Sections 4.1, 4.2, 4.3.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
import aiosqlite

from app.database import get_db
from app.models.common import ApiResponse, ResponseMeta
from app.models.indicators import CompositeQueryRequest
from app.services.indicator_service import list_indicators, get_indicator_values
from app.services.composite_service import compute_composite_scores

router = APIRouter(prefix="/indicators", tags=["Indicators"])


@router.get("", response_model=ApiResponse)
async def get_indicators(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return the full indicator catalog grouped by category."""
    snapshot_id = request.state.snapshot_id

    indicators = await list_indicators(db)

    # Group by category
    grouped: dict[str, list] = {}
    for ind in indicators:
        cat = ind.category
        grouped.setdefault(cat, []).append(ind.model_dump())

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
            total_count=len(indicators),
        ),
        data=grouped,
    )


@router.get("/{indicator_id}/values", response_model=ApiResponse)
async def get_indicator_values_endpoint(
    request: Request,
    indicator_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return one indicator's values for all 514 regions (fast dict format)."""
    snapshot_id = request.state.snapshot_id

    result = await get_indicator_values(db, indicator_id, snapshot_id=snapshot_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Indicator '{indicator_id}' not found.",
        )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
        ),
        data=result.model_dump(),
    )


@router.post("/composite-query", response_model=ApiResponse)
async def composite_query(
    request: Request,
    body: CompositeQueryRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Calculate weighted composite scores across all regions.

    Weights are in integer basis points (1/10000).
    Sum of all weights MUST equal exactly 10000.
    """
    snapshot_id = request.state.snapshot_id

    try:
        result = await compute_composite_scores(db, body, snapshot_id=snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=snapshot_id,
            mode=request.state.data_mode,
        ),
        data=result.model_dump(),
    )
