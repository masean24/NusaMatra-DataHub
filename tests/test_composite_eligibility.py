"""Eligibility, per-region renormalization, tie, and rank-scope tests."""

import aiosqlite
import pytest

from app.models.indicators import CompositeQueryRequest
from app.services.composite_service import apportion_weights, compute_composite_scores

SNAPSHOT = "test-snapshot"
INDICATORS = {"i1": 3000, "i2": 3000, "i3": 2000, "i4": 2000}


async def _make_db(tmp_path, facts, regions):
    path = tmp_path / "composite.db"
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.executescript(
        """
        CREATE TABLE dim_regions (
            region_id TEXT PRIMARY KEY,
            parent_region_id TEXT,
            level TEXT,
            name TEXT
        );
        CREATE TABLE dim_indicators (indicator_id TEXT PRIMARY KEY);
        CREATE TABLE fact_indicator_values (
            snapshot_id TEXT,
            region_id TEXT,
            indicator_id TEXT,
            normalized_score REAL,
            quality_flag TEXT
        );
        """
    )
    for region_id, parent_id, name in regions:
        await db.execute(
            "INSERT INTO dim_regions VALUES (?, ?, 'kabupaten', ?)",
            (region_id, parent_id, name),
        )
    for indicator_id in INDICATORS:
        await db.execute("INSERT INTO dim_indicators VALUES (?)", (indicator_id,))
    for region_id, indicator_id, score in facts:
        await db.execute(
            "INSERT INTO fact_indicator_values VALUES (?, ?, ?, ?, 'VERIFIED')",
            (SNAPSHOT, region_id, indicator_id, score),
        )
    await db.commit()
    return db


def test_apportion_weights_always_sums_to_10000():
    assert sum(apportion_weights({"a": 3000, "b": 3000, "c": 2000}).values()) == 10000
    assert sum(apportion_weights({"a": 1, "b": 1, "c": 1}).values()) == 10000
    assert apportion_weights({}) == {}


@pytest.mark.asyncio
async def test_partial_region_is_reweighted_not_zeroed(tmp_path):
    regions = [
        ("R1", "11", "Region Full"),
        ("R2", "11", "Region Partial"),
        ("R3", "12", "Region Mostly Empty"),
    ]
    facts = [
        ("R1", "i1", 100.0), ("R1", "i2", 100.0), ("R1", "i3", 100.0), ("R1", "i4", 100.0),
        ("R2", "i1", 90.0), ("R2", "i2", 80.0), ("R2", "i3", 70.0),
        ("R3", "i1", 95.0),
    ]
    db = await _make_db(tmp_path, facts, regions)
    try:
        result = await compute_composite_scores(
            db, CompositeQueryRequest(weights=INDICATORS), snapshot_id=SNAPSHOT
        )
    finally:
        await db.close()

    assert result.score_direction == "higher_is_need"
    assert result.total_eligible_national == 2
    assert result.total_regions == 2
    assert result.total_excluded == 1

    by_id = {region.region_id: region for region in result.regions}
    assert by_id["R2"].coverage_pct == 80.0
    assert by_id["R2"].missing_indicators == ["i4"]
    assert sum(by_id["R2"].effective_weights_region.values()) == 10000
    # 90*0.375 + 80*0.375 + 70*0.25 = 81.25, not 81.25*0.8 = 65.0
    assert by_id["R2"].composite_score == 81.25
    assert by_id["R1"].composite_score == 100.0

    assert [item.region_id for item in result.insufficient_data] == ["R3"]
    assert result.insufficient_data[0].coverage_pct == 30.0


@pytest.mark.asyncio
async def test_filter_keeps_national_rank(tmp_path):
    regions = [
        ("R1", "11", "Region Full"),
        ("R2", "12", "Region Partial"),
        ("R3", "12", "Region Mostly Empty"),
    ]
    facts = [
        ("R1", "i1", 100.0), ("R1", "i2", 100.0), ("R1", "i3", 100.0), ("R1", "i4", 100.0),
        ("R2", "i1", 90.0), ("R2", "i2", 80.0), ("R2", "i3", 70.0),
        ("R3", "i1", 95.0),
    ]
    db = await _make_db(tmp_path, facts, regions)
    try:
        result = await compute_composite_scores(
            db,
            CompositeQueryRequest(weights=INDICATORS, filter_province_id="12"),
            snapshot_id=SNAPSHOT,
        )
    finally:
        await db.close()

    assert result.total_regions == 1
    assert result.total_eligible_national == 2
    assert result.regions[0].region_id == "R2"
    assert result.regions[0].rank == 1
    assert result.regions[0].national_rank == 2
    assert [item.region_id for item in result.insufficient_data] == ["R3"]


@pytest.mark.asyncio
async def test_equal_scores_share_rank(tmp_path):
    regions = [("R1", "11", "A"), ("R2", "11", "B")]
    facts = [
        ("R1", "i1", 80.0), ("R1", "i2", 80.0), ("R1", "i3", 80.0), ("R1", "i4", 80.0),
        ("R2", "i1", 80.0), ("R2", "i2", 80.0), ("R2", "i3", 80.0), ("R2", "i4", 80.0),
    ]
    db = await _make_db(tmp_path, facts, regions)
    try:
        result = await compute_composite_scores(
            db, CompositeQueryRequest(weights=INDICATORS), snapshot_id=SNAPSHOT
        )
    finally:
        await db.close()

    assert [region.rank for region in result.regions] == [1, 1]
    assert [region.national_rank for region in result.regions] == [1, 1]


@pytest.mark.asyncio
async def test_region_without_any_observation_is_reported(tmp_path):
    regions = [("R1", "11", "A"), ("R2", "11", "B")]
    facts = [
        ("R1", "i1", 80.0), ("R1", "i2", 80.0), ("R1", "i3", 80.0), ("R1", "i4", 80.0),
    ]
    db = await _make_db(tmp_path, facts, regions)
    try:
        result = await compute_composite_scores(
            db, CompositeQueryRequest(weights=INDICATORS), snapshot_id=SNAPSHOT
        )
    finally:
        await db.close()

    assert result.total_excluded == 1
    assert result.insufficient_data[0].region_id == "R2"
    assert result.insufficient_data[0].coverage_pct == 0.0


def test_documented_math_is_68_34():
    components = {"a": 72.1, "b": 61.5, "c": 70.3}
    weights = {"a": 4375, "b": 3125, "c": 2500}
    score = sum(components[key] * weights[key] / 10000 for key in components)
    assert round(score, 2) == 68.34
