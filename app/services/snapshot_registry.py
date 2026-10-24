"""
Snapshot resolution for request pinning.

A request either selects an exact snapshot (``snapshot`` or ``snapshot_id``)
or receives the active default for its environment. Unknown explicit snapshots
are never silently replaced by the latest data.
"""

from pathlib import Path
from typing import Any, Optional

import aiosqlite

from app.config import settings


def _db_path(mode: str) -> str:
    if mode == "LIVE":
        return settings.live_database_path
    return settings.database_path


async def resolve_snapshot(
    mode: str, requested_snapshot: Optional[str] = None
) -> Optional[dict[str, Any]]:
    path = Path(_db_path(mode))
    if not path.exists():
        return None

    async with aiosqlite.connect(str(path)) as db:
        db.row_factory = aiosqlite.Row
        if requested_snapshot:
            cursor = await db.execute(
                "SELECT * FROM data_snapshots WHERE snapshot_id = ?",
                (requested_snapshot,),
            )
        else:
            reproducible_filter = (
                "AND content_sha256 IS NOT NULL AND is_reproducible = 1"
                if mode == "LIVE"
                else ""
            )
            cursor = await db.execute(
                f"""
                SELECT * FROM data_snapshots
                WHERE environment_tag = ? AND is_active_default = 1
                {reproducible_filter}
                ORDER BY published_at DESC
                LIMIT 1
                """,
                (mode,),
            )
        row = await cursor.fetchone()
        return dict(row) if row else None


def snapshot_meta_fields(request) -> dict[str, Any]:
    meta = getattr(request.state, "snapshot_meta", None) or {}
    return {
        "content_sha256": meta.get("content_sha256"),
        "snapshot_immutable": bool(meta.get("is_immutable", 0)),
        "snapshot_reproducible": bool(meta.get("is_reproducible", 0))
        and bool(meta.get("content_sha256")),
        "methodology_version": meta.get("methodology_version"),
    }
