"""
Indicators router — catalog, values, and composite query.
Matches API_CONTRACT_DRAFT.md Sections 4.1, 4.2, 4.3.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional
import aiosqlite

from app.database import get_db
from app.models.common import (
    ApiResponse,
    ResponseMeta,
    LiveUnavailableError,
    WeightValidationError,
)
from app.models.indicators import (
    CompositePreset,
    CompositeQueryRequest,
    CompositeQueryResult,
    IndicatorCatalogItem,
    IndicatorValuesData,
)
from app.services.indicator_service import list_indicators, get_indicator_values
from app.services.composite_service import compute_composite_scores, COMPOSITE_PRESETS

router = APIRouter(prefix="/indicators", tags=["Indicators"])

_503_responses = {
    503: {
        "model": LiveUnavailableError,
        "description": (
            "LIVE mode requested but not yet available. "
            "Retry with ``?mode=demo``."
        ),
    }
}

_mode_param = Query(
    None,
    description=(
        "Data mode: ``demo`` (default) or ``live``. "
        "``live`` serves verified official government data. "
        "Earthquake endpoints are fail-closed when upstream BMKG is unavailable."
    ),
    include_in_schema=True,
)

_snapshot_param = Query(
    None,
    description="Pin a specific snapshot version (e.g. ``2026.10.0-wia-demo``).",
    include_in_schema=True,
)


@router.get(
    "",
    response_model=ApiResponse[dict[str, list[IndicatorCatalogItem]]],
    responses=_503_responses,
)
async def get_indicators(
    request: Request,
    mode: Optional[str] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return the full indicator catalog grouped by category."""
    _snapshot_id = request.state.snapshot_id

    indicators = await list_indicators(db)

    # Group by category
    grouped: dict[str, list] = {}
    for ind in indicators:
        cat = ind.category
        grouped.setdefault(cat, []).append(ind.model_dump())

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(indicators),
        ),
        data=grouped,
    )


@router.get(
    "/{indicator_id}/values",
    response_model=ApiResponse[IndicatorValuesData],
    responses=_503_responses,
)
async def get_indicator_values_endpoint(
    request: Request,
    indicator_id: str,
    mode: Optional[str] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return one indicator's values for all 514 regions (fast dict format)."""
    _snapshot_id = request.state.snapshot_id

    result = await get_indicator_values(db, indicator_id, snapshot_id=_snapshot_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Indicator '{indicator_id}' not found.",
        )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(result.values_by_region),
        ),
        data=result,
    )


@router.post(
    "/composite-query",
    response_model=ApiResponse[CompositeQueryResult],
    responses={
        **_503_responses,
        422: {
            "model": WeightValidationError,
            "description": (
                "Weight validation failed. "
                "Weights must be integer basis points summing to exactly 10000, "
                "and all ``indicator_id`` keys must exist in the catalog."
            ),
        },
    },
)
async def composite_query(
    request: Request,
    body: CompositeQueryRequest,
    mode: Optional[str] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Calculate weighted composite scores across all regions.

    **Weight rules (enforced, returns 422 on violation):**
    - Weights are integer **basis points** (1 bp = 1/10000 = 0.01 %).
    - Sum of all weights **MUST equal exactly 10000** (= 100 %).
    - Every ``indicator_id`` key **must exist** in the indicator catalog.

    **Example (sum = 10000):**
    ```json
    {
      "weights": {
        "dis_multihazard_index": 3500,
        "soc_poverty_rate": 2500,
        "edu_damaged_classrooms_pct": 2000,
        "hlt_stunting_prevalence": 2000
      }
    }
    ```
    """
    _snapshot_id = request.state.snapshot_id

    try:
        result = await compute_composite_scores(db, body, snapshot_id=_snapshot_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "code": "WEIGHT_VALIDATION_ERROR",
                "message": str(exc),
            },
        )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=result.total_regions,
        ),
        data=result,
    )


@router.get(
    "/composite-presets",
    response_model=ApiResponse[list[CompositePreset]],
    responses=_503_responses,
)
async def get_composite_presets(
    request: Request,
    mode: Optional[str] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
):
    """
    Get curated policy-weighting presets for composite scoring.

    Provides ready-to-use scenario weights summing to exactly 10,000 basis points (100%).
    Frontend map clients can send these directly to POST /indicators/composite-query.
    """
    _snapshot_id = request.state.snapshot_id

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(COMPOSITE_PRESETS),
        ),
        data=COMPOSITE_PRESETS,
    )
