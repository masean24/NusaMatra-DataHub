"""
Mode selector middleware.

Extracts the data mode (DEMO or LIVE) from:
  1. Query parameter ?mode=demo|live
  2. HTTP header X-Data-Mode: DEMO|LIVE
  3. Falls back to settings.default_mode

Stores the resolved mode in request.state.data_mode and
request.state.snapshot_id.

Blocker #1: LIVE mode must NEVER fall back to DEMO data.
If LIVE is requested but unavailable, we return 503.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from pathlib import Path
from app.config import settings


class ModeSelector(BaseHTTPMiddleware):
    """Resolve DEMO/LIVE mode and attach to request state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Determine mode from query param, then header, then default
        mode = (
            request.query_params.get("mode", "").upper()
            or request.headers.get("x-data-mode", "").upper()
            or settings.default_mode
        )

        if mode not in ("DEMO", "LIVE"):
            mode = settings.default_mode

        # BLOCKER #1: LIVE must fail closed — unless explicitly enabled with verified database
        if mode == "LIVE":
            if not settings.enable_live_mode or not Path(settings.live_database_path).exists():
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "code": "LIVE_UNAVAILABLE",
                        "message": (
                            "LIVE mode is not yet available. "
                            "LIVE data sources have not been verified and connected. "
                            "Use mode=demo for the demonstration dataset."
                        ),
                    },
                    headers={
                        "X-NusaMatra-Mode": "LIVE",
                        "X-Data-Fallback": "UNAVAILABLE",
                    },
                )
            snapshot_id = (
                request.query_params.get("snapshot_id")
                or settings.live_snapshot_id
            )
        else:
            # Resolve snapshot
            snapshot_id = (
                request.query_params.get("snapshot_id")
                or settings.default_snapshot_id
            )

        # Store in request state for downstream handlers
        request.state.data_mode = mode
        request.state.snapshot_id = snapshot_id

        # Call the actual endpoint handler
        response = await call_next(request)

        # Inject standard response headers if not explicitly set by the route handler
        response.headers["X-NusaMatra-Snapshot"] = snapshot_id
        response.headers["X-NusaMatra-Mode"] = mode
        if "X-Data-Fallback" not in response.headers:
            response.headers["X-Data-Fallback"] = "NONE"

        # Apply short/no-cache for dynamic real-time feeds (e.g. earthquakes), long-cache for static datasets
        if "Cache-Control" not in response.headers:
            if request.url.path.startswith(f"{settings.api_prefix}/earthquakes"):
                response.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"

        return response
