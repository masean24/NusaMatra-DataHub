"""
Region data service — queries dim_regions and fact_indicator_values.
"""

from typing import Optional
import aiosqlite

from app.models.regions import (
    AnchorPoint,
    CompositeScores,
    IndicatorProvenance,
    RegionCodes,
    RegionDetail,
    RegionIndicatorValue,
    RegionSummary,
)


async def list_regions(
    db: aiosqlite.Connection,
    *,
    level: str = "kabupaten_kota",
    parent_id: Optional[str] = None,
    q: Optional[str] = None,
    snapshot_id: str = "2026.10.0-wia-demo",
) -> list[RegionSummary]:
    """List regions with optional filters."""

    conditions = []
    params: list = []

    if level == "kabupaten_kota":
        conditions.append("r.level IN ('kabupaten', 'kota')")
    elif level == "provinsi":
        conditions.append("r.level = 'provinsi'")
    # "all" → no level filter

    if parent_id:
        conditions.append("r.parent_region_id = ?")
        params.append(parent_id)

    if q:
        # Escape SQL LIKE wildcards to prevent unintended wildcard matches
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            "(r.name LIKE ? ESCAPE '\\' OR r.region_id LIKE ? ESCAPE '\\' OR r.bps_code LIKE ? ESCAPE '\\')"
        )
        like = f"%{escaped_q}%"
        params.extend([like, like, like])

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            r.region_id, r.parent_region_id, r.level, r.name, r.short_name,
            r.kemendagri_code, r.bps_code, r.kemendikdasmen_code,
            r.island_group, r.area_km2,
            r.label_lat, r.label_lng,
            r.bbox_min_lng, r.bbox_min_lat, r.bbox_max_lng, r.bbox_max_lat,
            p.name AS province_name
        FROM dim_regions r
        LEFT JOIN dim_regions p ON r.parent_region_id = p.region_id
        {where}
        ORDER BY r.region_id
    """

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    return [_row_to_summary(row) for row in rows]


async def get_region_detail(
    db: aiosqlite.Connection,
    region_id: str,
    snapshot_id: str = "2026.10.0-wia-demo",
) -> Optional[RegionDetail]:
    """Get full region profile with indicator values."""

    # Fetch region
    cursor = await db.execute(
        """
        SELECT
            r.region_id, r.parent_region_id, r.level, r.name, r.short_name,
            r.kemendagri_code, r.bps_code, r.kemendikdasmen_code,
            r.island_group, r.area_km2,
            r.label_lat, r.label_lng,
            r.bbox_min_lng, r.bbox_min_lat, r.bbox_max_lng, r.bbox_max_lat,
            p.name AS province_name
        FROM dim_regions r
        LEFT JOIN dim_regions p ON r.parent_region_id = p.region_id
        WHERE r.region_id = ?
        """,
        [region_id],
    )
    row = await cursor.fetchone()
    if not row:
        return None

    region = _row_to_summary(row)

    # Fetch indicators for this region
    cursor = await db.execute(
        """
        SELECT
            f.indicator_id, f.raw_value, f.normalized_score,
            f.national_percentile, f.national_rank, f.reference_year,
            f.quality_flag, f.dataset_id,
            COALESCE(si.indicator_name, i.indicator_name) AS indicator_name,
            COALESCE(si.category, i.category) AS category,
            COALESCE(si.unit, i.unit) AS unit,
            COALESCE(si.polarity, i.polarity) AS polarity,
            d.agency_code, d.official_portal_url
        FROM fact_indicator_values f
        JOIN dim_indicators i ON f.indicator_id = i.indicator_id
        LEFT JOIN snapshot_indicators si
            ON si.indicator_id = f.indicator_id AND si.snapshot_id = f.snapshot_id
        LEFT JOIN dim_datasets d ON f.dataset_id = d.dataset_id
        WHERE f.region_id = ? AND f.snapshot_id = ?
        ORDER BY category, f.indicator_id
        """,
        [region_id, snapshot_id],
    )
    ind_rows = await cursor.fetchall()

    indicators = []
    category_scores: dict[str, list[float]] = {}

    for ir in ind_rows:
        ns = ir["normalized_score"]
        cat = ir["category"]
        if ns is not None:
            category_scores.setdefault(cat, []).append(ns)

        indicators.append(
            RegionIndicatorValue(
                indicator_id=ir["indicator_id"],
                indicator_name=ir["indicator_name"],
                category=cat,
                raw_value=ir["raw_value"],
                unit=ir["unit"],
                polarity=ir["polarity"],
                normalized_score=ns,
                national_percentile=ir["national_percentile"],
                national_rank=ir["national_rank"],
                reference_year=ir["reference_year"],
                quality_flag=ir["quality_flag"],
                provenance=IndicatorProvenance(
                    dataset_id=ir["dataset_id"],
                    agency_code=ir["agency_code"] or "UNKNOWN",
                    official_url=ir["official_portal_url"],
                ),
            )
        )

    # Compute composite scores as mean of normalized scores per category
    def _cat_mean(cat: str) -> Optional[float]:
        vals = category_scores.get(cat, [])
        return round(sum(vals) / len(vals), 1) if vals else None

    all_scores = [s for vals in category_scores.values() for s in vals]
    overall = round(sum(all_scores) / len(all_scores), 1) if all_scores else None

    composite = CompositeScores(
        overall_priority_index=overall,
        disaster_risk=_cat_mean("disaster_risk"),
        socioeconomic=_cat_mean("socioeconomic"),
        education_access=_cat_mean("education_access"),
        healthcare_access=_cat_mean("healthcare_access"),
        infrastructure=_cat_mean("infrastructure"),
        data_reliability=_cat_mean("data_reliability"),
    )

    return RegionDetail(region=region, composite_scores=composite, indicators=indicators)


def _row_to_summary(row) -> RegionSummary:
    """Convert a database row to a RegionSummary model."""
    return RegionSummary(
        region_id=row["region_id"],
        parent_region_id=row["parent_region_id"],
        province_name=row["province_name"] if "province_name" in row.keys() else None,
        level=row["level"],
        name=row["name"],
        short_name=row["short_name"],
        codes=RegionCodes(
            kemendagri=row["kemendagri_code"],
            bps=row["bps_code"],
            kemendikdasmen=row["kemendikdasmen_code"],
        ),
        island_group=row["island_group"],
        area_km2=row["area_km2"],
        anchor_point=AnchorPoint(lng=row["label_lng"], lat=row["label_lat"]),
        bbox=[
            row["bbox_min_lng"] or 0,
            row["bbox_min_lat"] or 0,
            row["bbox_max_lng"] or 0,
            row["bbox_max_lat"] or 0,
        ],
    )
