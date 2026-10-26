"""
Immutable snapshot identity and canonical content hashing.

The digest is computed from the canonical warehouse state, not from file
timestamps or the snapshot label. It therefore changes when any included
observation, indicator metadata, region catalog entry, dataset provenance row,
or scoring configuration changes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from app.config import settings

CONTENT_HASH_SPEC = "canonical-json-v1"
SNAPSHOT_ID_PREFIX = "2026.10.0-live"
STAGING_SNAPSHOT_ID = "__nusa_matra_live_staging__"

SNAPSHOT_COLUMNS: dict[str, str] = {
    "content_sha256": "TEXT",
    "metadata_checksum": "TEXT",
    "content_hash_spec": "TEXT NOT NULL DEFAULT 'canonical-json-v1'",
    "is_immutable": "INTEGER NOT NULL DEFAULT 0",
    "is_reproducible": "INTEGER NOT NULL DEFAULT 1",
    "methodology_version": "TEXT",
    "reference_periods": "TEXT",
    "source_manifest": "TEXT",
    "supersedes": "TEXT",
    "observation_count": "INTEGER",
    "indicator_count": "INTEGER",
    "available_indicator_count": "INTEGER",
    "region_count": "INTEGER",
    "dataset_count": "INTEGER",
    "immutability_note": "TEXT",
}

INDICATOR_COLUMNS: dict[str, str] = {
    "is_public": "INTEGER NOT NULL DEFAULT 1",
    "retired_at": "TEXT",
    "retirement_reason": "TEXT",
}

SNAPSHOT_INDICATORS_DDL = """
CREATE TABLE IF NOT EXISTS snapshot_indicators (
    snapshot_id TEXT NOT NULL REFERENCES data_snapshots(snapshot_id),
    indicator_id TEXT NOT NULL REFERENCES dim_indicators(indicator_id),
    indicator_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,
    polarity TEXT NOT NULL,
    availability_status TEXT NOT NULL,
    primary_dataset_id TEXT,
    derivation_formula TEXT,
    description TEXT NOT NULL,
    national_min REAL,
    national_max REAL,
    national_mean REAL,
    national_median REAL,
    observation_count INTEGER NOT NULL DEFAULT 0,
    reference_years TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, indicator_id)
);
"""


def _sync_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_indicator_schema(conn: sqlite3.Connection) -> None:
    """Add public-visibility columns to an existing indicator catalog."""
    columns = _sync_columns(conn, "dim_indicators")
    for name, sql_type in INDICATOR_COLUMNS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE dim_indicators ADD COLUMN {name} {sql_type}")


async def ensure_indicator_schema_async(db) -> None:
    cursor = await db.execute("PRAGMA table_info(dim_indicators)")
    columns = {row[1] for row in await cursor.fetchall()}
    for name, sql_type in INDICATOR_COLUMNS.items():
        if name not in columns:
            await db.execute(f"ALTER TABLE dim_indicators ADD COLUMN {name} {sql_type}")


def ensure_snapshot_schema(conn: sqlite3.Connection) -> None:
    """Add immutable-snapshot and indicator-visibility columns to an existing DB."""
    columns = _sync_columns(conn, "data_snapshots")
    for name, sql_type in SNAPSHOT_COLUMNS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE data_snapshots ADD COLUMN {name} {sql_type}")
    ensure_indicator_schema(conn)
    conn.execute(SNAPSHOT_INDICATORS_DDL)
    conn.commit()


async def ensure_snapshot_schema_async(db) -> None:
    """Async equivalent used by application startup migrations."""
    cursor = await db.execute("PRAGMA table_info(data_snapshots)")
    columns = {row[1] for row in await cursor.fetchall()}
    for name, sql_type in SNAPSHOT_COLUMNS.items():
        if name not in columns:
            await db.execute(
                f"ALTER TABLE data_snapshots ADD COLUMN {name} {sql_type}"
            )
    await ensure_indicator_schema_async(db)
    await db.execute(SNAPSHOT_INDICATORS_DDL)
    await db.commit()


def _canonical_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    number = round(float(value), 6)
    return 0.0 if number == 0 else number


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _scoring_config() -> dict[str, Any]:
    # Imported lazily to avoid a module cycle during seeder startup.
    from app.services.composite_service import (
        COMPOSITE_PRESETS,
        SCORE_DIRECTION,
        TOTAL_BASIS_POINTS,
    )

    return {
        "score_direction": SCORE_DIRECTION,
        "total_basis_points": TOTAL_BASIS_POINTS,
        "min_coverage_pct": settings.composite_min_coverage_pct,
        "min_components": settings.composite_min_components,
        "presets": [
            {"preset_id": preset.preset_id, "weights": preset.weights}
            for preset in COMPOSITE_PRESETS
        ],
    }


def _snapshot_header(conn: sqlite3.Connection, snapshot_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT environment_tag, boundary_version, methodology_version "
        "FROM data_snapshots WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Snapshot '{snapshot_id}' does not exist")
    return {
        "environment_tag": row[0],
        "boundary_version": row[1],
        "methodology_version": row[2],
    }


def _indicator_rows(conn: sqlite3.Connection, snapshot_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT indicator_id, indicator_name, category, unit, polarity,
               availability_status, primary_dataset_id, derivation_formula,
               description, national_min, national_max, national_mean,
               national_median, observation_count, reference_years
        FROM snapshot_indicators
        WHERE snapshot_id = ?
        ORDER BY indicator_id
        """,
        (snapshot_id,),
    ).fetchall()
    return [
        {
            "indicator_id": r[0],
            "indicator_name": r[1],
            "category": r[2],
            "unit": r[3],
            "polarity": r[4],
            "availability_status": r[5],
            "primary_dataset_id": r[6],
            "derivation_formula": r[7],
            "description": r[8],
            "national_min": _canonical_number(r[9]),
            "national_max": _canonical_number(r[10]),
            "national_mean": _canonical_number(r[11]),
            "national_median": _canonical_number(r[12]),
            "observation_count": r[13],
            "reference_years": json.loads(r[14] or "[]"),
        }
        for r in rows
    ]


