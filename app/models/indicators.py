"""
Indicator response models.
Matches API_CONTRACT_DRAFT.md Sections 4.1, 4.2, 4.3.
"""

from typing import Optional
from pydantic import BaseModel, Field


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


class RegionIndicatorValue(BaseModel):
    """Compact indicator value for one region."""

    raw: Optional[float] = None
    norm: Optional[float] = None
    pct: Optional[float] = None
    rank: Optional[int] = None
    flag: str = "DEMO_EXAMPLE"


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
    Blocker #4: use basis points, not floats.
    """

    weights: dict[str, int] = Field(
        ...,
        description="Map of indicator_id -> weight in basis points (1/10000). Sum must equal 10000.",
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
    )


class CompositeRegionScore(BaseModel):
    """One region's composite score in the query result."""

    region_id: str
    region_name: str
    composite_score: float
    rank: int
    component_scores: dict[str, Optional[float]] = {}


class CompositeQueryResult(BaseModel):
    """Payload for POST /indicators/composite-query."""

    total_regions: int
    weights_basis_points: dict[str, int]
    regions: list[CompositeRegionScore] = []


class CompositePreset(BaseModel):
    """Pre-defined policy weighting scenario."""

    preset_id: str
    title: str
    category: str
    description: str
    target_focus: str
    weights: dict[str, int]
