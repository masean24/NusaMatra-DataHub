"""Integrity checks against the generated LIVE snapshot.

These tests are skipped when the LIVE database has not been generated (for
example in a clean checkout before running ``scripts/seed_live_db.py``).
"""

import sqlite3
import statistics
from pathlib import Path

import pytest

LIVE_DB = Path(__file__).parent.parent / "data" / "nusa_matra_live.db"


def _active_snapshot() -> str:
    if not LIVE_DB.exists():
        return "2026.10.0-official-live"
    connection = sqlite3.connect(LIVE_DB)
    row = connection.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag = 'LIVE' AND is_active_default = 1 "
        "ORDER BY published_at DESC LIMIT 1"
    ).fetchone()
    connection.close()
    return row[0] if row else "2026.10.0-official-live"


SNAPSHOT = _active_snapshot()

pytestmark = pytest.mark.skipif(
    not LIVE_DB.exists(), reason="LIVE database not generated"
)


@pytest.fixture
def live():
    connection = sqlite3.connect(LIVE_DB)
    yield connection
    connection.close()


def test_all_514_kabkota_have_observations(live):
    count = live.execute(
        "SELECT COUNT(DISTINCT region_id) FROM fact_indicator_values WHERE snapshot_id = ?",
        (SNAPSHOT,),
    ).fetchone()[0]
    assert count == 514


def test_national_rank_does_not_exceed_population(live):
    max_rank = live.execute(
        "SELECT MAX(national_rank) FROM fact_indicator_values WHERE snapshot_id = ?",
        (SNAPSHOT,),
    ).fetchone()[0]
    assert max_rank <= 514


def test_kabupaten_and_kota_with_same_name_are_not_swapped(live):
    """Kota Bogor (3271) must not receive Kabupaten Bogor (3201) values."""
    kab = live.execute(
        "SELECT raw_value FROM fact_indicator_values WHERE region_id='3201' AND indicator_id='soc_hdi' AND snapshot_id=?",
        (SNAPSHOT,),
    ).fetchone()
    kota = live.execute(
        "SELECT raw_value FROM fact_indicator_values WHERE region_id='3271' AND indicator_id='soc_hdi' AND snapshot_id=?",
        (SNAPSHOT,),
    ).fetchone()
    assert kab and kota
    assert round(kab[0], 2) == 72.39
    assert round(kota[0], 2) == 78.52


def test_score_direction_is_vulnerability_in_live(live):
    """Higher normalized_score must mean greater vulnerability in LIVE."""
    for indicator_id, expected_sign in (
        ("soc_poverty_rate", 1),
        ("soc_hdi", -1),
    ):
        rows = live.execute(
            "SELECT raw_value, normalized_score FROM fact_indicator_values "
            "WHERE snapshot_id=? AND indicator_id=? AND normalized_score IS NOT NULL",
            (SNAPSHOT, indicator_id),
        ).fetchall()
        correlation = statistics.correlation(
            [row[0] for row in rows], [row[1] for row in rows]
        )
        assert correlation * expected_sign > 0.99, (
            f"{indicator_id} direction is inconsistent (corr={correlation})"
        )


def test_no_observations_attached_to_provinces(live):
    count = live.execute(
        """SELECT COUNT(*) FROM fact_indicator_values f
           JOIN dim_regions r ON r.region_id = f.region_id
           WHERE f.snapshot_id = ? AND r.level = 'provinsi'""",
        (SNAPSHOT,),
    ).fetchone()[0]
    assert count == 0


def test_internal_reliability_indicators_are_derived(live):
    for indicator_id in ("meta_indicator_completeness", "meta_freshness_lag_years"):
        count = live.execute(
            "SELECT COUNT(*) FROM fact_indicator_values WHERE snapshot_id=? AND indicator_id=?",
            (SNAPSHOT, indicator_id),
        ).fetchone()[0]
        assert count == 514