def _region_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT region_id, parent_region_id, level, name, short_name,
               kemendagri_code, bps_code, kemendikdasmen_code, island_group,
               area_km2, label_lat, label_lng, bbox_min_lng, bbox_min_lat,
               bbox_max_lng, bbox_max_lat, boundary_version
        FROM dim_regions
        ORDER BY region_id
        """
    ).fetchall()
    return [
        {
            "region_id": r[0],
            "parent_region_id": r[1],
            "level": r[2],
            "name": r[3],
            "short_name": r[4],
            "kemendagri_code": r[5],
            "bps_code": r[6],
            "kemendikdasmen_code": r[7],
            "island_group": r[8],
            "area_km2": _canonical_number(r[9]),
            "label_lat": _canonical_number(r[10]),
            "label_lng": _canonical_number(r[11]),
            "bbox_min_lng": _canonical_number(r[12]),
            "bbox_min_lat": _canonical_number(r[13]),
            "bbox_max_lng": _canonical_number(r[14]),
            "bbox_max_lat": _canonical_number(r[15]),
            "boundary_version": r[16],
        }
        for r in rows
    ]


def _dataset_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT dataset_id, agency_code, agency_name, dataset_title,
               official_portal_url, api_or_download_url, access_method,
               license_name, update_frequency, raw_sha256
        FROM dim_datasets
        ORDER BY dataset_id
        """
    ).fetchall()
    return [
        {
            "dataset_id": r[0],
            "agency_code": r[1],
            "agency_name": r[2],
            "dataset_title": r[3],
            "official_portal_url": r[4],
            "api_or_download_url": r[5],
            "access_method": r[6],
            "license_name": r[7],
            "update_frequency": r[8],
            "raw_sha256": r[9],
        }
        for r in rows
    ]


