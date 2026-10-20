"""
Health check router.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from fastapi import APIRouter, Request

from app.config import settings
from app.database import check_db_health
from app.models.health import HealthResponse, DatabaseHealth

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Check API health: database connectivity, mode, and fallback status."""

    db_health = await check_db_health()

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