def test_verified_kabkota_water_replaces_province_imputation(live):
    flags = dict(
        live.execute(
            """SELECT quality_flag, COUNT(*) FROM fact_indicator_values
               WHERE snapshot_id=? AND indicator_id='inf_safe_water_pct'
               GROUP BY quality_flag""",
            (SNAPSHOT,),
        ).fetchall()
    )
    assert flags.get("VERIFIED", 0) == 513
    assert flags.get("IMPUTED_PROVINCE", 0) == 1


def test_lanny_jaya_water_normalization_regression(live):
    row = live.execute(
        """SELECT raw_value, normalized_score, national_rank, quality_flag,
                  dataset_id, source_record_ref
           FROM fact_indicator_values
           WHERE snapshot_id=? AND indicator_id='inf_safe_water_pct' AND region_id='9507'""",
        (SNAPSHOT,),
    ).fetchone()
    assert row is not None
    raw, normalized, rank, flag, dataset_id, source_ref = row
    assert round(raw, 2) == 32.89
    assert round(normalized, 2) == 78.89
    assert rank == 7
    assert flag == "IMPUTED_PROVINCE"
    assert dataset_id == "bps_provincial_sdgs_2025"
    assert "PAPUA PEGUNUNGAN" in source_ref


def test_all_live_observations_match_frozen_normalization_bounds(live):
    for indicator_id, polarity, national_min, national_max in live.execute(
        """SELECT si.indicator_id, si.polarity, si.national_min, si.national_max
           FROM snapshot_indicators si
           WHERE si.snapshot_id=? AND si.observation_count > 0""",
        (SNAPSHOT,),
    ):
        for region_id, raw, stored in live.execute(
            """SELECT region_id, raw_value, normalized_score
               FROM fact_indicator_values
               WHERE snapshot_id=? AND indicator_id=?""",
            (SNAPSHOT, indicator_id),
        ):
            share = max(
                0.0,
                min(1.0, (raw - national_min) / (national_max - national_min)),
            )
            expected = (1.0 - share) * 100 if polarity == "positive" else share * 100
            assert abs(expected - stored) <= 0.02, (
                f"{indicator_id}/{region_id}: stored {stored}, expected {expected:.2f}"
            )


def test_electrification_remains_flagged_as_imputed(live):
    flags = dict(
        live.execute(
            """SELECT quality_flag, COUNT(*) FROM fact_indicator_values
               WHERE snapshot_id=? AND indicator_id='inf_electrification_pct'
               GROUP BY quality_flag""",
            (SNAPSHOT,),
        ).fetchall()
    )
    assert flags.get("IMPUTED_PROVINCE", 0) == 514
    assert flags.get("VERIFIED", 0) == 0


def test_new_official_indicators_are_populated(live):
    expected_minimum = {
        "edu_net_enrollment_smp": 514,
        "edu_net_enrollment_sma": 514,
        "edu_student_teacher_ratio_sd": 514,
        "edu_damaged_classrooms_pct": 514,
        "soc_dependency_ratio": 514,
        "inf_internet_household_pct": 514,
        "hlt_jkn_coverage_pct": 514,
        "hlt_facilities_per_10k": 514,
        "hlt_doctors_per_10k": 514,
        "dis_affected_pop_per_10k": 514,
        "dis_events_5yr_freq": 510,
    }
    for indicator_id, minimum in expected_minimum.items():
        count = live.execute(
            "SELECT COUNT(*) FROM fact_indicator_values WHERE snapshot_id=? AND indicator_id=?",
            (SNAPSHOT, indicator_id),
        ).fetchone()[0]
        assert count >= minimum, f"{indicator_id}: expected >= {minimum}, got {count}"


def test_province_imputed_indicators_are_flagged(live):
    for indicator_id in (
        "inf_internet_household_pct",
        "hlt_jkn_coverage_pct",
        "hlt_doctors_per_10k",
        "dis_affected_pop_per_10k",
    ):
        flags = dict(
            live.execute(
                """SELECT quality_flag, COUNT(*) FROM fact_indicator_values
                   WHERE snapshot_id=? AND indicator_id=? GROUP BY quality_flag""",
                (SNAPSHOT, indicator_id),
            ).fetchall()
        )
        assert flags.get("IMPUTED_PROVINCE", 0) == 514
        assert flags.get("VERIFIED", 0) == 0