def _observation_rows(conn: sqlite3.Connection, snapshot_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT region_id, indicator_id, reference_year, raw_value,
               normalized_score, national_percentile, national_rank,
               quality_flag, dataset_id, source_record_ref
        FROM fact_indicator_values
        WHERE snapshot_id = ?
        ORDER BY indicator_id, region_id, reference_year
        """,
        (snapshot_id,),
    ).fetchall()
    return [
        {
            "region_id": r[0],
            "indicator_id": r[1],
            "reference_year": r[2],
            "raw_value": _canonical_number(r[3]),
            "normalized_score": _canonical_number(r[4]),
            "national_percentile": _canonical_number(r[5]),
            "national_rank": r[6],
            "quality_flag": r[7],
            "dataset_id": r[8],
            "source_record_ref": r[9],
        }
        for r in rows
    ]


def _payload(conn: sqlite3.Connection, snapshot_id: str) -> dict[str, Any]:
    header = _snapshot_header(conn, snapshot_id)
    indicators = _indicator_rows(conn, snapshot_id)
    observations = _observation_rows(conn, snapshot_id)
    weeks = sorted({row["reference_year"] for row in observations})
    return {
        "spec": CONTENT_HASH_SPEC,
        "environment_tag": header["environment_tag"],
        "boundary_version": header["boundary_version"],
        "methodology_version": header["methodology_version"],
        "scoring": _scoring_config(),
        "datasets": _dataset_rows(conn),
        "indicators": indicators,
        "regions": _region_rows(conn),
        "reference_periods": weeks,
        "observations": observations,
    }


def compute_content_digest(conn: sqlite3.Connection, snapshot_id: str) -> str:
    return hashlib.sha256(_json_bytes(_payload(conn, snapshot_id))).hexdigest()


def compute_metadata_checksum(conn: sqlite3.Connection, snapshot_id: str) -> str:
    payload = _payload(conn, snapshot_id)
    payload.pop("observations", None)
    payload.pop("reference_periods", None)
    derived_fields = {
        "national_min",
        "national_max",
        "national_mean",
        "national_median",
        "observation_count",
        "reference_years",
    }
    payload["indicators"] = [
        {key: value for key, value in row.items() if key not in derived_fields}
        for row in payload["indicators"]
    ]
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def snapshot_id_from_digest(digest: str) -> str:
    return f"{SNAPSHOT_ID_PREFIX}-{digest[:16]}"


def _stats_for_indicator(
    conn: sqlite3.Connection, snapshot_id: str, indicator_id: str
) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT raw_value, reference_year FROM fact_indicator_values "
        "WHERE snapshot_id = ? AND indicator_id = ? AND raw_value IS NOT NULL",
        (snapshot_id, indicator_id),
    ).fetchall()
    values = sorted(float(r[0]) for r in rows)
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "years": [],
        }
    middle = len(values) // 2
    median = (
        values[middle]
        if len(values) % 2
        else (values[middle - 1] + values[middle]) / 2
    )
    return {
        "count": len(values),
        "min": round(values[0], 6),
        "max": round(values[-1], 6),
        "mean": round(sum(values) / len(values), 6),
        "median": round(median, 6),
        "years": sorted({int(r[1]) for r in rows}),
    }


def populate_snapshot_indicators(
    conn: sqlite3.Connection, snapshot_id: str
) -> None:
    """Freeze indicator metadata and national distribution per snapshot."""
    computed_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        SELECT indicator_id, indicator_name, category, unit, polarity,
               availability_status, primary_dataset_id, derivation_formula,
               description
        FROM dim_indicators
        WHERE is_public = 1
        ORDER BY indicator_id
        """
    )
    rows = cursor.fetchall()
    conn.execute(
        "DELETE FROM snapshot_indicators WHERE snapshot_id = ?", (snapshot_id,)
    )
    for row in rows:
        indicator_id = row[0]
        stats = _stats_for_indicator(conn, snapshot_id, indicator_id)
        if stats["count"] > 0:
            status = row[5] if row[5] != "UNAVAILABLE" else "DIRECT"
        else:
            status = "UNAVAILABLE"
        conn.execute(
            """
            INSERT INTO snapshot_indicators (
                snapshot_id, indicator_id, indicator_name, category, unit,
                polarity, availability_status, primary_dataset_id,
                derivation_formula, description, national_min, national_max,
                national_mean, national_median, observation_count,
                reference_years, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                indicator_id,
                row[1],
                row[2],
                row[3],
                row[4],
                status,
                row[6],
                row[7],
                row[8],
                stats["min"],
                stats["max"],
                stats["mean"],
                stats["median"],
                stats["count"],
                json.dumps(stats["years"]),
                computed_at,
            ),
        )
    conn.commit()


def mark_legacy_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE data_snapshots
        SET is_immutable = 0,
            is_reproducible = 0,
            immutability_note = COALESCE(
                immutability_note,
                'Legacy snapshot ID was reused across publications; content cannot be reconstructed.'
            )
        WHERE environment_tag = 'LIVE'
          AND content_sha256 IS NULL
          AND snapshot_id NOT LIKE '2026.10.0-live-%'
        """
    )
    conn.commit()


