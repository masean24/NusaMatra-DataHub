"""
Pydantic schemas for BMKG Earthquake Data.
Supports standard JSON responses and RFC 7946 GeoJSON FeatureCollection.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class EarthquakeEvent(BaseModel):
    """Normalized earthquake observation event from BMKG."""

    id: str = Field(..., description="Unique event identifier based on datetime and coordinates")
    datetime: str = Field(..., description="ISO 8601 UTC timestamp of occurrence")
    date: str = Field(..., description="Indonesian date representation (e.g., '21 Okt 2026')")
    time: str = Field(..., description="Local time representation with timezone (e.g., '18:58:36 WIB')")
    magnitude: float = Field(..., description="Earthquake magnitude on Richter scale")
    depth: str = Field(..., description="Depth formatted string (e.g., '10 km')")
    depth_km: Optional[float] = Field(None, description="Numeric depth in kilometers")
    latitude: float = Field(..., description="Latitude coordinate (WGS84)")
    longitude: float = Field(..., description="Longitude coordinate (WGS84)")
    coordinates: list[float] = Field(
        ...,
        description="Standard GeoJSON [longitude, latitude] coordinates array for direct mapping",
    )
    area: str = Field(..., description="Official narrative location description from BMKG")
    potency: Optional[str] = Field(None, description="Tsunami potential statement or general warning")
    felt: Optional[str] = Field(None, description="Observed MMI shake intensity reports in affected areas")
    shakemap_url: Optional[str] = Field(None, description="Absolute URL to official BMKG Shakemap image")
    source: str = Field("BMKG", description="Originating government agency (Badan Meteorologi, Klimatologi, dan Geofisika)")


class GeoJsonGeometry(BaseModel):
    """RFC 7946 GeoJSON Point geometry."""

    type: str = "Point"
    coordinates: list[float] = Field(..., description="[longitude, latitude] array")


class GeoJsonFeature(BaseModel):
    """RFC 7946 GeoJSON Feature for an earthquake epicenter."""

    type: str = "Feature"
    id: str
    geometry: GeoJsonGeometry
    properties: dict[str, Any]


class EarthquakeGeoJsonCollection(BaseModel):
    """RFC 7946 GeoJSON FeatureCollection for direct consumption by 3D map engines."""

    type: str = "FeatureCollection"
    metadata: dict[str, Any]
    features: list[GeoJsonFeature]


class EarthquakeSummary(BaseModel):
    """Executive summary of current national earthquake activity."""

    latest: Optional[EarthquakeEvent] = Field(None, description="Latest detected seismic event")
    recent_m5_count: int = Field(..., description="Number of recent earthquakes M >= 5.0")
    felt_count: int = Field(..., description="Number of recent felt earthquakes")
    max_magnitude_recent: Optional[float] = Field(None, description="Highest magnitude among recent events")
    cached_at: str = Field(..., description="ISO 8601 timestamp when data was fetched/cached")
    cache_ttl_seconds: int = Field(60, description="Cache Time-To-Live in seconds")
    agency: str = "BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)"
    official_portal: str = "https://data.bmkg.go.id/gempabumi/"
