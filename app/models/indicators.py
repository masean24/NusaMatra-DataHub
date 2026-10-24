"""
Indicator response models.
Matches API_CONTRACT_DRAFT.md Sections 4.1, 4.2, 4.3.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class IndicatorProvenance(BaseModel):
    """Dataset provenance for an indicator."""

    dataset_id: str
    agency_code: str
    dataset_title: Optional[str] = None
    official_portal_url: Optional[str] = None


class IndicatorStats(BaseModel):
    """National-level distribution statistics."""

    min: Optional[float] = None
    p25: Optional[float] = None
    median: Optional[float] = None
    mean: Optional[float] = None
    p75: Optional[float] = None
    max: Optional[float] = None


class IndicatorCatalogItem(BaseModel):
    """Single indicator in the catalog list (GET /indicators)."""

    indicator_id: str
    indicator_name: str
    category: str
    unit: str
    polarity: str
    availability_status: str
    derivation_formula: Optional[str] = None
    description: str
    stats: IndicatorStats
    provenance: Optional[IndicatorProvenance] = None
    live_available: bool = Field(True, description="Whether data is available in the current snapshot")
    live_coverage_count: Optional[int] = Field(None, description="Number of regions with available values")


class RegionIndicatorValue(BaseModel):
    """Compact indicator value for one region."""

    raw: Optional[float] = None
    norm: Optional[float] = None
    pct: Optional[float] = None
    rank: Optional[int] = None
    flag: str = "DEMO_EXAMPLE"
    dataset_id: Optional[str] = Field(
        None, description="Exact dataset used for this observation."
    )
    source_record_ref: Optional[str] = Field(
        None, description="Exact source record reference for this observation."
    )


class IndicatorMeta(BaseModel):
    """Indicator metadata in the values response."""

    indicator_id: str
    indicator_name: str
    category: str
    unit: str
    polarity: str
    availability_status: str
    reference_year: int
    stats: IndicatorStats
    provenance: Optional[IndicatorProvenance] = None


class IndicatorValuesData(BaseModel):
    """Payload for GET /indicators/{id}/values."""

    indicator: IndicatorMeta
    values_by_region: dict[str, RegionIndicatorValue] = {}


# --- Composite Query (POST /indicators/composite-query) ---

class CompositeQueryRequest(BaseModel):
    """
    Request body for weighted composite score calculation.
    Weights are in integer basis points (sum must equal 10000).
    Each weight must be in the range 0–10000 (inclusive).
    Blocker #4: use basis points, not floats.
    """

    weights: dict[str, int] = Field(
        ...,
        description="Map of indicator_id -> weight in basis points (1/10000). Each weight 0–10000, sum must equal 10000.",
        examples=[{
            "dis_multihazard_index": 3500,
            "soc_poverty_rate": 2500,
            "edu_damaged_classrooms_pct": 2000,
            "hlt_stunting_prevalence": 2000,
        }],
    )
    filter_province_id: Optional[str] = Field(
        None,
        description="Optional 2-digit province code to filter results.",
        pattern=r"^\d{2}$",
    )

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, w: dict[str, int]) -> dict[str, int]:
        if not w:
            raise ValueError("weights tidak boleh kosong (weights must not be empty)")
        for k, v in w.items():
            if not (0 <= v <= 10000):
                raise ValueError(
                    f"Bobot '{k}' harus dalam rentang 0..10000 bp, diterima {v}"
                )
        total = sum(w.values())
        if total != 10000:
            raise ValueError(
                f"Weights must sum to 10000 basis points, got {total}"
            )
        return w


class CompositeRegionScore(BaseModel):
    """One region's composite score in the query result."""

    region_id: str
    region_name: str
    composite_score: float
    rank: int
    national_rank: int = Field(
        0,
        description="Position across all nationally eligible regions, before province filtering.",
    )
    coverage_pct: float = Field(
        100.0,
        description="Share of the requested weight that had observations for this region.",
    )
    components_used: list[str] = Field(
        default_factory=list,
        description="Indicator IDs actually contributing to this region's score.",
    )
    missing_indicators: list[str] = Field(
        default_factory=list,
        description="Requested indicators with no observation for this region.",
    )
    effective_weights_region: dict[str, int] = Field(
        default_factory=dict,
        description="Per-region basis-point weights after redistributing to 10,000.",
    )
    component_scores: dict[str, Optional[float]] = {}
    quality_flags: dict[str, str] = Field(
        default_factory=dict,
        description="Quality flag per component (VERIFIED, IMPUTED_PROVINCE, DERIVED).",
    )


