"""Normalization and composite regression tests for the v2.2 integrity fix."""

import sqlite3
import statistics
from pathlib import Path

import aiosqlite
import pytest

from app.services.indicator_service import get_indicator_values
from app.services.normalization_service import normalize_score, rank_normalized_values

LIVE_DB = Path(__file__).parent.parent / "data" / "nusa_matra_live.db"

live_only = pytest.mark.skipif(
    not LIVE_DB.exists(), reason="LIVE database not generated"
)


def test_positive_polarity_lower_raw_is_higher_need():
    assert normalize_score(10, 10, 110, "positive") == 100.0
    assert normalize_score(60, 10, 110, "positive") == 50.0
    assert normalize_score(110, 10, 110, "positive") == 0.0


def test_negative_polarity_higher_raw_is_higher_need():
    assert normalize_score(10, 10, 110, "negative") == 0.0
    assert normalize_score(60, 10, 110, "negative") == 50.0
    assert normalize_score(110, 10, 110, "negative") == 100.0


def test_degenerate_distribution_is_neutral():
    assert normalize_score(42, 42, 42, "positive") == 50.0


def test_rank_normalization_competition_ranking():
    ranked = rank_normalized_values(
        [
            ("a", 10, 80.0, "VERIFIED"),
            ("b", 20, 80.0, "VERIFIED"),
            ("c", 30, 70.0, "VERIFIED"),
        ]
    )
    assert [row[3] for row in ranked] == [1, 1, 3]
    assert [row[4] for row in ranked] == [100.0, 100.0, 0.0]


def _active_snapshot(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag = 'LIVE' AND is_active_default = 1 "
        "ORDER BY published_at DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    return row[0]


@live_only
def test_live_scores_are_monotonic_for_both_directions():
    connection = sqlite3.connect(LIVE_DB)
    snapshot = _active_snapshot(connection)
    for indicator_id, polarity in connection.execute(
        """SELECT indicator_id, polarity FROM snapshot_indicators
           WHERE snapshot_id=? AND observation_count > 10""",
        (snapshot,),
    ):
        rows = connection.execute(
            """SELECT raw_value, normalized_score FROM fact_indicator_values
               WHERE snapshot_id=? AND indicator_id=? AND raw_value IS NOT NULL
               AND normalized_score IS NOT NULL""",
            (snapshot, indicator_id),
        ).fetchall()
        correlation = statistics.correlation(
            [row[0] for row in rows], [row[1] for row in rows]
        )
        expected_sign = 1 if polarity == "negative" else -1
        assert correlation * expected_sign > 0.99, (
            f"{indicator_id} violates {polarity} direction: corr={correlation}"
        )
    connection.close()


@live_only
def test_live_snapshot_contains_all_quality_flag_classes():
    connection = sqlite3.connect(LIVE_DB)
    snapshot = _active_snapshot(connection)
    flags = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT quality_flag FROM fact_indicator_values WHERE snapshot_id=?",
            (snapshot,),
        )
    }
    assert {"VERIFIED", "DERIVED", "IMPUTED_PROVINCE"}.issubset(flags)
    connection.close()


@live_only
def test_lanny_jaya_composite_recalculated_after_correction():
    connection = sqlite3.connect(LIVE_DB)
    snapshot = _active_snapshot(connection)
    weights = {
        "soc_poverty_rate": 3000,
        "hlt_stunting_prevalence": 3000,
        "inf_safe_water_pct": 2000,
        "inf_safe_sanitation_pct": 2000,
    }
    placeholders = ",".join("?" for _ in weights)
    rows = connection.execute(
        f"""SELECT region_id, indicator_id, normalized_score
            FROM fact_indicator_values
            WHERE snapshot_id=? AND indicator_id IN ({placeholders})""",
        [snapshot, *weights],
    ).fetchall()
    connection.close()

    components: dict[str, dict[str, float]] = {}
    for region_id, indicator_id, score in rows:
        components.setdefault(region_id, {})[indicator_id] = score

    scored = []
    for region_id, values in components.items():
        present_weight = sum(weights[i] for i in values)
        if len(values) < 2 or present_weight < 7000:
            continue
        score = sum(
            values[indicator_id] * weight / present_weight
            for indicator_id, weight in weights.items()
            if indicator_id in values
        )
        scored.append((region_id, round(score, 2)))
    scored.sort(key=lambda item: (-item[1], item[0]))
    rank = next(index for index, item in enumerate(scored, 1) if item[0] == "9507")
    score = next(item[1] for item in scored if item[0] == "9507")
    assert score == 74.34
    assert rank == 5


@live_only
@pytest.mark.asyncio
async def test_live_indicator_value_exposes_observation_provenance():
    from app.services.snapshot_integrity import ensure_snapshot_schema_async

    db = await aiosqlite.connect(LIVE_DB)
    db.row_factory = aiosqlite.Row
    await ensure_snapshot_schema_async(db)
    row = await (
        await db.execute(
            "SELECT snapshot_id FROM data_snapshots WHERE is_active_default = 1 LIMIT 1"
        )
    ).fetchone()
    result = await get_indicator_values(db, "inf_safe_water_pct", row["snapshot_id"])
    await db.close()

    value = result.values_by_region["9507"]
    assert value.raw == 32.89
    assert value.norm == 78.89
    assert value.flag == "IMPUTED_PROVINCE"
    assert value.dataset_id == "bps_provincial_sdgs_2025"
    assert "PAPUA PEGUNUNGAN" in value.source_record_ref
