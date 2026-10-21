"""
Nusa Matra Data Hub — FastAPI Application Entry Point.

Geographic Decision-Support Backend API (WIA 2026).
Serves /api/v1 endpoints for the Nusa Matra 3D map frontend.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.middleware.mode_selector import ModeSelector
from app.routers import regions, indicators, boundaries, datasets, snapshots, health

STATIC_DIR = Path(__file__).parent / "static"


def custom_generate_unique_id(route: APIRoute) -> str:
    """Use the endpoint function name as the OpenAPI operation ID."""
    return route.endpoint.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Ensure database schema exists on startup
    await init_db()
    yield


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


# --- Documentation routes (conditioned on ENABLE_DOCS) ---
if settings.enable_docs:
    @app.get("/docs", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Swagger UI with custom Nusa Matra favicon."""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            swagger_favicon_url="/static/favicon.png",
        )

    @app.get("/redoc", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/redoc", include_in_schema=False)
    async def custom_redoc_html():
        """ReDoc with custom Nusa Matra favicon."""
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
        "X-Data-Fallback",
        "Content-Length",
    ],
)

# --- Routers ---
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(regions.router, prefix=settings.api_prefix)
app.include_router(indicators.router, prefix=settings.api_prefix)
app.include_router(boundaries.router, prefix=settings.api_prefix)
app.include_router(datasets.router, prefix=settings.api_prefix)
app.include_router(snapshots.router, prefix=settings.api_prefix)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — API info and links."""
    res = {
        "service": settings.app_name,
        "version": settings.app_version,
        "mode": settings.default_mode,
        "health": f"{settings.api_prefix}/health",
        "endpoints": {
            "regions": f"{settings.api_prefix}/regions",
            "indicators": f"{settings.api_prefix}/indicators",
            "boundaries_kab": f"{settings.api_prefix}/boundaries/kabupaten",
            "boundaries_prov": f"{settings.api_prefix}/boundaries/provinsi",
            "datasets": f"{settings.api_prefix}/datasets",
            "snapshots": f"{settings.api_prefix}/snapshots",
        },
        "notice": (
            "DEMO mode only. All data is illustrative (DEMO_EXAMPLE). "
            "Not sourced from verified LIVE measurements."
        ),
    }
    if settings.enable_docs:
        res["docs"] = f"{settings.api_prefix}/docs"
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
