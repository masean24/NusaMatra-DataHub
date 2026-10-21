"""
Async SQLite database connection manager.

For DEMO MVP, we use SQLite via aiosqlite.
Production LIVE mode would use asyncpg + PostGIS.
"""

import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from starlette.requests import Request
from app.config import settings


def _db_path(mode: str = "DEMO") -> str:
    if mode == "LIVE" and settings.enable_live_mode and Path(settings.live_database_path).exists():
        return settings.live_database_path
    return settings.database_path


async def get_db(request: Request = None):
    """FastAPI dependency — yields an async SQLite connection matching the resolved mode."""
    mode = getattr(request.state, "data_mode", settings.default_mode) if request else settings.default_mode
    db = await aiosqlite.connect(_db_path(mode))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Run migration scripts to initialise the database schema."""
    migration_file = Path(__file__).parent.parent / "migrations" / "001_init_schema.sql"
    async with aiosqlite.connect(_db_path()) as db:
        sql = migration_file.read_text(encoding="utf-8")
        await db.executescript(sql)
        await db.commit()


async def check_db_health(mode: str = "DEMO") -> dict:
    """Quick health probe — returns row counts for key tables."""
    try:
        async with aiosqlite.connect(_db_path(mode)) as db:
            db.row_factory = aiosqlite.Row
            counts = {}
            for table in ("dim_regions", "dim_indicators", "fact_indicator_values", "data_snapshots"):
                cursor = await db.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                row = await cursor.fetchone()
                counts[table] = row["cnt"] if row else 0
            return {"status": "connected", "tables": counts}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
