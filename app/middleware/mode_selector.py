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
import time
from app.config import settings
from app.services.telemetry_service import telemetry


class ModeSelector(BaseHTTPMiddleware):
    """Resolve DEMO/LIVE mode and attach to request state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass validation for docs and static assets
        path = request.url.path
        if (
            path in ("/docs", "/redoc", "/scalar", "/openapi.json", "/favicon.ico", "/favicon.png", "/apple-touch-icon.png", "/stats")
            or path.startswith(f"{settings.api_prefix}/docs")
            or path.startswith(f"{settings.api_prefix}/scalar")
            or path.startswith(f"{settings.api_prefix}/redoc")
            or path.startswith(f"{settings.api_prefix}/stats/ui")
            or path.startswith("/static")
        ):
            return await call_next(request)

        # Validate mode parameter if provided
        raw_mode = request.query_params.get("mode") or request.headers.get("x-data-mode")
        if raw_mode is not None and raw_mode.strip() != "":
            mode_candidate = raw_mode.strip().upper()
            if mode_candidate not in ("DEMO", "LIVE"):
                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "error",
                        "code": "INVALID_MODE",
                        "message": f"Invalid mode '{raw_mode}'. Mode must be either 'demo' or 'live'.",
                    },
                )
            mode = mode_candidate
        else:
            mode = settings.default_mode

        # Validate snapshot_id if explicitly requested
        raw_snapshot = request.query_params.get("snapshot_id")
        if raw_snapshot is not None and raw_snapshot.strip() != "":
            valid_snapshots = (settings.default_snapshot_id, settings.live_snapshot_id)
            if raw_snapshot not in valid_snapshots:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "code": "SNAPSHOT_NOT_FOUND",
                        "message": (
                            f"Snapshot '{raw_snapshot}' not found. "
                            "Check GET /api/v1/snapshots for active snapshots."
                        ),
                    },
                )
            # Check environment compatibility
            if mode == "LIVE" and raw_snapshot != settings.live_snapshot_id:
                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "error",
                        "code": "SNAPSHOT_MODE_MISMATCH",
                        "message": (
                            f"Snapshot '{raw_snapshot}' belongs to DEMO environment, "
                            "but mode=LIVE was requested."
                        ),
                    },
                )
            elif mode == "DEMO" and raw_snapshot != settings.default_snapshot_id:
                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "error",
                        "code": "SNAPSHOT_MODE_MISMATCH",
                        "message": (
                            f"Snapshot '{raw_snapshot}' belongs to LIVE environment, "
                            "but mode=DEMO was requested."
                        ),
                    },
                )
            snapshot_id = raw_snapshot
        else:
            snapshot_id = settings.live_snapshot_id if mode == "LIVE" else settings.default_snapshot_id

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

        # Store in request state for downstream handlers
        request.state.data_mode = mode
        request.state.snapshot_id = snapshot_id

        # Call the actual endpoint handler and measure execution latency
        start_t = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        # Record telemetry metric
        telemetry.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            mode=mode,
        )

        # Inject standard response headers if not explicitly set by the route handler
        response.headers["X-NusaMatra-Snapshot"] = snapshot_id
        response.headers["X-NusaMatra-Mode"] = mode
        if "X-Data-Fallback" not in response.headers:
            response.headers["X-Data-Fallback"] = "NONE"

        # Apply specific cache policies: short/no-cache for earthquakes, long immutable for boundaries, standard for datasets
        if "Cache-Control" not in response.headers:
            if request.url.path.startswith(f"{settings.api_prefix}/earthquakes"):
                response.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
            elif request.url.path.startswith(f"{settings.api_prefix}/boundaries"):
                response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"

        return response
