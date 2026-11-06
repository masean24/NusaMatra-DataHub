"""Build the static region area reference from the high-resolution BIG boundaries.

The API uses this reference for display metadata only. Snapshot content digests
continue to use dim_regions.area_km2, so rebuilding this file does not change
any snapshot hash.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pyproj import Geod

ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES = ROOT / "data" / "boundaries"
OUTPUT = ROOT / "data" / "region_areas.csv"

SOURCES = (
    ("provinsi", BOUNDARIES / "indonesia_provinsi_high.geojson"),
    ("kabupaten_kota", BOUNDARIES / "indonesia_kabupaten_high.geojson"),
)


def _ring_area_km2(geod: Geod, ring: list[list[float]]) -> float:
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    area, _ = geod.polygon_area_perimeter(lons, lats)
    return abs(area) / 1_000_000


def _geometry_area_km2(geod: Geod, geometry: dict) -> float:
    geometry_type = geometry["type"]
    coordinates = geometry["coordinates"]

    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise ValueError(f"Unsupported geometry type: {geometry_type}")

    total = 0.0
    for polygon in polygons:
        if not polygon:
            continue
        total += _ring_area_km2(geod, polygon[0])
        total -= sum(_ring_area_km2(geod, hole) for hole in polygon[1:])
    return total


def main() -> None:
    geod = Geod(ellps="WGS84")
    rows: list[tuple[str, str, str, str]] = []

    for level, path in SOURCES:
        with path.open(encoding="utf-8") as handle:
            collection = json.load(handle)

        for feature in collection["features"]:
            properties = feature["properties"]
            area = _geometry_area_km2(geod, feature["geometry"])
            if area <= 0:
                raise ValueError(
                    f"Invalid area for {properties['region_id']}: {area}"
                )
            rows.append(
                (
                    str(properties["region_id"]),
                    level,
                    properties["name"],
                    f"{area:.2f}",
                )
            )

    if len(rows) != 552:
        raise ValueError(f"Expected 552 regions, got {len(rows)}")

    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("Duplicate region_id in boundary sources")

    rows.sort(key=lambda row: row[0])

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region_id", "level", "name", "area_km2"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} regions to {OUTPUT}")


if __name__ == "__main__":
    main()
