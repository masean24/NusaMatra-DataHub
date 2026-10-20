"""
Composite score calculation service.
Supports weighted aggregation with integer basis points (Blocker #4).
"""

from typing import Optional
import aiosqlite

from app.models.indicators import (
    CompositeQueryRequest,
    CompositeQueryResult,
    CompositeRegionScore,
)


async def compute_composite_scores(
    db: aiosqlite.Connection,
    request: CompositeQueryRequest,
    snapshot_id: str = "2026.10.0-wia-demo",
) -> CompositeQueryResult:
    """
    Calculate weighted composite scores for all regions.

    Weights are in basis points (1/10000). Sum must equal 10000.
    Each indicator's normalized_score (0-100) is multiplied by its
    weight/10000, then summed to produce a composite score (0-100).
    """

    weights = request.weights
    indicator_ids = list(weights.keys())

    if not indicator_ids:
        return CompositeQueryResult(
            total_regions=0,
            weights_basis_points=weights,
            regions=[],
        )

    # Validate weights sum to 10000
    weight_sum = sum(weights.values())
    if weight_sum != 10000:
        raise ValueError(
            f"Weights must sum to 10000 basis points, got {weight_sum}"
        )

    # Build query to fetch normalized scores for requested indicators
    placeholders = ",".join("?" for _ in indicator_ids)

    province_filter = ""
    params: list = [snapshot_id] + indicator_ids
    if request.filter_province_id:
        province_filter = "AND r.parent_region_id = ?"
        params.append(request.filter_province_id)

    query = f"""
        SELECT
            f.region_id,
            r.name AS region_name,
            f.indicator_id,
            f.normalized_score
        FROM fact_indicator_values f
        JOIN dim_regions r ON f.region_id = r.region_id
        WHERE f.snapshot_id = ?
          AND f.indicator_id IN ({placeholders})
          AND r.level IN ('kabupaten', 'kota')
          {province_filter}
        ORDER BY f.region_id, f.indicator_id
    """

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # Aggregate scores per region
    region_data: dict[str, dict] = {}
    for row in rows:
        rid = row["region_id"]
        if rid not in region_data:
            region_data[rid] = {
                "region_name": row["region_name"],
                "component_scores": {},
                "composite": 0.0,
            }
        norm = row["normalized_score"]
        iid = row["indicator_id"]
        region_data[rid]["component_scores"][iid] = norm
        if norm is not None:
            region_data[rid]["composite"] += norm * (weights[iid] / 10000.0)

    # Sort by composite score descending and assign ranks
    sorted_regions = sorted(
        region_data.items(),
        key=lambda x: x[1]["composite"],
        reverse=True,
    )

    results = []
    for rank, (rid, data) in enumerate(sorted_regions, start=1):
        results.append(
            CompositeRegionScore(
                region_id=rid,
                region_name=data["region_name"],
                composite_score=round(data["composite"], 2),
                rank=rank,
                component_scores=data["component_scores"],
            )
        )

    return CompositeQueryResult(
        total_regions=len(results),
        weights_basis_points=weights,
        regions=results,
    )
