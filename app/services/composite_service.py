"""
Composite score calculation service.

Canonical semantics (DEMO and LIVE):
    normalized_score / composite_score 100 = most vulnerable / most in need.

Ranking rules:
- Nationally unavailable indicators are removed and remaining weights are
  rescaled to 10,000 basis points (global renormalization).
- Each region is then evaluated on the components it actually has. Weights are
  redistributed per region only when the region meets the coverage gate.
- Regions below the gate are returned in ``insufficient_data`` and are never
  ranked as if missing data were zero.
- ``national_rank`` is computed before province filtering; ``rank`` is the
  position within the returned (filtered) list.
"""

from typing import Optional

import aiosqlite

from app.config import settings
from app.models.indicators import (
    CompositePreset,
    CompositeQueryRequest,
    CompositeQueryResult,
    CompositeRegionScore,
    InsufficientDataRegion,
    PresetAvailability,
)

SCORE_DIRECTION = "higher_is_need"
TOTAL_BASIS_POINTS = 10000


def apportion_weights(weights: dict[str, int], target: int = TOTAL_BASIS_POINTS) -> dict[str, int]:
    """Scale integer weights to ``target`` using largest-remainder apportionment."""
    usable = {key: value for key, value in weights.items() if value > 0}
    total = sum(usable.values())
    if total <= 0:
        return {}

    exact = {key: value * target / total for key, value in usable.items()}
    apportioned = {key: int(value) for key, value in exact.items()}
    remainder = target - sum(apportioned.values())

    order = sorted(
        exact,
        key=lambda key: (-(exact[key] - apportioned[key]), key),
    )
    for key in order[:remainder]:
        apportioned[key] += 1
    return apportioned


def _assign_rank(entries: list, attribute: str) -> None:
    """Competition ranking: equal scores share a rank (1, 1, 3)."""
    previous_score = None
    current_rank = 0
    for index, entry in enumerate(entries, start=1):
        score = getattr(entry, "composite_score")
        if score != previous_score:
            current_rank = index
            previous_score = score
        setattr(entry, attribute, current_rank)


