"""
Nusa Matra Data Hub — FastAPI Application Entry Point.

Geographic Decision-Support Backend API (WIA 2026).
Serves /api/v1 endpoints for the Nusa Matra 3D map frontend.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.middleware.mode_selector import ModeSelector
from app.routers import regions, indicators, boundaries, datasets, snapshots, health, earthquakes, stats
from app.routers.stats import get_stats_html
from app.services.telemetry_service import telemetry

STATIC_DIR = Path(__file__).parent / "static"


def custom_generate_unique_id(route: APIRoute) -> str:
    """Use the endpoint function name as the OpenAPI operation ID."""
    return route.endpoint.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Ensure database schema exists on startup
    await init_db()
    await telemetry.start()
    try:
        yield
    finally:
        await telemetry.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Nusa Matra Data Hub API — Geographic Decision-Support Backend API (WIA 2026).\n\n"
        "Menyajikan data indikator pembangunan 514 Kabupaten/Kota Indonesia "
        "untuk sistem pendukung keputusan berbasis peta 3D. "
        f"Mode default: {settings.default_mode}."
    ),
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=f"{settings.api_prefix}/openapi.json" if settings.enable_docs else None,
)

# --- Static files & Favicon ---
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve custom favicon for the browser."""
    ico_path = STATIC_DIR / "favicon.ico"
    if ico_path.exists():
        return FileResponse(ico_path)
    return FileResponse(STATIC_DIR / "favicon.png")


@app.get("/favicon.png", include_in_schema=False)
async def favicon_png():
    """Serve custom favicon PNG."""
    return FileResponse(STATIC_DIR / "favicon.png")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon():
    """Serve Apple Touch icon."""
    return FileResponse(STATIC_DIR / "apple-touch-icon.png")


# --- Documentation routes (conditioned on ENABLE_DOCS) ---
if settings.enable_docs:
    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_alias():
        """Alias for /api/v1/openapi.json for compatibility."""
        return app.openapi()

    @app.get("/docs", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/docs", include_in_schema=False)
    @app.get("/scalar", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/scalar", include_in_schema=False)
    async def scalar_api_reference():
        """
        Ultra-modern interactive API reference powered by Scalar.
        Features 3-column split view, deepSpace dark theme, live playground, and multi-language code snippets.
        """
        spec = app.openapi()
        spec_json = json.dumps(spec)
        scalar_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{app.title} — API Reference</title>
    <link rel="icon" type="image/png" href="/static/favicon.png" />
    <style>
      html, body {{
        height: 100%;
        margin: 0;
        padding: 0;
        background-color: #0b0f19;
      }}
      #app {{
        height: 100%;
      }}
    </style>
  </head>
  <body>
    <div id="app"></div>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
    <script>
      Scalar.createApiReference('#app', {{
        spec: {{
          content: {spec_json},
        }},
        theme: 'deepSpace',
        darkMode: true,
        forceDarkModeState: 'dark',
        showSidebar: true,
        layout: 'modern',
        searchHotKey: 'k',
        defaultHttpClient: {{
          targetKey: 'javascript',
          clientKey: 'fetch'
        }},
        favicon: '/static/favicon.png'
      }});
    </script>
  </body>
</html>"""
        return HTMLResponse(scalar_html)

    @app.get("/redoc", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/redoc", include_in_schema=False)
    async def custom_redoc_html():
        """ReDoc formal schema view."""
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_favicon_url="/static/favicon.png",
        )

# --- Middleware ---
# In Starlette, middleware added LAST executes FIRST (outermost wrapper).
# ModeSelector is registered first (inner), and CORSMiddleware is registered
# last (outermost) so that even short-circuited error responses (e.g. 503 LIVE
# fail-closed) receive full CORS headers (Access-Control-Allow-Origin, etc.).
app.add_middleware(ModeSelector)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "X-Data-Mode",
        "X-NusaMatra-Mode",
        "X-NusaMatra-Snapshot",
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "*",
    ],
    expose_headers=[
        "X-NusaMatra-Mode",
        "X-NusaMatra-Snapshot",
        "X-NusaMatra-Content-SHA256",
        "X-NusaMatra-Snapshot-Immutable",
        "X-NusaMatra-Snapshot-Reproducible",
        "X-Data-Fallback",
        "Content-Length",
    ],
)

# --- Routers ---
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(health.router, include_in_schema=False)
app.include_router(regions.router, prefix=settings.api_prefix)
app.include_router(indicators.router, prefix=settings.api_prefix)
app.include_router(boundaries.router, prefix=settings.api_prefix)
app.include_router(datasets.router, prefix=settings.api_prefix)
app.include_router(snapshots.router, prefix=settings.api_prefix)
app.include_router(earthquakes.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)


@app.get("/stats", response_class=HTMLResponse, include_in_schema=False)
@app.get(f"{settings.api_prefix}/stats/ui", response_class=HTMLResponse, include_in_schema=False)
async def stats_ui():
    """Visual real-time interactive telemetry & usage statistics dashboard."""
    return HTMLResponse(content=get_stats_html())


@app.get("/", tags=["Root"])
async def root(request: Request):
    """Root endpoint — API info and links (or visual dashboard for browsers)."""
    accept = request.headers.get("accept", "")
    # If opened by a human in a web browser, serve the interactive visual dashboard
    if "text/html" in accept and "application/json" not in accept:
        return HTMLResponse(content=get_stats_html())

    res = {
        "service": settings.app_name,
        "version": settings.app_version,
        "mode": settings.default_mode,
        "health": f"{settings.api_prefix}/health",
        "stats": f"{settings.api_prefix}/stats",
        "stats_dashboard": "/stats",
        "endpoints": {
            "regions": f"{settings.api_prefix}/regions",
            "indicators": f"{settings.api_prefix}/indicators",
            "indicators_coverage": f"{settings.api_prefix}/indicators/coverage",
            "boundaries_kab": f"{settings.api_prefix}/boundaries/kabupaten",
            "boundaries_prov": f"{settings.api_prefix}/boundaries/provinsi",
            "datasets": f"{settings.api_prefix}/datasets",
            "snapshots": f"{settings.api_prefix}/snapshots",
            "earthquakes_latest": f"{settings.api_prefix}/earthquakes/latest",
            "earthquakes_recent": f"{settings.api_prefix}/earthquakes/recent",
            "earthquakes_felt": f"{settings.api_prefix}/earthquakes/felt",
            "earthquakes_geojson": f"{settings.api_prefix}/earthquakes/geojson",
            "earthquakes_summary": f"{settings.api_prefix}/earthquakes/summary",
            "stats": f"{settings.api_prefix}/stats",
        },
        "notice": (
            "DEMO and LIVE modes available. "
            "DEMO data is illustrative (DEMO_EXAMPLE). "
            "LIVE data is sourced from verified official government datasets (BPS, BNPB, Kemenkes, Kemendikdasmen, BMKG). "
            "Earthquake endpoints are fail-closed when upstream BMKG is unavailable."
        ),
    }
    if settings.enable_docs:
        res["docs"] = f"{settings.api_prefix}/docs"
        res["redoc"] = f"{settings.api_prefix}/redoc"
        res["openapi"] = app.openapi_url
    return res


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
    )
