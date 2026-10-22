"""
Health check router.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from typing import Literal, Optional
from fastapi import APIRouter, Query, Request

from app.config import settings
from app.database import check_db_health
from app.models.health import HealthResponse, DatabaseHealth

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    mode: Optional[Literal["demo", "live"]] = Query(None, description="Data mode: 'demo' or 'live'"),
):
    """Check API health: database connectivity, mode, and fallback status."""

    mode = getattr(request.state, "data_mode", settings.default_mode)
    db_health = await check_db_health(mode=mode)

    overall = "healthy" if db_health["status"] == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        version=settings.app_version,
        mode=request.state.data_mode,
        active_snapshot=request.state.snapshot_id,
        database=DatabaseHealth(**db_health),
        redis="not_configured",
        static_fallback_ready=True,
    )