async def compute_composite_scores(
    db: aiosqlite.Connection,
    request: CompositeQueryRequest,
    snapshot_id: str = "2026.10.0-wia-demo",
) -> CompositeQueryResult:
    """Calculate weighted composite vulnerability scores for eligible regions."""
    weights = request.weights
    requested_ids = list(weights.keys())

    # Validate that every requested indicator exists in the catalog.
    placeholders_check = ",".join("?" for _ in requested_ids)
    cursor_check = await db.execute(
        f"SELECT indicator_id FROM dim_indicators WHERE indicator_id IN ({placeholders_check})",
        requested_ids,
    )
    found_rows = await cursor_check.fetchall()
    found_ids = {row["indicator_id"] for row in found_rows}
    unknown_ids = [indicator_id for indicator_id in requested_ids if indicator_id not in found_ids]
    if unknown_ids:
        raise ValueError(
            f"Unknown indicator_id(s): {', '.join(unknown_ids)}. "
            "Check GET /indicators for valid IDs."
        )

    placeholders = ",".join("?" for _ in requested_ids)
    cursor = await db.execute(
        f"""
        SELECT
            f.region_id,
            r.name AS region_name,
            r.parent_region_id,
            f.indicator_id,
            f.normalized_score,
            f.quality_flag
        FROM fact_indicator_values f
        JOIN dim_regions r ON f.region_id = r.region_id
        WHERE f.snapshot_id = ?
          AND f.indicator_id IN ({placeholders})
          AND r.level IN ('kabupaten', 'kota')
        ORDER BY f.region_id, f.indicator_id
        """,
        [snapshot_id] + requested_ids,
    )
    rows = await cursor.fetchall()

    # --- Global availability & renormalization --------------------------------
    available_ids = {
        row["indicator_id"] for row in rows if row["normalized_score"] is not None
    }
    unavailable_indicators = [
        indicator_id for indicator_id in requested_ids if indicator_id not in available_ids
    ]
    if not available_ids:
        raise ValueError(
            f"All requested indicators are unavailable in this snapshot: "
            f"{', '.join(unavailable_indicators)}. "
            "Check GET /api/v1/indicators/coverage for verified indicators."
        )

    if unavailable_indicators:
        effective_weights = apportion_weights(
            {indicator_id: weights[indicator_id] for indicator_id in requested_ids if indicator_id in available_ids}
        )
        renormalized = True
    else:
        effective_weights = dict(weights)
        renormalized = False

    active_ids = [indicator_id for indicator_id in requested_ids if indicator_id in available_ids]
    required_components = min(settings.composite_min_components, len(requested_ids))
    coverage_threshold_bp = settings.composite_min_coverage_pct * 100
    available_weight_bp = sum(weights[indicator_id] for indicator_id in active_ids)
    national_coverage_pct = round(available_weight_bp / 100.0, 1)
    rankable = (
        national_coverage_pct >= settings.composite_min_coverage_pct
        and len(active_ids) >= required_components
    )

    if not rankable:
        reasons = []
        if national_coverage_pct < settings.composite_min_coverage_pct:
            reasons.append(
                f"national weight coverage {national_coverage_pct}% is below "
                f"the {settings.composite_min_coverage_pct}% threshold"
            )
        if len(active_ids) < required_components:
            reasons.append(
                f"only {len(active_ids)} of the required {required_components} "
                "components have national observations"
            )
        return CompositeQueryResult(
            total_regions=0,
            total_eligible_national=0,
            total_excluded=0,
            rankable=False,
            not_rankable_reason="; ".join(reasons),
            national_coverage_pct=national_coverage_pct,
            available_weight_basis_points=available_weight_bp,
            available_indicators=active_ids,
            score_direction=SCORE_DIRECTION,
            min_coverage_pct=settings.composite_min_coverage_pct,
            min_components=required_components,
            weights_basis_points=weights,
            regions=[],
            unavailable_indicators=unavailable_indicators,
            effective_weights=effective_weights,
            renormalized=renormalized,
            insufficient_data=[],
        )

    # --- Group observations per region ---------------------------------------
    region_data: dict[str, dict] = {}
    for row in rows:
        region_id = row["region_id"]
        entry = region_data.setdefault(
            region_id,
            {
                "region_name": row["region_name"],
                "parent_region_id": row["parent_region_id"],
                "components": {},
                "quality_flags": {},
            },
        )
        indicator_id = row["indicator_id"]
        if indicator_id in effective_weights and row["normalized_score"] is not None:
            entry["components"][indicator_id] = row["normalized_score"]
            entry["quality_flags"][indicator_id] = row["quality_flag"]

    # Include every kab/kota, even those with no observation at all, so excluded
    # regions are reported instead of disappearing from the response.
    all_regions_cursor = await db.execute(
        "SELECT region_id, name, parent_region_id FROM dim_regions "
        "WHERE level IN ('kabupaten', 'kota')"
    )
    for row in await all_regions_cursor.fetchall():
        region_data.setdefault(
            row["region_id"],
            {
                "region_name": row["name"],
                "parent_region_id": row["parent_region_id"],
                "components": {},
                "quality_flags": {},
            },
        )

    eligible: list[CompositeRegionScore] = []
    excluded: list[InsufficientDataRegion] = []

    for region_id, entry in region_data.items():
        present = entry["components"]
        present_weight = sum(weights[indicator_id] for indicator_id in present)
        coverage_pct = round(present_weight / 100.0, 1)

        if len(present) < required_components or present_weight < coverage_threshold_bp:
            excluded.append(
                InsufficientDataRegion(
                    region_id=region_id,
                    region_name=entry["region_name"],
                    coverage_pct=coverage_pct,
                    components_used=sorted(present),
                    missing_indicators=[
                        indicator_id for indicator_id in requested_ids if indicator_id not in present
                    ],
                    component_scores={indicator_id: present.get(indicator_id) for indicator_id in requested_ids},
                )
            )
            continue

        region_weights = apportion_weights(
            {indicator_id: effective_weights[indicator_id] for indicator_id in present}
        )
        composite = sum(
            score * (region_weights[indicator_id] / TOTAL_BASIS_POINTS)
            for indicator_id, score in present.items()
            if region_weights.get(indicator_id)
        )

        eligible.append(
            CompositeRegionScore(
                region_id=region_id,
                region_name=entry["region_name"],
                composite_score=round(composite, 2),
                rank=0,
                coverage_pct=coverage_pct,
                components_used=sorted(present),
                missing_indicators=[
                    indicator_id for indicator_id in requested_ids if indicator_id not in present
                ],
                effective_weights_region=region_weights,
                component_scores={indicator_id: present.get(indicator_id) for indicator_id in requested_ids},
                quality_flags=entry["quality_flags"],
            )
        )

    # --- National ranking (before province filter) ----------------------------
    eligible.sort(key=lambda item: (-item.composite_score, item.region_id))
    _assign_rank(eligible, "national_rank")

    filtered = eligible
    if request.filter_province_id:
        filtered = [
            item
            for item in eligible
            if region_data[item.region_id]["parent_region_id"] == request.filter_province_id
        ]
    _assign_rank(filtered, "rank")

    if request.filter_province_id:
        excluded = [
            item
            for item in excluded
            if region_data[item.region_id]["parent_region_id"] == request.filter_province_id
        ]
    excluded.sort(key=lambda item: (-item.coverage_pct, item.region_id))

    return CompositeQueryResult(
        total_regions=len(filtered),
        total_eligible_national=len(eligible),
        total_excluded=len(excluded),
        rankable=True,
        not_rankable_reason=None,
        national_coverage_pct=national_coverage_pct,
        available_weight_basis_points=available_weight_bp,
        available_indicators=active_ids,
        score_direction=SCORE_DIRECTION,
        min_coverage_pct=settings.composite_min_coverage_pct,
        min_components=required_components,
        weights_basis_points=weights,
        regions=filtered,
        unavailable_indicators=unavailable_indicators,
        effective_weights=effective_weights,
        renormalized=renormalized,
        insufficient_data=excluded,
    )