class InsufficientDataRegion(BaseModel):
    """Region excluded from ranking because its coverage is below the threshold."""

    region_id: str
    region_name: str
    coverage_pct: float
    components_used: list[str] = Field(default_factory=list)
    missing_indicators: list[str] = Field(default_factory=list)
    component_scores: dict[str, Optional[float]] = {}
    reason: str = "COVERAGE_BELOW_THRESHOLD"


class CompositeQueryResult(BaseModel):
    """Payload for POST /indicators/composite-query."""

    total_regions: int = Field(
        ..., description="Number of ranked regions returned (after province filtering)."
    )
    total_eligible_national: int = Field(
        0, description="Regions meeting the eligibility threshold nationally."
    )
    total_excluded: int = Field(
        0, description="Regions excluded from ranking because of insufficient coverage."
    )
    rankable: bool = Field(
        True,
        description="False when the requested scenario fails published rankability rules; regions is then empty.",
    )
    not_rankable_reason: Optional[str] = Field(
        None, description="Structured explanation when rankable is false."
    )
    national_coverage_pct: float = Field(
        100.0, description="Share of requested weight that has national observations."
    )
    available_weight_basis_points: int = Field(
        10000, description="Requested weight backed by nationally available indicators."
    )
    available_indicators: list[str] = Field(
        default_factory=list,
        description="Requested indicators with at least one national observation.",
    )
    score_direction: str = Field(
        "higher_is_need",
        description="Canonical score semantics: higher score means greater need for intervention.",
    )
    min_coverage_pct: int = Field(
        70, description="Minimum share of requested weight required to be ranked."
    )
    min_components: int = Field(
        2, description="Minimum number of contributing components required to be ranked."
    )
    weights_basis_points: dict[str, int]
    regions: list[CompositeRegionScore] = []
    unavailable_indicators: list[str] = Field(
        default_factory=list,
        description="Indicators requested in weights that have 0 data in this snapshot.",
    )
    effective_weights: Optional[dict[str, int]] = Field(
        None,
        description="Global effective weights after excluding nationally unavailable indicators.",
    )
    renormalized: bool = Field(
        False,
        description="Whether global weights were rescaled because some requested indicators have no observations.",
    )
    insufficient_data: list[InsufficientDataRegion] = Field(
        default_factory=list,
        description="Regions that could not be ranked, with the components that were available.",
    )


class PresetAvailability(BaseModel):
    """Live availability metadata for a policy preset."""

    available_indicators: list[str] = Field(default_factory=list)
    unavailable_indicators: list[str] = Field(default_factory=list)
    indicator_coverage_pct: dict[str, float] = Field(default_factory=dict)
    effective_weights: dict[str, int] = Field(default_factory=dict)
    coverage_weight_pct: float = Field(
        0.0, description="Share of preset weight backed by at least one observation."
    )
    rankable: bool = Field(
        False, description="True when coverage_weight_pct meets the eligibility threshold."
    )


class CompositePreset(BaseModel):
    """Pre-defined policy weighting scenario."""

    preset_id: str
    title: str
    category: str
    description: str
    target_focus: str
    weights: dict[str, int]
    availability: Optional[PresetAvailability] = None
