"""
Async SQLite database connection manager.

For DEMO MVP, we use SQLite via aiosqlite.
Production LIVE mode would use asyncpg + PostGIS.
"""

import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from app.config import settings


def _db_path() -> str:
    return settings.database_path


async def get_db():
    """FastAPI dependency — yields an async SQLite connection."""
    db = await aiosqlite.connect(_db_path())
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


async def check_db_health() -> dict:
    """Quick health probe — returns row counts for key tables."""
    try:
        async with aiosqlite.connect(_db_path()) as db:
            db.row_factory = aiosqlite.Row
            counts = {}
            for table in ("dim_regions", "dim_indicators", "fact_indicator_values", "data_snapshots"):
                cursor = await db.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                row = await cursor.fetchone()
                counts[table] = row["cnt"] if row else 0
            return {"status": "connected", "tables": counts}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