async def compute_preset_availability(
    db: aiosqlite.Connection,
    preset: CompositePreset,
    snapshot_id: str,
) -> PresetAvailability:
    """Attach live coverage metadata to a static policy preset."""
    indicator_ids = list(preset.weights)
    placeholders = ",".join("?" for _ in indicator_ids)

    cursor = await db.execute(
        f"""
        SELECT f.indicator_id, COUNT(DISTINCT f.region_id) AS coverage
        FROM fact_indicator_values f
        JOIN dim_regions r ON f.region_id = r.region_id
        WHERE f.snapshot_id = ?
          AND f.indicator_id IN ({placeholders})
          AND r.level IN ('kabupaten', 'kota')
          AND f.normalized_score IS NOT NULL
        GROUP BY f.indicator_id
        """,
        [snapshot_id] + indicator_ids,
    )
    coverage_by_indicator = {
        row["indicator_id"]: row["coverage"] for row in await cursor.fetchall()
    }

    total_cursor = await db.execute(
        "SELECT COUNT(*) AS total FROM dim_regions WHERE level IN ('kabupaten', 'kota')"
    )
    total_row = await total_cursor.fetchone()
    total_regions = total_row["total"] if total_row else 514

    indicator_coverage = {
        indicator_id: round(
            (coverage_by_indicator.get(indicator_id, 0) / total_regions) * 100, 1
        )
        for indicator_id in indicator_ids
    }
    available = [
        indicator_id
        for indicator_id in indicator_ids
        if coverage_by_indicator.get(indicator_id, 0) > 0
    ]
    unavailable = [indicator_id for indicator_id in indicator_ids if indicator_id not in available]

    effective_weights = apportion_weights(
        {indicator_id: preset.weights[indicator_id] for indicator_id in available}
    )
    coverage_weight_pct = round(
        sum(preset.weights[indicator_id] for indicator_id in available) / 100.0, 1
    )
    required_components = min(settings.composite_min_components, len(indicator_ids))

    return PresetAvailability(
        available_indicators=available,
        unavailable_indicators=unavailable,
        indicator_coverage_pct=indicator_coverage,
        effective_weights=effective_weights,
        coverage_weight_pct=coverage_weight_pct,
        rankable=(
            coverage_weight_pct >= settings.composite_min_coverage_pct
            and len(available) >= required_components
        ),
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
