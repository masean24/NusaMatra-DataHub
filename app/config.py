"""
Application configuration via environment variables.
Uses pydantic-settings for typed config with .env file support.
"""

from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Nusa Matra Data Hub configuration."""

    # Application metadata
    app_name: str = "Nusa Matra Data Hub"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database (SQLite for DEMO MVP, migrate to PostGIS for LIVE)
    database_path: str = str(Path(__file__).parent.parent / "data" / "nusa_matra_demo.db")

    # Default mode and snapshot
    default_mode: str = "DEMO"
    default_snapshot_id: str = "2026.10.0-wia-demo"
    boundary_version: str = "BIG-Kepmendagri-300.2.2-2430-2025"

    # LIVE mode controls
    enable_live_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_LIVE_MODE", "NM_ENABLE_LIVE_MODE", "enable_live_mode"),
        description="Enable verified LIVE mode against official datasets",
    )
    live_database_path: str = Field(
        default=str(Path(__file__).parent.parent / "data" / "nusa_matra_live.db"),
        validation_alias=AliasChoices("LIVE_DATABASE_PATH", "NM_LIVE_DATABASE_PATH", "live_database_path"),
        description="Path to verified official LIVE SQLite database",
    )
    live_snapshot_id: str = "2026.10.0-official-live"

    # API settings & documentation
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://api.orangkeren.me",
        "*",
    ]
    enable_docs: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_DOCS", "NM_ENABLE_DOCS", "enable_docs"),
        description="Toggle API documentation (/docs, /redoc, /scalar, and openapi.json)",
    )
    bps_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("BPS_API_KEY", "NM_BPS_API_KEY", "bps_api_key"),
        description="Official BPS WebAPI Developer Key",
    )

    # Composite ranking eligibility policy
    composite_min_coverage_pct: int = Field(
        default=70,
        validation_alias=AliasChoices(
            "COMPOSITE_MIN_COVERAGE_PCT",
            "NM_COMPOSITE_MIN_COVERAGE_PCT",
            "composite_min_coverage_pct",
        ),
        description="Minimum percentage of requested weight observed for a region to be ranked",
    )
    composite_min_components: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "COMPOSITE_MIN_COMPONENTS",
            "NM_COMPOSITE_MIN_COMPONENTS",
            "composite_min_components",
        ),
        description="Minimum number of contributing indicators for a region to be ranked",
    )

    # Telemetry persistence (point to a Coolify persistent volume in production)
    telemetry_db_path: str = Field(
        default=str(Path(__file__).parent.parent / "data" / "telemetry.db"),
        validation_alias=AliasChoices(
            "TELEMETRY_DB_PATH",
            "NM_TELEMETRY_DB_PATH",
            "telemetry_db_path",
        ),
        description="SQLite path for persisted telemetry counters",
    )
    telemetry_flush_interval_seconds: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "TELEMETRY_FLUSH_INTERVAL_SECONDS",
            "NM_TELEMETRY_FLUSH_INTERVAL_SECONDS",
            "telemetry_flush_interval_seconds",
        ),
        description="Seconds between telemetry snapshot flushes",
    )
    telemetry_persistence_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "TELEMETRY_PERSISTENCE_ENABLED",
            "NM_TELEMETRY_PERSISTENCE_ENABLED",
            "telemetry_persistence_enabled",
        ),
        description="Persist telemetry counters across process restarts",
    )

    model_config = {"env_prefix": "NM_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
