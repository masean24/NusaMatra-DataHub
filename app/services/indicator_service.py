"""
Indicator data service — queries dim_indicators and fact_indicator_values.
"""

from typing import Optional
import aiosqlite

from app.models.indicators import (
    IndicatorCatalogItem,
    IndicatorMeta,
    IndicatorProvenance,
    IndicatorStats,
    IndicatorValuesData,
    RegionIndicatorValue,
)


async def list_indicators(
    db: aiosqlite.Connection,
    snapshot_id: str = "2026.10.0-wia-demo",
) -> list[IndicatorCatalogItem]:
    """Return the full indicator catalog grouped by category."""

    cursor = await db.execute(
        """
        SELECT
            i.indicator_id,
            COALESCE(si.indicator_name, i.indicator_name) AS indicator_name,
            COALESCE(si.category, i.category) AS category,
            COALESCE(si.unit, i.unit) AS unit,
            COALESCE(si.polarity, i.polarity) AS polarity,
            COALESCE(si.availability_status, i.availability_status) AS availability_status,
            COALESCE(si.derivation_formula, i.derivation_formula) AS derivation_formula,
            COALESCE(si.description, i.description) AS description,
            COALESCE(si.national_mean, i.national_mean) AS national_mean,
            COALESCE(si.national_median, i.national_median) AS national_median,
            COALESCE(si.national_min, i.national_min) AS national_min,
            COALESCE(si.national_max, i.national_max) AS national_max,
            COALESCE(si.primary_dataset_id, i.primary_dataset_id) AS primary_dataset_id,
            d.dataset_id, d.agency_code, d.dataset_title, d.official_portal_url,
            COUNT(f.region_id) as coverage_count
        FROM dim_indicators i
        LEFT JOIN snapshot_indicators si
            ON si.indicator_id = i.indicator_id AND si.snapshot_id = ?
        LEFT JOIN dim_datasets d ON COALESCE(si.primary_dataset_id, i.primary_dataset_id) = d.dataset_id
        LEFT JOIN fact_indicator_values f ON i.indicator_id = f.indicator_id AND f.snapshot_id = ?
        GROUP BY i.indicator_id
        ORDER BY category, i.indicator_id
        """,
        [snapshot_id, snapshot_id],
    )
    rows = await cursor.fetchall()

    return [
        IndicatorCatalogItem(
            indicator_id=r["indicator_id"],
            indicator_name=r["indicator_name"],
            category=r["category"],
            unit=r["unit"],
            polarity=r["polarity"],
            availability_status=r["availability_status"],
            derivation_formula=r["derivation_formula"],
            description=r["indicator_name"],  # Use name as description fallback
            stats=IndicatorStats(
                min=r["national_min"],
                mean=r["national_mean"],
                median=r["national_median"],
                max=r["national_max"],
            ),
            provenance=(
                IndicatorProvenance(
                    dataset_id=r["dataset_id"],
                    agency_code=r["agency_code"],
                    dataset_title=r["dataset_title"],
                    official_portal_url=r["official_portal_url"],
                )
                if r["dataset_id"]
                else None
            ),
            live_available=bool(r["coverage_count"] and r["coverage_count"] > 0),
            live_coverage_count=r["coverage_count"] or 0,
        )
        for r in rows
    ]


async def get_indicator_values(
    db: aiosqlite.Connection,
    indicator_id: str,
    snapshot_id: str = "2026.10.0-wia-demo",
) -> Optional[IndicatorValuesData]:
    """Return one indicator's values for all 514 regions (dict format)."""

    # Fetch indicator metadata
    cursor = await db.execute(
        """
        SELECT
            i.indicator_id,
            COALESCE(si.indicator_name, i.indicator_name) AS indicator_name,
            COALESCE(si.category, i.category) AS category,
            COALESCE(si.unit, i.unit) AS unit,
            COALESCE(si.polarity, i.polarity) AS polarity,
            COALESCE(si.availability_status, i.availability_status) AS availability_status,
            COALESCE(si.national_mean, i.national_mean) AS national_mean,
            COALESCE(si.national_median, i.national_median) AS national_median,
            COALESCE(si.national_min, i.national_min) AS national_min,
            COALESCE(si.national_max, i.national_max) AS national_max,
            COALESCE(si.primary_dataset_id, i.primary_dataset_id) AS primary_dataset_id,
            d.dataset_id, d.agency_code, d.dataset_title, d.official_portal_url
        FROM dim_indicators i
        LEFT JOIN snapshot_indicators si
            ON si.indicator_id = i.indicator_id AND si.snapshot_id = ?
        LEFT JOIN dim_datasets d ON COALESCE(si.primary_dataset_id, i.primary_dataset_id) = d.dataset_id
        WHERE i.indicator_id = ?
        """,
        [snapshot_id, indicator_id],
    )
    ind_row = await cursor.fetchone()
    if not ind_row:
        return None

    # Fetch all region values
    cursor = await db.execute(
        """
        SELECT
            f.region_id, f.raw_value, f.normalized_score,
            f.national_percentile, f.national_rank,
            f.quality_flag, f.reference_year, f.dataset_id, f.source_record_ref
        FROM fact_indicator_values f
        WHERE f.indicator_id = ? AND f.snapshot_id = ?
        ORDER BY f.region_id
        """,
        [indicator_id, snapshot_id],
    )
    value_rows = await cursor.fetchall()

    # Pick reference year from first row (all same for a snapshot indicator)
    ref_year = value_rows[0]["reference_year"] if value_rows else 2025

    values_by_region = {}
    for vr in value_rows:
        values_by_region[vr["region_id"]] = RegionIndicatorValue(
            raw=vr["raw_value"],
            norm=vr["normalized_score"],
            pct=vr["national_percentile"],
            rank=vr["national_rank"],
            flag=vr["quality_flag"],
            dataset_id=vr["dataset_id"],
            source_record_ref=vr["source_record_ref"],
        )

    indicator_meta = IndicatorMeta(
        indicator_id=ind_row["indicator_id"],
        indicator_name=ind_row["indicator_name"],
        category=ind_row["category"],
        unit=ind_row["unit"],
        polarity=ind_row["polarity"],
        availability_status=ind_row["availability_status"],
        reference_year=ref_year,
        stats=IndicatorStats(
            min=ind_row["national_min"],
            mean=ind_row["national_mean"],
            median=ind_row["national_median"],
            max=ind_row["national_max"],
        ),
        provenance=(
            IndicatorProvenance(
                dataset_id=ind_row["dataset_id"],
                agency_code=ind_row["agency_code"],
                dataset_title=ind_row["dataset_title"],
                official_portal_url=ind_row["official_portal_url"],
            )
            if ind_row["dataset_id"]
            else None
        ),
    )

    return IndicatorValuesData(
        indicator=indicator_meta,
        values_by_region=values_by_region,
    )
