"""Consistency checks for the DEMO snapshot (canonical vulnerability semantics)."""

import sqlite3
import statistics
from pathlib import Path

import pytest

DEMO_DB = Path(__file__).parent.parent / "data" / "nusa_matra_demo.db"
SNAPSHOT = "2026.10.0-wia-demo"

pytestmark = pytest.mark.skipif(not DEMO_DB.exists(), reason="DEMO database not generated")


@pytest.fixture
def demo():
    connection = sqlite3.connect(DEMO_DB)
    yield connection
    connection.close()


def test_demo_score_direction_matches_live_semantics(demo):
    for indicator_id, expected_sign in (("soc_poverty_rate", 1), ("soc_hdi", -1)):
        rows = demo.execute(
            "SELECT raw_value, normalized_score FROM fact_indicator_values "
            "WHERE snapshot_id=? AND indicator_id=? AND normalized_score IS NOT NULL",
            (SNAPSHOT, indicator_id),
        ).fetchall()
        correlation = statistics.correlation(
            [row[0] for row in rows], [row[1] for row in rows]
        )
        assert correlation * expected_sign > 0.99


def test_demo_percentile_agrees_with_rank(demo):
    rows = demo.execute(
        "SELECT national_rank, national_percentile FROM fact_indicator_values "
        "WHERE snapshot_id=? AND indicator_id='soc_hdi' ORDER BY national_rank",
        (SNAPSHOT,),
    ).fetchall()
    assert rows[0][0] == 1
    assert rows[0][1] == 100.0
    assert rows[-1][0] == 514
    assert rows[-1][1] == 0.0
    percentiles = [row[1] for row in rows]
    assert percentiles == sorted(percentiles, reverse=True)


def test_demo_every_available_indicator_covers_514(demo):
    counts = demo.execute(
        """SELECT i.indicator_id, COUNT(f.region_id)
           FROM dim_indicators i
           LEFT JOIN fact_indicator_values f
             ON f.indicator_id = i.indicator_id AND f.snapshot_id = ?
           WHERE i.availability_status != 'UNAVAILABLE'
           GROUP BY i.indicator_id""",
        (SNAPSHOT,),
    ).fetchall()
    assert counts
    assert all(count == 514 for _, count in counts)
