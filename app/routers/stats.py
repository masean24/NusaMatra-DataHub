"""
Telemetry and System Stats Router.

Provides:
- GET /api/v1/stats: JSON metrics summary for SDKs and dashboard widgets
"""

from pathlib import Path
from fastapi import APIRouter, Request

from app.models.common import ApiResponse, ResponseMeta
from app.services.telemetry_service import telemetry
from app.config import settings

router = APIRouter(tags=["System"])

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "stats.html"


def get_stats_html() -> str:
    """Read the stats HTML template."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "<h1>Nusa Matra Telemetry Dashboard</h1>"


@router.get(
    "/stats",
    response_model=ApiResponse[dict],
    summary="Get real-time system usage and telemetry metrics (JSON)",
)
async def get_stats_json(request: Request):
    """
    Return comprehensive API telemetry:
    - Uptime and total requests
    - Average latency (ms) and status code distribution
    - Most active endpoints and runtime mode ratios (DEMO vs LIVE)
    - Recent requests stream
    """
    summary = telemetry.get_summary()
    return ApiResponse(
        meta=ResponseMeta(
            snapshot_id=getattr(request.state, "snapshot_id", settings.default_snapshot_id),
            mode=getattr(request.state, "data_mode", settings.default_mode),
            total_count=summary["total_requests"],
        ),
        data=summary,
    )
