"""
Snapshot and dataset catalog service.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from app.models.health import DatasetInfo, SnapshotInfo


def _iso_timestamp(value: Optional[str]) -> Optional[str]:
    """Normalize legacy SQLite timestamps to timezone-aware ISO-8601."""
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _parse_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return fallback
    if isinstance(fallback, list) and not isinstance(parsed, list):
        return fallback
    return parsed


async def _snapshot_counts(db: aiosqlite.Connection, snapshot_id: str) -> dict[str, Any]:
    total_indicators = (
        await (await db.execute("SELECT COUNT(*) FROM dim_indicators")).fetchone()
    )[0]
    available_indicators = (
        await (
            await db.execute(
                "SELECT COUNT(DISTINCT indicator_id) FROM fact_indicator_values "
                "WHERE snapshot_id = ? AND normalized_score IS NOT NULL",
                (snapshot_id,),
            )
        ).fetchone()
    )[0]
    observation_count = (
        await (
            await db.execute(
                "SELECT COUNT(*) FROM fact_indicator_values WHERE snapshot_id = ?",
                (snapshot_id,),
            )
        ).fetchone()
    )[0]
    region_count = (
        await (
            await db.execute(
                "SELECT COUNT(DISTINCT region_id) FROM fact_indicator_values "
                "WHERE snapshot_id = ?",
                (snapshot_id,),
            )
        ).fetchone()
    )[0]
    total_regions = (
        await (
            await db.execute(
                "SELECT COUNT(*) FROM dim_regions WHERE level IN ('kabupaten', 'kota')"
            )
        ).fetchone()
    )[0]
    dataset_count = (
        await (await db.execute("SELECT COUNT(*) FROM dim_datasets")).fetchone()
    )[0]

    available_catalog_count = (
        await (
            await db.execute(
                "SELECT COUNT(*) FROM snapshot_indicators "
                "WHERE snapshot_id = ? AND availability_status != 'UNAVAILABLE'",
                (snapshot_id,),
            )
        ).fetchone()
    )[0]
    if not available_catalog_count:
        available_catalog_count = (
            await (
                await db.execute(
                    "SELECT COUNT(*) FROM dim_indicators "
                    "WHERE availability_status != 'UNAVAILABLE'"
                )
            ).fetchone()
        )[0]

    completeness = round(available_indicators / total_indicators * 100, 1) if total_indicators else 0.0
    data_pct = (
        round(available_indicators / available_catalog_count * 100, 1)
        if available_catalog_count
        else 0.0
    )
    region_pct = round(region_count / total_regions * 100, 1) if total_regions else 0.0
    return {
        "total_indicators": total_indicators,
        "available_indicators": available_indicators,
        "available_catalog_count": available_catalog_count,
        "observation_count": observation_count,
        "region_count": region_count,
        "total_regions": total_regions,
        "dataset_count": dataset_count,
        "indicator_completeness_pct": completeness,
        "available_indicator_data_pct": data_pct,
        "region_coverage_pct": region_pct,
    }


def _row_value(row: aiosqlite.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


async def _to_snapshot_info(
    db: aiosqlite.Connection, row: aiosqlite.Row
) -> SnapshotInfo:
    counts = await _snapshot_counts(db, row["snapshot_id"])
    content_sha256 = _row_value(row, "content_sha256")

    # Immutable snapshots store their counts at publication time. Prefer those
    # values so later catalog changes cannot rewrite historical metadata.
    stored_indicator_count = _row_value(row, "indicator_count")
    stored_available_count = _row_value(row, "available_indicator_count")
    stored_observation_count = _row_value(row, "observation_count")
    stored_region_count = _row_value(row, "region_count")
    stored_dataset_count = _row_value(row, "dataset_count")

    indicator_count = (
        stored_indicator_count
        if stored_indicator_count is not None
        else counts["total_indicators"]
    )
    available_count = (
        stored_available_count
        if stored_available_count is not None
        else counts["available_indicators"]
    )
    observation_count = (
        stored_observation_count
        if stored_observation_count is not None
        else counts["observation_count"]
    )
    region_count = (
        stored_region_count
        if stored_region_count is not None
        else counts["region_count"]
    )
    dataset_count = (
        stored_dataset_count
        if stored_dataset_count is not None
        else counts["dataset_count"]
    )
    completeness = (
        round(available_count / indicator_count * 100, 1)
        if indicator_count
        else 0.0
    )
    region_pct = (
        round(region_count / counts["total_regions"] * 100, 1)
        if counts["total_regions"]
        else 0.0
    )

    return SnapshotInfo(
        snapshot_id=row["snapshot_id"],
        label=row["label"],
        environment_tag=row["environment_tag"],
        is_active_default=bool(row["is_active_default"]),
        boundary_version=row["boundary_version"],
        created_at=_iso_timestamp(row["created_at"]) or "",
        published_at=_iso_timestamp(row["published_at"]),
        manifest_checksum=row["manifest_checksum"],
        notes=row["notes"],
        indicator_completeness_pct=completeness,
        content_sha256=content_sha256,
        metadata_checksum=_row_value(row, "metadata_checksum") or row["manifest_checksum"],
        content_hash_spec=_row_value(row, "content_hash_spec"),
        is_immutable=bool(_row_value(row, "is_immutable", 0)),
        is_reproducible=bool(_row_value(row, "is_reproducible", 0)) and bool(content_sha256),
        methodology_version=_row_value(row, "methodology_version"),
        reference_periods=_parse_json(_row_value(row, "reference_periods"), []),
        source_manifest=_parse_json(_row_value(row, "source_manifest"), None),
        supersedes=_row_value(row, "supersedes"),
        observation_count=observation_count,
        indicator_count=indicator_count,
        available_indicator_count=available_count,
        region_count=region_count,
        dataset_count=dataset_count,
        available_indicator_data_pct=counts["available_indicator_data_pct"],
        region_coverage_pct=region_pct,
        immutability_note=_row_value(row, "immutability_note"),
    )


async def list_snapshots(db: aiosqlite.Connection) -> list[SnapshotInfo]:
    """Return all available data snapshots with explicit coverage metadata."""
    cursor = await db.execute("SELECT * FROM data_snapshots ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [await _to_snapshot_info(db, row) for row in rows]


async def get_snapshot(
    db: aiosqlite.Connection, snapshot_id: str
) -> Optional[SnapshotInfo]:
    cursor = await db.execute(
        "SELECT * FROM data_snapshots WHERE snapshot_id = ?", (snapshot_id,)
    )
    row = await cursor.fetchone()
    return await _to_snapshot_info(db, row) if row else None


async def list_datasets(db: aiosqlite.Connection) -> list[DatasetInfo]:
    """Return all registered datasets."""
    cursor = await db.execute(
        """
        SELECT
            dataset_id, agency_code, agency_name, dataset_title,
            official_portal_url, api_or_download_url, access_method,
            license_name, update_frequency, last_ingested_at, raw_sha256
        FROM dim_datasets
        ORDER BY agency_code, dataset_id
        """
    )
    rows = await cursor.fetchall()

    return [
        DatasetInfo(
            dataset_id=r["dataset_id"],
            agency_code=r["agency_code"],
            agency_name=r["agency_name"],
            dataset_title=r["dataset_title"],
            official_portal_url=r["official_portal_url"],
            api_or_download_url=r["api_or_download_url"],
            access_method=r["access_method"],
            license_name=r["license_name"],
            update_frequency=r["update_frequency"],
            last_ingested_at=r["last_ingested_at"],
            raw_sha256=r["raw_sha256"],
        )
        for r in rows
    ]
