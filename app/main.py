"""
Nusa Matra Data Hub — FastAPI Application Entry Point.

Geographic Decision-Support Backend API (WIA 2026).
Serves /api/v1 endpoints for the Nusa Matra 3D map frontend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.middleware.mode_selector import ModeSelector
from app.routers import regions, indicators, boundaries, datasets, snapshots, health


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
        "Nusa Matra Data Hub API — Menyajikan data indikator pembangunan "
        "514 Kabupaten/Kota Indonesia untuk sistem pendukung keputusan "
        "berbasis peta 3D. Mode saat ini: DEMO."
    ),
    lifespan=lifespan,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# --- Middleware ---
# CORS (permissive for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data mode selector (DEMO/LIVE) — must be added after CORS
app.add_middleware(ModeSelector)

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
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "mode": settings.default_mode,
        "docs": f"{settings.api_prefix}/docs",
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
