"""
Region (wilayah) response models.
Matches API_CONTRACT_DRAFT.md Sections 2.1 and 2.2.
"""

from typing import Optional
from pydantic import BaseModel, Field


class RegionCodes(BaseModel):
    """Cross-agency code bridging for a region."""

    kemendagri: str = Field(..., examples=["32.01"])
    bps: str = Field(..., examples=["3201"])
    kemendikdasmen: Optional[str] = Field(None, examples=["020500"])


class AnchorPoint(BaseModel):
    """Centroid / label point guaranteed on land."""

    lng: float
    lat: float


class RegionSummary(BaseModel):
    """Region in list responses (GET /regions)."""

    region_id: str
    parent_region_id: Optional[str] = None
    province_name: Optional[str] = None
    level: str
    name: str
    short_name: str
    codes: RegionCodes
    island_group: str
    area_km2: Optional[float] = None
    anchor_point: AnchorPoint
    bbox: list[float] = Field(
        ..., min_length=4, max_length=4,
        description="[minLng, minLat, maxLng, maxLat]",
    )


class IndicatorProvenance(BaseModel):
    """Data provenance for a single indicator value."""

    dataset_id: str
    agency_code: str
    official_url: Optional[str] = None


class RegionIndicatorValue(BaseModel):
    """One indicator's value attached to a region profile."""

    indicator_id: str
    indicator_name: str
    category: str
    raw_value: Optional[float] = None
    unit: str
    normalized_score: Optional[float] = None
    national_percentile: Optional[float] = None
    national_rank: Optional[int] = None
    reference_year: int
    quality_flag: str = "DEMO_EXAMPLE"
    provenance: IndicatorProvenance


class CompositeScores(BaseModel):
    """Pre-computed composite domain scores for a region."""

    overall_priority_index: Optional[float] = None
    disaster_risk: Optional[float] = None
    socioeconomic: Optional[float] = None
    education_access: Optional[float] = None
    healthcare_access: Optional[float] = None
    infrastructure: Optional[float] = None
    data_reliability: Optional[float] = None


class RegionDetail(BaseModel):
    """Full region profile (GET /regions/{region_id})."""

    region: RegionSummary
    composite_scores: CompositeScores
    indicators: list[RegionIndicatorValue] = []
