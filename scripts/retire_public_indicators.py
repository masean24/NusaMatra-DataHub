#!/usr/bin/env python3
"""
Retire restricted indicators from the public catalog without mutating historical
snapshots.

The active LIVE snapshot is copied into a new staging snapshot with only public
indicators. The old snapshot and its zero-fact retired rows remain intact, so
pinned Evidence Passport links continue to resolve.

This script is idempotent: if the active snapshot already excludes every retired
indicator, it exits without publishing a new snapshot.
"""

from __future__ import annotations

import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.indicator_policy import RETIRED_PUBLIC_INDICATORS
from app.services.normalization_service import normalize_score, rank_normalized_values
from app.services.snapshot_integrity import (
    ensure_snapshot_schema,
    finalize_staging_snapshot,
    populate_snapshot_indicators,
    verify_content_digest,
)

DB_PATH = Path(
    os.environ.get("NM_LIVE_DATABASE_PATH")
    or os.environ.get("LIVE_DATABASE_PATH")
    or REPO_ROOT / "data" / "nusa_matra_live.db"
)
STAGING_ID = "__nusa_matra_live_retirement_staging__"


def _mark_retired(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for indicator_id, reason in RETIRED_PUBLIC_INDICATORS.items():
        conn.execute(
            """
            UPDATE dim_indicators
            SET is_public = 0,
                retired_at = COALESCE(retired_at, ?),
                retirement_reason = COALESCE(retirement_reason, ?)
            WHERE indicator_id = ?
            """,
            (now, reason, indicator_id),
        )
    conn.commit()


def _active_live_snapshot(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM data_snapshots
        WHERE environment_tag = 'LIVE' AND is_active_default = 1
        ORDER BY published_at DESC
        LIMIT 1
        """
    ).fetchone()


def _snapshot_has_retired(conn: sqlite3.Connection, snapshot_id: str) -> bool:
    placeholders = ",".join("?" for _ in RETIRED_PUBLIC_INDICATORS)
    row = conn.execute(
        f"""
        SELECT 1 FROM snapshot_indicators
        WHERE snapshot_id = ?
          AND indicator_id IN ({placeholders})
        LIMIT 1
        """,
        [snapshot_id, *RETIRED_PUBLIC_INDICATORS],
    ).fetchone()
    return row is not None


def _clear_staging(conn: sqlite3.Connection) -> None:
    for table in ("fact_indicator_values", "snapshot_indicators", "data_snapshots"):
        conn.execute(f"DELETE FROM {table} WHERE snapshot_id = ?", (STAGING_ID,))
    conn.commit()


def _create_staging(conn: sqlite3.Connection, source: sqlite3.Row) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO data_snapshots (
            snapshot_id, label, environment_tag, is_active_default,
            boundary_version, created_at, published_at, manifest_checksum,
            notes, content_hash_spec, is_immutable, is_reproducible,
            methodology_version, supersedes
        ) VALUES (?, ?, 'LIVE', 0, ?, ?, ?, ?, ?, 'canonical-json-v1', 0, 0, ?, ?)
        """,
        (
            STAGING_ID,
            source["label"],
            source["boundary_version"],
            now,
            now,
            source["manifest_checksum"],
            "Retirement staging snapshot; replaced by a digest-addressed immutable snapshot.",
            source["methodology_version"],
            source["snapshot_id"],
        ),
    )
    conn.commit()


def _copy_public_facts(conn: sqlite3.Connection, source_snapshot_id: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO fact_indicator_values (
            snapshot_id, region_id, indicator_id, reference_year,
            raw_value, normalized_score, national_percentile, national_rank,
            quality_flag, dataset_id, source_record_ref
        )
        SELECT ?, f.region_id, f.indicator_id, f.reference_year,
               f.raw_value, f.normalized_score, f.national_percentile,
               f.national_rank, f.quality_flag, f.dataset_id, f.source_record_ref
        FROM fact_indicator_values f
        WHERE f.snapshot_id = ?
          AND EXISTS (
              SELECT 1 FROM dim_indicators i
              WHERE i.indicator_id = f.indicator_id AND i.is_public = 1
          )
        """,
        (STAGING_ID, source_snapshot_id),
    )
    conn.commit()
    return cursor.rowcount


def _insert_derived(
    conn: sqlite3.Connection,
    snapshot_id: str,
    indicator_id: str,
    values: list[tuple[str, float]],
    polarity: str,
) -> None:
    if not values:
        return
    raw_numbers = [value for _, value in values]
    low, high = min(raw_numbers), max(raw_numbers)
    conn.execute(
        """
        UPDATE dim_indicators
        SET national_min = ?, national_max = ?, national_mean = ?, national_median = ?
        WHERE indicator_id = ?
        """,
        (
            round(low, 4),
            round(high, 4),
            round(sum(raw_numbers) / len(raw_numbers), 4),
            round(statistics.median(raw_numbers), 4),
            indicator_id,
        ),
    )
    normalized = [
        (region_id, value, normalize_score(value, low, high, polarity), "DERIVED")
        for region_id, value in values
    ]
    ranked = rank_normalized_values(normalized)
    by_region = {
        region_id: (value, score, rank, percentile)
        for region_id, value, score, rank, percentile in ranked
    }
    for region_id, value, score, _flag in normalized:
        _, _, rank, percentile = by_region[region_id]
        conn.execute(
            """
            INSERT OR REPLACE INTO fact_indicator_values (
                snapshot_id, region_id, indicator_id, reference_year,
                raw_value, normalized_score, national_percentile, national_rank,
                quality_flag, dataset_id, source_record_ref
            ) VALUES (?, ?, ?, 2026, ?, ?, ?, ?, 'DERIVED',
                      'nusa_matra_internal_audit', ?)
            """,
            (
                snapshot_id,
                region_id,
                indicator_id,
                round(value, 4),
                score,
                percentile,
                rank,
                f"Internal snapshot audit ({indicator_id})",
            ),
        )


def _recompute_internal_meta(conn: sqlite3.Connection, staging_id: str) -> None:
    """Recompute completeness/freshness against the public core framework.

    The old snapshot's facts are copied verbatim. These two derived indicators
    must be recalculated because retired indicators are no longer part of the
    public completeness denominator.
    """
    core_ids = [
        row[0]
        for row in conn.execute(
            "SELECT indicator_id FROM dim_indicators "
            "WHERE is_public = 1 AND indicator_id NOT LIKE 'meta_%'"
        )
    ]
    if not core_ids:
        return
    core_set = set(core_ids)
    region_ids = [
        row[0]
        for row in conn.execute(
            "SELECT region_id FROM dim_regions WHERE level IN ('kabupaten', 'kota')"
        )
    ]
    covered = {region_id: 0 for region_id in region_ids}
    years = {region_id: [] for region_id in region_ids}

    placeholders = ",".join("?" for _ in core_ids)
    for region_id, indicator_id, year in conn.execute(
        f"""
        SELECT region_id, indicator_id, reference_year
        FROM fact_indicator_values
        WHERE snapshot_id = ? AND indicator_id IN ({placeholders})
        """,
        [staging_id, *core_ids],
    ):
        if indicator_id in core_set and region_id in covered:
            covered[region_id] += 1
            years[region_id].append(year)

    completeness = [
        (region_id, round(count / len(core_ids) * 100.0, 4))
        for region_id, count in covered.items()
    ]
    freshness = [
        (region_id, round(2026 - (sum(values) / len(values)), 4))
        for region_id, values in years.items()
        if values
    ]

    conn.execute(
        "DELETE FROM fact_indicator_values "
        "WHERE snapshot_id = ? AND indicator_id IN "
        "('meta_indicator_completeness', 'meta_freshness_lag_years')",
        (staging_id,),
    )
    _insert_derived(
        conn, staging_id, "meta_indicator_completeness", completeness, "positive"
    )
    _insert_derived(
        conn, staging_id, "meta_freshness_lag_years", freshness, "negative"
    )
    conn.commit()


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] LIVE database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = OFF")

    ensure_snapshot_schema(conn)
    _mark_retired(conn)

    active = _active_live_snapshot(conn)
    if active is None:
        print("[ERROR] No active LIVE snapshot found.")
        conn.close()
        return 1

    old_id = active["snapshot_id"]
    if not _snapshot_has_retired(conn, old_id):
        print(f"[OK] Active snapshot {old_id} already excludes retired indicators.")
        conn.close()
        return 0

    print(f"[INFO] Publish retirement snapshot from: {old_id}")
    _clear_staging(conn)
    _create_staging(conn, active)
    copied = _copy_public_facts(conn, old_id)
    print(f"       [OK] Copied {copied} public fact rows")
    _recompute_internal_meta(conn, STAGING_ID)

    populate_snapshot_indicators(conn, STAGING_ID)
    result = finalize_staging_snapshot(
        conn,
        STAGING_ID,
        label=active["label"],
        boundary_version=active["boundary_version"],
        notes=(
            "Public catalog retirement: restricted Dapodik, student-travel-time, "
            "and real-time ICU indicators removed from this snapshot. "
            "Historical snapshots remain immutable."
        ),
        supersedes=old_id,
    )
    new_id = result["snapshot_id"]

    if not verify_content_digest(conn, new_id):
        print(f"[ERROR] Digest verification failed for {new_id}")
        conn.close()
        return 1

    new_row = conn.execute(
        "SELECT indicator_count, available_indicator_count FROM data_snapshots WHERE snapshot_id = ?",
        (new_id,),
    ).fetchone()
    print(f"[OK] New active snapshot: {new_id}")
    print(
        f"     indicators={new_row['indicator_count']} "
        f"available={new_row['available_indicator_count']} "
        f"content_sha256={result['content_sha256'][:16]}..."
    )
    print(f"[OK] Historical snapshot retained: {old_id}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
