"""
Indicators router — catalog, values, and composite query.
Matches API_CONTRACT_DRAFT.md Sections 4.1, 4.2, 4.3.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Any, Literal, Optional
import aiosqlite

from app.database import get_db
from app.models.common import (
    ApiResponse,
    CoverageMeta,
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
        "description": "LIVE mode requested but verified database unavailable.",
    }
}

_mode_param = Query(
    None,
    pattern="^(demo|live)$",
    description="Data mode: ``demo`` (default) or ``live``.",
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
    mode: Optional[Literal["demo", "live"]] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return the full indicator catalog grouped by category."""
    _snapshot_id = request.state.snapshot_id

    indicators = await list_indicators(db, snapshot_id=_snapshot_id)

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
    "/coverage",
    response_model=ApiResponse[dict[str, Any]],
)
async def get_indicators_coverage(
    request: Request,
    mode: Optional[Literal["demo", "live"]] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Return comprehensive data coverage summary for all 33 indicators in the active snapshot.

    Enables frontend 3D map clients to immediately identify which indicators/layers have verified data.
    """
    _snapshot_id = request.state.snapshot_id
    cursor = await db.execute(
        """
        SELECT 
            i.indicator_id, i.indicator_name, i.category,
            COUNT(f.region_id) as coverage_count
        FROM dim_indicators i
        LEFT JOIN fact_indicator_values f 
            ON i.indicator_id = f.indicator_id AND f.snapshot_id = ?
        GROUP BY i.indicator_id
        ORDER BY i.category, i.indicator_id
        """,
        [_snapshot_id],
    )
    rows = await cursor.fetchall()

    total_reg = 514
    indicators_info = {}
    available_count = 0
    empty_indicators = []

    for r in rows:
        cnt = r["coverage_count"]
        is_avail = cnt > 0
        if is_avail:
            available_count += 1
        else:
            empty_indicators.append(r["indicator_id"])

        indicators_info[r["indicator_id"]] = {
            "name": r["indicator_name"],
            "category": r["category"],
            "available": is_avail,
            "coverage_count": cnt,
            "coverage_pct": round((cnt / total_reg) * 100, 1),
        }

    data = {
        "snapshot_id": _snapshot_id,
        "mode": request.state.data_mode,
        "total_indicators": len(rows),
        "available_indicators_count": available_count,
        "empty_indicators_count": len(empty_indicators),
        "empty_indicators": empty_indicators,
        "indicators": indicators_info,
    }

    coverage_meta = CoverageMeta(
        available=available_count,
        total_regions=total_reg,
        missing_region_ids=empty_indicators,
        mode=request.state.data_mode,
    )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=len(rows),
            coverage=coverage_meta,
        ),
        data=data,
    )


@router.get(
    "/{indicator_id}/values",
    response_model=ApiResponse[IndicatorValuesData],
    responses=_503_responses,
)
async def get_indicator_values_endpoint(
    request: Request,
    indicator_id: str,
    mode: Optional[Literal["demo", "live"]] = _mode_param,
    snapshot_id: Optional[str] = _snapshot_param,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return one indicator's values for all 514 regions (fast dict format) with coverage metadata."""
    _snapshot_id = request.state.snapshot_id

    result = await get_indicator_values(db, indicator_id, snapshot_id=_snapshot_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Indicator '{indicator_id}' not found.",
        )

    available = len(result.values_by_region)
    missing_ids = []
    if available < 514:
        reg_cursor = await db.execute(
            "SELECT region_id FROM dim_regions WHERE level IN ('kabupaten', 'kota') ORDER BY region_id"
        )
        reg_rows = await reg_cursor.fetchall()
        missing_ids = [r["region_id"] for r in reg_rows if r["region_id"] not in result.values_by_region]

    coverage_meta = CoverageMeta(
        available=available,
        total_regions=514,
        missing_region_ids=missing_ids,
        mode=request.state.data_mode,
    )

    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=_snapshot_id,
            mode=request.state.data_mode,
            total_count=available,
            coverage=coverage_meta,
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
    mode: Optional[Literal["demo", "live"]] = _mode_param,
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
    mode: Optional[Literal["demo", "live"]] = _mode_param,
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
