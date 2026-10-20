"""
Snapshot and dataset catalog service.
"""

from typing import Optional
import aiosqlite

from app.models.health import DatasetInfo, SnapshotInfo


async def list_snapshots(db: aiosqlite.Connection) -> list[SnapshotInfo]:
    """Return all available data snapshots."""

    cursor = await db.execute(
        """
        SELECT
            s.snapshot_id, s.label, s.environment_tag, s.is_active_default,
            s.boundary_version, s.created_at, s.published_at,
            s.manifest_checksum, s.notes
        FROM data_snapshots s
        ORDER BY s.created_at DESC
        """
    )
    rows = await cursor.fetchall()

    snapshots = []
    for r in rows:
        # Compute indicator completeness for this snapshot
        count_cursor = await db.execute(
            """
            SELECT
                COUNT(DISTINCT indicator_id) AS ind_count,
                (SELECT COUNT(*) FROM dim_indicators WHERE availability_status != 'UNAVAILABLE') AS total_available
            FROM fact_indicator_values
            WHERE snapshot_id = ?
            """,
            [r["snapshot_id"]],
        )
        count_row = await count_cursor.fetchone()
        total_avail = count_row["total_available"] if count_row else 0
        ind_count = count_row["ind_count"] if count_row else 0
        completeness = round((ind_count / total_avail * 100), 1) if total_avail > 0 else 0.0

        snapshots.append(
            SnapshotInfo(
                snapshot_id=r["snapshot_id"],
                label=r["label"],
                environment_tag=r["environment_tag"],
                is_active_default=bool(r["is_active_default"]),
                boundary_version=r["boundary_version"],
                created_at=r["created_at"],
                published_at=r["published_at"],
                manifest_checksum=r["manifest_checksum"],
                notes=r["notes"],
                indicator_completeness_pct=completeness,
            )
        )

    return snapshots


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
