"""
Health check and system status models.
Matches API_CONTRACT_DRAFT.md Section 5.
"""

from typing import Optional
from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    """Database connectivity status."""

    status: str  # "connected" or "error"
    tables: Optional[dict[str, int]] = None
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Full health check payload."""

    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    mode: str
    active_snapshot: str
    database: DatabaseHealth
    redis: Optional[str] = "not_configured"
    static_fallback_ready: bool = True


class DatasetInfo(BaseModel):
    """Single dataset in the provenance catalog."""

    dataset_id: str
    agency_code: str
    agency_name: str
    dataset_title: str
    official_portal_url: str
    api_or_download_url: str
    access_method: str
    license_name: str
    update_frequency: str
    last_ingested_at: str
    raw_sha256: str


class SnapshotInfo(BaseModel):
    """A data snapshot version."""

    snapshot_id: str
    label: str
    environment_tag: str
    is_active_default: bool
    boundary_version: str
    created_at: str
    published_at: Optional[str] = None
    manifest_checksum: str
    notes: Optional[str] = None
    indicator_completeness_pct: Optional[float] = None
