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

    model_config = {"env_prefix": "NM_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
