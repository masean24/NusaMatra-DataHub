"""
Composite score calculation service.
Supports weighted aggregation with integer basis points (Blocker #4).
"""

from typing import Optional
import aiosqlite

from app.models.indicators import (
    CompositePreset,
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

    # Note: empty weights, negative values, out-of-range, and sum != 10000
    # are all validated by CompositeQueryRequest's @field_validator.
    # We only need to validate that indicator_ids exist in the catalog.

    # Validate that all indicator_ids exist in the catalog
    placeholders_check = ",".join("?" for _ in indicator_ids)
    cursor_check = await db.execute(
        f"SELECT indicator_id FROM dim_indicators WHERE indicator_id IN ({placeholders_check})",
        indicator_ids,
    )
    found_rows = await cursor_check.fetchall()
    found_ids = {r["indicator_id"] for r in found_rows}
    unknown_ids = [iid for iid in indicator_ids if iid not in found_ids]
    if unknown_ids:
        raise ValueError(
            f"Unknown indicator_id(s): {', '.join(unknown_ids)}. "
            "Check GET /indicators for valid IDs."
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

    found_indicator_ids = {
        row["indicator_id"] for row in rows if row["normalized_score"] is not None
    }
    unavailable_indicators = [
        iid for iid in indicator_ids if iid not in found_indicator_ids
    ]
    effective_weights = (
        {iid: w for iid, w in weights.items() if iid in found_indicator_ids}
        if unavailable_indicators
        else weights
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
        unavailable_indicators=unavailable_indicators,
        effective_weights=effective_weights,
    )


COMPOSITE_PRESETS: list[CompositePreset] = [
    CompositePreset(
        preset_id="bencana_infrastruktur",
        title="Mitigasi Bencana & Ketahanan Infrastruktur",
        category="disaster_and_infrastructure",
        description="Menyorot kabupaten/kota rawan multi-bencana (IRBI & banjir) yang memerlukan penguatan infrastruktur jalan dan elektrifikasi.",
        target_focus="Infrastruktur dan Mitigasi Bencana",
        weights={
            "dis_multihazard_index": 3500,
            "dis_flood_hazard_idx": 1500,
            "inf_asphalt_road_village_pct": 2500,
            "inf_electrification_pct": 2500,
        },
    ),
    CompositePreset(
        preset_id="kemiskinan_stunting",
        title="Pengentasan Kemiskinan Ekstrem & Stunting",
        category="social_and_health",
        description="Fokus pada wilayah prioritas intervensi penanganan stunting balita, kemiskinan (P0), serta penyediaan air minum dan sanitasi layak.",
        target_focus="Sosial, Kesehatan, dan Sanitasi",
        weights={
            "soc_poverty_rate": 3000,
            "hlt_stunting_prevalence": 3000,
            "inf_safe_water_pct": 2000,
            "inf_safe_sanitation_pct": 2000,
        },
    ),
    CompositePreset(
        preset_id="pendidikan_daerah_3t",
        title="Pemerataan Kualitas Pendidikan Daerah 3T",
        category="education_access",
        description="Identifikasi daerah tertinggal dengan kerusakan ruang kelas tinggi, rasio murid-guru belum ideal, dan keterbatasan akses internet.",
        target_focus="Fasilitas dan Akses Pendidikan",
        weights={
            "edu_damaged_classrooms_pct": 3000,
            "edu_mean_years_schooling": 2500,
            "edu_student_teacher_ratio_sd": 2500,
            "inf_internet_household_pct": 2000,
        },
    ),
    CompositePreset(
        preset_id="indeks_pembangunan_terpadu",
        title="Prioritas Pembangunan Komprehensif Nasional",
        category="balanced_development",
        description="Penilaian menyeluruh lintas 4 pilar: IPM/HDI, harapan lama sekolah, usia harapan hidup, dan ketahanan risiko multi-bencana.",
        target_focus="Pembangunan Manusia dan Wilayah Holistik",
        weights={
            "soc_hdi": 2500,
            "dis_multihazard_index": 2500,
            "edu_expected_years_schooling": 2500,
            "hlt_life_expectancy": 2500,
        },
    ),
]
