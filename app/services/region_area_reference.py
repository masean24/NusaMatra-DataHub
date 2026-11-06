"""Static region area reference derived from high-resolution BIG boundaries.

Area is display metadata, not snapshot content: it is intentionally kept out of
dim_regions and therefore out of content_sha256. See docs/api/API_SPECIFICATION.md.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Optional

REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "region_areas.csv"
)


@lru_cache(maxsize=1)
def _area_by_region() -> dict[str, float]:
    if not REFERENCE_PATH.exists():
        return {}

    with REFERENCE_PATH.open(encoding="utf-8", newline="") as handle:
        return {
            row["region_id"]: round(float(row["area_km2"]), 2)
            for row in csv.DictReader(handle)
        }


def reference_area_km2(region_id: str) -> Optional[float]:
    """Return the geodesic reference area, or None when no reference exists."""
    return _area_by_region().get(str(region_id))