def finalize_staging_snapshot(
    conn: sqlite3.Connection,
    staging_id: str,
    *,
    label: str,
    boundary_version: str,
    notes: str,
    supersedes: Optional[str],
) -> dict[str, Any]:
    """Freeze staging facts into a digest-addressed immutable snapshot."""
    populate_snapshot_indicators(conn, staging_id)
    content_sha256 = compute_content_digest(conn, staging_id)
    metadata_checksum = compute_metadata_checksum(conn, staging_id)
    final_id = snapshot_id_from_digest(content_sha256)

    existing = conn.execute(
        "SELECT content_sha256 FROM data_snapshots WHERE snapshot_id = ?",
        (final_id,),
    ).fetchone()
    if existing is not None:
        # Same canonical content: keep the existing immutable snapshot and
        # make it the active default again.
        conn.execute(
            "DELETE FROM fact_indicator_values WHERE snapshot_id = ?", (staging_id,)
        )
        conn.execute(
            "DELETE FROM snapshot_indicators WHERE snapshot_id = ?", (staging_id,)
        )
        conn.execute(
            "DELETE FROM data_snapshots WHERE snapshot_id = ?", (staging_id,)
        )
        conn.execute(
            "UPDATE data_snapshots SET is_active_default = 0 WHERE environment_tag = 'LIVE'"
        )
        conn.execute(
            "UPDATE data_snapshots SET is_active_default = 1 WHERE snapshot_id = ?",
            (final_id,),
        )
        conn.commit()
        return {
            "snapshot_id": final_id,
            "content_sha256": existing[0],
            "metadata_checksum": metadata_checksum,
            "reused": True,
        }

    now = datetime.now(timezone.utc).isoformat()
    periods = [
        int(r[0])
        for r in conn.execute(
            "SELECT DISTINCT reference_year FROM fact_indicator_values "
            "WHERE snapshot_id = ? ORDER BY reference_year",
            (staging_id,),
        )
    ]
    counts = conn.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT region_id), COUNT(DISTINCT indicator_id)
        FROM fact_indicator_values WHERE snapshot_id = ?
        """,
        (staging_id,),
    ).fetchone()
    available_count = conn.execute(
        "SELECT COUNT(*) FROM snapshot_indicators "
        "WHERE snapshot_id = ? AND observation_count > 0",
        (staging_id,),
    ).fetchone()[0]
    dataset_count = conn.execute("SELECT COUNT(*) FROM dim_datasets").fetchone()[0]
    source_manifest = json.dumps(_dataset_rows(conn), sort_keys=True, ensure_ascii=False)

    conn.execute(
        "UPDATE data_snapshots SET is_active_default = 0 WHERE environment_tag = 'LIVE'"
    )
    conn.execute(
        """
        INSERT INTO data_snapshots (
            snapshot_id, label, environment_tag, is_active_default,
            boundary_version, created_at, published_at, manifest_checksum,
            notes, content_sha256, metadata_checksum, content_hash_spec,
            is_immutable, is_reproducible, methodology_version,
            reference_periods, source_manifest, supersedes, observation_count,
            indicator_count, available_indicator_count, region_count,
            dataset_count, immutability_note
        ) VALUES (?, ?, 'LIVE', 1, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            final_id,
            label,
            boundary_version,
            now,
            now,
            metadata_checksum,
            notes,
            content_sha256,
            metadata_checksum,
            CONTENT_HASH_SPEC,
            "v2.2-minmax-full-range",
            json.dumps(periods),
            source_manifest,
            supersedes,
            counts[0],
            conn.execute(
                "SELECT COUNT(*) FROM dim_indicators WHERE is_public = 1"
            ).fetchone()[0],
            available_count,
            counts[1],
            dataset_count,
            "Immutable LIVE snapshot. content_sha256 covers canonical observations and scoring metadata.",
        ),
    )
    conn.execute(
        "UPDATE fact_indicator_values SET snapshot_id = ? WHERE snapshot_id = ?",
        (final_id, staging_id),
    )
    conn.execute(
        "UPDATE snapshot_indicators SET snapshot_id = ? WHERE snapshot_id = ?",
        (final_id, staging_id),
    )
    conn.execute(
        "DELETE FROM data_snapshots WHERE snapshot_id = ?", (staging_id,)
    )
    conn.commit()
    return {
        "snapshot_id": final_id,
        "content_sha256": content_sha256,
        "metadata_checksum": metadata_checksum,
        "reused": False,
    }


def verify_content_digest(conn: sqlite3.Connection, snapshot_id: str) -> bool:
    row = conn.execute(
        "SELECT content_sha256 FROM data_snapshots WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if row is None or not row[0]:
        return False
    return compute_content_digest(conn, snapshot_id) == row[0]
