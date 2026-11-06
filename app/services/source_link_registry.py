"""Reference source-link registry.

The registry is display/provenance metadata only. It is intentionally loaded
from a CSV and never written back to dim_datasets/dim_indicators, so snapshot
content digests remain immutable.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

REFERENCE_VERSION = "2026-11-sources-2"
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "source_links.csv"

VALID_LEVELS = {"table", "dataset", "publication", "dashboard", "portal"}
VALID_VERIFICATIONS = {
    "verified",
    "pending",
    "partial",
    "problem_unresolved",
    "not_applicable",
}


@dataclass(frozen=True)
class SourceLink:
    url: Optional[str]
    level: Optional[str]
    note_idn: Optional[str]
    note_en: Optional[str]
    verification: Optional[str] = None
    dataset_id_override: Optional[str] = None


@lru_cache(maxsize=1)
def _registry() -> dict[tuple[str, str], SourceLink]:
    if not REGISTRY_PATH.exists():
        return {}

    records: dict[tuple[str, str], SourceLink] = {}
    with REGISTRY_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            level = (row.get("source_link_level") or "").strip() or None
            if level is not None and level not in VALID_LEVELS:
                raise ValueError(f"Invalid source_link_level: {level}")
            verification = (row.get("source_verification") or "").strip() or None
            if verification is not None and verification not in VALID_VERIFICATIONS:
                raise ValueError(f"Invalid source_verification: {verification}")
            records[(row["record_type"], row["record_id"])] = SourceLink(
                url=(row.get("official_portal_url") or "").strip() or None,
                level=level,
                note_idn=(row.get("source_note_idn") or "").strip() or None,
                note_en=(row.get("source_note_en") or "").strip() or None,
                verification=verification,
                dataset_id_override=(
                    (row.get("dataset_id_override") or "").strip() or None
                ),
            )
    return records


def indicator_source(indicator_id: str) -> Optional[SourceLink]:
    return _registry().get(("indicator", indicator_id))


def dataset_source(dataset_id: str) -> Optional[SourceLink]:
    return _registry().get(("dataset", dataset_id))


def resolved_dataset_id(
    indicator_id: str, region_id: str, fact_dataset_id: Optional[str]
) -> Optional[str]:
    """Return the approved source dataset for one observation.

    Water 9507 is a documented exception: its factual dataset stays on the
    provincial fallback rather than the indicator's usual kab/kota dataset.
    """
    link = indicator_source(indicator_id)
    if not link or not link.dataset_id_override:
        return fact_dataset_id
    if indicator_id == "inf_safe_water_pct" and str(region_id) == "9507":
        return fact_dataset_id
    return link.dataset_id_override
