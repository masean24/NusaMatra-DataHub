"""
Canonical min-max normalization and ranking for indicator observations.

Score semantics are always ``higher_is_need``:
- positive source polarity (higher raw is better) -> lower raw gets higher score
- negative source polarity (higher raw is worse) -> higher raw gets higher score

The LIVE seeder normalizes each indicator exactly once over its full canonical
observation set. This avoids the stale-row / mixed-bounds defect that produced
Lanny Jaya's 100.0 score while its raw value was not the national minimum.
"""

from __future__ import annotations

from typing import Iterable, Optional

SCORE_DIRECTION = "higher_is_need"
METHODOLOGY_VERSION = "v2.2-minmax-full-range"


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def normalize_score(
    raw_value: Optional[float],
    national_min: Optional[float],
    national_max: Optional[float],
    polarity: str,
) -> Optional[float]:
    """Return a 0-100 need score using the documented min-max transform."""
    if raw_value is None or national_min is None or national_max is None:
        return None
    if national_max <= national_min:
        # A degenerate distribution carries no ordering information. Return a
        # neutral score rather than pretending one region is maximally needy.
        return 50.0
    share = clamp((raw_value - national_min) / (national_max - national_min))
    if polarity == "positive":
        score = (1.0 - share) * 100.0
    else:
        score = share * 100.0
    return round(score, 2)


def rank_normalized_values(
    values: Iterable[tuple[str, float, float, str]],
) -> list[tuple[str, float, float, int, float]]:
    """
    Rank ``(region_id, raw, normalized, flag)`` rows.

    Returns ``(region_id, raw, normalized, national_rank, percentile)``.
    Equal normalized scores share a competition rank (1, 1, 3).
    """
    ordered = sorted(values, key=lambda item: (-item[2], item[0]))
    total = len(ordered)
    ranked: list[tuple[str, float, float, int, float]] = []
    previous_score: Optional[float] = None
    current_rank = 0
    for index, (region_id, raw, normalized, _flag) in enumerate(ordered, start=1):
        if normalized != previous_score:
            current_rank = index
            previous_score = normalized
        percentile = (
            ((total - current_rank) / (total - 1)) * 100.0 if total > 1 else 100.0
        )
        ranked.append((region_id, raw, normalized, current_rank, round(percentile, 2)))
    return ranked


def expected_score(
    raw_value: float, national_min: float, national_max: float, polarity: str
) -> float:
    return normalize_score(raw_value, national_min, national_max, polarity) or 0.0
