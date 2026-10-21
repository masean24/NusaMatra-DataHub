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
from fastapi.responses import FileResponse, HTMLResponse
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
    SWAGGER_UI_PARAMETERS = {
        "defaultModelsExpandDepth": 1,
        "defaultModelExpandDepth": 1,
        "docExpansion": "list",
        "filter": True,  # Enables instant search filter on endpoints
        "tryItOutEnabled": True,  # Automatically activates "Try it out" for quick testing
        "syntaxHighlight.theme": "monokai",
        "displayRequestDuration": True,  # Displays latency in milliseconds
        "persistAuthorization": True,
    }

    SWAGGER_DARK_CSS = """
    <style>
      :root {
        --nm-bg-main: #0b0f19;
        --nm-bg-card: #111827;
        --nm-border: #1f2937;
        --nm-text: #f9fafb;
      }
      body {
        background-color: var(--nm-bg-main) !important;
        color: var(--nm-text) !important;
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
      }
      .swagger-ui {
        color: var(--nm-text) !important;
      }
      /* Custom Branded Topbar */
      .nm-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        border-bottom: 1px solid #334155;
        padding: 14px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 14px rgba(0,0,0,0.35);
      }
      .nm-header .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        text-decoration: none;
      }
      .nm-header .brand img {
        width: 30px;
        height: 30px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      }
      .nm-header .brand-title {
        font-size: 17px;
        font-weight: 700;
        color: #ffffff;
      }
      .nm-header .brand-tag {
        font-size: 11px;
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.4);
        padding: 2px 8px;
        border-radius: 9999px;
        font-weight: 600;
      }
      .nm-header .nav-links {
        display: flex;
        gap: 10px;
        align-items: center;
      }
      .nm-header .nav-link {
        font-size: 13px;
        color: #94a3b8;
        text-decoration: none;
        padding: 6px 12px;
        border-radius: 6px;
        transition: all 0.2s;
        border: 1px solid transparent;
      }
      .nm-header .nav-link:hover {
        color: #ffffff;
        background: rgba(255, 255, 255, 0.05);
        border-color: #334155;
      }
      .nm-header .nav-link.active {
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.12);
        border-color: rgba(56, 189, 248, 0.3);
        font-weight: 600;
      }
      /* Hide default topbar */
      .swagger-ui .topbar { display: none !important; }
      /* Text & Typography */
      .swagger-ui .info { margin: 24px 0 !important; }
      .swagger-ui .info .title { color: #f1f5f9 !important; font-weight: 800 !important; }
      .swagger-ui .info p, .swagger-ui .info li { color: #94a3b8 !important; }
      /* Search Filter Bar */
      .swagger-ui .filter-container { padding: 14px 0 22px 0 !important; }
      .swagger-ui .filter input {
        background: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25) !important;
      }
      .swagger-ui .filter input:focus {
        border-color: #38bdf8 !important;
        outline: none !important;
      }
      /* Operation Blocks */
      .swagger-ui .opblock {
        background: #111827 !important;
        border-radius: 10px !important;
        border: 1px solid #1f2937 !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2) !important;
        margin: 0 0 16px !important;
      }
      .swagger-ui .opblock.opblock-get { border-color: rgba(16, 185, 129, 0.4) !important; background: rgba(16, 185, 129, 0.04) !important; }
      .swagger-ui .opblock.opblock-post { border-color: rgba(59, 130, 246, 0.4) !important; background: rgba(59, 130, 246, 0.04) !important; }
      .swagger-ui .opblock .opblock-summary-method {
        border-radius: 6px !important;
        font-weight: 700 !important;
        padding: 6px 12px !important;
      }
      .swagger-ui .opblock .opblock-summary-path { color: #f3f4f6 !important; font-weight: 600 !important; }
      .swagger-ui .opblock .opblock-summary-description { color: #9ca3af !important; }
      .swagger-ui .opblock-body { background: #0f172a !important; }
      .swagger-ui table thead tr th, .swagger-ui table thead tr td {
        color: #cbd5e1 !important;
        border-bottom: 1px solid #334155 !important;
      }
      .swagger-ui .parameter__name { color: #f8fafc !important; font-weight: 600 !important; }
      .swagger-ui .parameter__type { color: #38bdf8 !important; }
      .swagger-ui input[type=text], .swagger-ui textarea, .swagger-ui select {
        background: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
      }
      .swagger-ui .responses-inner { background: #0f172a !important; }
      .swagger-ui .response-col_status { color: #f8fafc !important; }
      .swagger-ui .btn.execute {
        background: #2563eb !important;
        border-color: #2563eb !important;
        color: #ffffff !important;
        border-radius: 6px !important;
      }
      .swagger-ui .btn.execute:hover { background: #1d4ed8 !important; }
      .swagger-ui section.models {
        background: #111827 !important;
        border: 1px solid #1f2937 !important;
        border-radius: 10px !important;
      }
      .swagger-ui section.models h4 { color: #f3f4f6 !important; }
      .swagger-ui .model-box { background: #0f172a !important; }
    </style>
    """

    SWAGGER_HEADER_HTML = """
    <div class="nm-header">
      <a href="/" class="brand">
        <img src="/static/favicon.png" alt="Nusa Matra Logo">
        <div>
          <span class="brand-title">Nusa Matra Data Hub</span>
          <span class="brand-tag">v0.1.0 • DEMO</span>
        </div>
      </a>
      <div class="nav-links">
        <a href="/api/v1/docs" class="nav-link active">⚡ Swagger UI</a>
        <a href="/api/v1/elements" class="nav-link">🎨 Stoplight Elements</a>
        <a href="/api/v1/redoc" class="nav-link">📖 ReDoc</a>
        <a href="/api/v1/openapi.json" class="nav-link" target="_blank">📄 OpenAPI JSON</a>
      </div>
    </div>
    """

    @app.get("/docs", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Swagger UI with modern dark makeover, search filter, and quick navigation."""
        base_resp = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI (Modern Dark)",
            swagger_favicon_url="/static/favicon.png",
            swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        )
        html = base_resp.body.decode("utf-8")
        # Inject custom styling and top header
        html = html.replace("</head>", f"{SWAGGER_DARK_CSS}</head>")
        html = html.replace("<body>", f"<body>{SWAGGER_HEADER_HTML}")
        return HTMLResponse(html)

    @app.get("/elements", include_in_schema=False)
    @app.get(f"{settings.api_prefix}/elements", include_in_schema=False)
    async def custom_stoplight_elements_html():
        """Stoplight Elements 3-column modern interactive API documentation."""
        elements_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>{app.title} - Stoplight Elements</title>
    <link rel="icon" type="image/png" href="/static/favicon.png">
    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
    <style>
      html, body {{
        height: 100%;
        margin: 0;
        padding: 0;
        background-color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }}
      .nav-bar {{
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        border-bottom: 1px solid #334155;
        padding: 10px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        height: 38px;
        box-sizing: content-box;
      }}
      .nav-bar .brand {{
        display: flex;
        align-items: center;
        gap: 10px;
        color: #ffffff;
        font-weight: 700;
        font-size: 15px;
        text-decoration: none;
      }}
      .nav-bar .brand img {{
        width: 26px;
        height: 26px;
        border-radius: 6px;
      }}
      .nav-bar .links {{
        display: flex;
        gap: 10px;
      }}
      .nav-bar .links a {{
        color: #94a3b8;
        text-decoration: none;
        font-size: 13px;
        padding: 5px 10px;
        border-radius: 6px;
        transition: all 0.2s;
        border: 1px solid transparent;
      }}
      .nav-bar .links a:hover {{
        color: #ffffff;
        background: rgba(255,255,255,0.06);
        border-color: #334155;
      }}
      .nav-bar .links a.active {{
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.12);
        border-color: rgba(56, 189, 248, 0.3);
        font-weight: 600;
      }}
      .elements-container {{
        height: calc(100vh - 59px);
        width: 100%;
      }}
      elements-api {{
        height: 100%;
        width: 100%;
        display: block;
      }}
    </style>
  </head>
  <body>
    <div class="nav-bar">
      <a href="/" class="brand">
        <img src="/static/favicon.png" alt="Logo">
        <span>{app.title}</span>
      </a>
      <div class="links">
        <a href="/api/v1/docs">⚡ Swagger UI</a>
        <a href="/api/v1/elements" class="active">🎨 Stoplight Elements</a>
        <a href="/api/v1/redoc">📖 ReDoc</a>
        <a href="/api/v1/openapi.json" target="_blank">📄 OpenAPI JSON</a>
      </div>
    </div>
    <div class="elements-container">
      <elements-api
        apiDescriptionUrl="{app.openapi_url}"
        router="hash"
        layout="sidebar"
        logo="/static/favicon.png"
        tryItCredentialsPolicy="include"
      />
    </div>
  </body>
</html>"""
        return HTMLResponse(elements_html)

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
        res["docs_alternatives"] = {
            "swagger_dark": f"{settings.api_prefix}/docs",
            "stoplight_elements": f"{settings.api_prefix}/elements",
            "redoc": f"{settings.api_prefix}/redoc",
            "openapi_json": app.openapi_url,
        }
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
