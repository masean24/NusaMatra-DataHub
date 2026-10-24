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
from app.services.snapshot_registry import resolve_snapshot


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

        # Resolve snapshot pin. ``snapshot`` is the v2.2 alias; ``snapshot_id``
        # remains supported for the v2.1 frontend contract.
        raw_snapshot_alias = request.query_params.get("snapshot")
        raw_snapshot_id = request.query_params.get("snapshot_id")
        if (
            raw_snapshot_alias
            and raw_snapshot_id
            and raw_snapshot_alias.strip() != raw_snapshot_id.strip()
        ):
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "code": "SNAPSHOT_PARAM_CONFLICT",
                    "message": "Use either 'snapshot' or 'snapshot_id', not two different values.",
                },
            )
        raw_snapshot = (raw_snapshot_alias or raw_snapshot_id or "").strip() or None

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

        snapshot_meta = await resolve_snapshot(mode, raw_snapshot)
        if raw_snapshot and snapshot_meta is None:
            other_mode = "LIVE" if mode == "DEMO" else "DEMO"
            other_snapshot = await resolve_snapshot(other_mode, raw_snapshot)
            if other_snapshot is not None:
                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "error",
                        "code": "SNAPSHOT_MODE_MISMATCH",
                        "message": (
                            f"Snapshot '{raw_snapshot}' belongs to {other_mode}, "
                            f"but mode={mode} was requested."
                        ),
                    },
                )
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "code": "SNAPSHOT_NOT_FOUND",
                    "message": (
                        f"Snapshot '{raw_snapshot}' was not found. "
                        "Use GET /api/v1/snapshots to list immutable snapshot IDs."
                    ),
                },
            )

        if snapshot_meta is not None and snapshot_meta["environment_tag"] != mode:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "code": "SNAPSHOT_MODE_MISMATCH",
                    "message": (
                        f"Snapshot '{snapshot_meta['snapshot_id']}' belongs to "
                        f"{snapshot_meta['environment_tag']}, but mode={mode} was requested."
                    ),
                },
            )

        if snapshot_meta is None and mode == "LIVE":
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "code": "LIVE_SNAPSHOT_UNAVAILABLE",
                    "message": (
                        "LIVE mode is enabled but no active immutable snapshot is available. "
                        "Run the snapshot seeder before serving LIVE data."
                    ),
                },
                headers={
                    "X-NusaMatra-Mode": "LIVE",
                    "X-Data-Fallback": "UNAVAILABLE",
                },
            )

        snapshot_id = (
            snapshot_meta["snapshot_id"]
            if snapshot_meta is not None
            else (
                settings.live_snapshot_id
                if mode == "LIVE"
                else settings.default_snapshot_id
            )
        )

        # Store in request state for downstream handlers
        request.state.data_mode = mode
        request.state.snapshot_id = snapshot_id
        request.state.snapshot_meta = snapshot_meta

        # Call the actual endpoint handler and measure execution latency
        start_t = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        # Record telemetry metric for known API endpoints only.
        # Unknown paths (scanner probes such as /.gitmodules or /runtime.js) are ignored.
        if telemetry.is_trackable_path(request.url.path):
            route = request.scope.get("route")
            telemetry.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
                mode=mode,
                route_path=getattr(route, "path", None),
            )

        # Inject standard response headers if not explicitly set by the route handler
        response.headers["X-NusaMatra-Snapshot"] = snapshot_id
        response.headers["X-NusaMatra-Mode"] = mode
        if snapshot_meta is not None:
            response.headers["X-NusaMatra-Content-SHA256"] = str(
                snapshot_meta.get("content_sha256") or ""
            )
            response.headers["X-NusaMatra-Snapshot-Immutable"] = (
                "true" if snapshot_meta.get("is_immutable") else "false"
            )
            response.headers["X-NusaMatra-Snapshot-Reproducible"] = (
                "true"
                if snapshot_meta.get("is_reproducible")
                and snapshot_meta.get("content_sha256")
                else "false"
            )
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
