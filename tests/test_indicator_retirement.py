"""
Retirement and snapshot-retention regression tests.

These tests operate on a copy of the LIVE database so they never mutate the
working production database.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import settings
from app.services.snapshot_integrity import verify_content_digest

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = REPO_ROOT / "data" / "nusa_matra_live.db"
RETIRED_IDS = {
    "meta_dapodik_sync_rate",
    "edu_school_travel_time_p90",
    "hlt_realtime_icu_occupancy",
}


def _copy_database(source: Path, target: Path) -> None:
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def _run_retirement(db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["NM_LIVE_DATABASE_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "scripts/retire_public_indicators.py"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def retired_live_db(tmp_path, monkeypatch):
    if not LIVE_DB.exists():
        pytest.skip("LIVE database not available")

    target = tmp_path / "live_retirement.db"
    _copy_database(LIVE_DB, target)

    first = _run_retirement(target)
    assert first.returncode == 0, first.stderr or first.stdout

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    old_row = conn.execute(
        """
        SELECT snapshot_id, indicator_count, available_indicator_count
        FROM data_snapshots
        WHERE environment_tag = 'LIVE' AND indicator_count = 33
        ORDER BY published_at
        LIMIT 1
        """
    ).fetchone()
    new_row = conn.execute(
        """
        SELECT snapshot_id, indicator_count, available_indicator_count
        FROM data_snapshots
        WHERE environment_tag = 'LIVE' AND is_active_default = 1
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    if old_row is None:
        pytest.skip("no historical 33-indicator LIVE snapshot available")
    assert new_row is not None, "new active snapshot missing"
    assert old_row["snapshot_id"] != new_row["snapshot_id"]

    monkeypatch.setattr(settings, "live_database_path", str(target))
    monkeypatch.setattr(settings, "enable_live_mode", True)
    yield target, old_row["snapshot_id"], new_row["snapshot_id"]


@pytest.mark.asyncio
async def test_catalog_is_snapshot_scoped(client, retired_live_db):
    _, old_id, new_id = retired_live_db

    old_catalog = await client.get(
        "/api/v1/indicators", params={"mode": "live", "snapshot_id": old_id}
    )
    new_catalog = await client.get(
        "/api/v1/indicators", params={"mode": "live", "snapshot_id": new_id}
    )

    assert old_catalog.status_code == 200
    assert new_catalog.status_code == 200
    assert old_catalog.json()["meta"]["total_count"] == 33
    assert new_catalog.json()["meta"]["total_count"] == 30

    def ids(payload):
        return {
            item["indicator_id"]
            for items in payload["data"].values()
            for item in items
        }

    old_ids = ids(old_catalog.json())
    new_ids = ids(new_catalog.json())
    assert RETIRED_IDS <= old_ids
    assert not (RETIRED_IDS & new_ids)


@pytest.mark.asyncio
async def test_coverage_and_values_follow_same_filter(client, retired_live_db):
    _, old_id, new_id = retired_live_db

    old_coverage = await client.get(
        "/api/v1/indicators/coverage", params={"mode": "live", "snapshot_id": old_id}
    )
    new_coverage = await client.get(
        "/api/v1/indicators/coverage", params={"mode": "live", "snapshot_id": new_id}
    )
    assert old_coverage.status_code == 200
    assert new_coverage.status_code == 200
    assert old_coverage.json()["data"]["total_indicators"] == 33
    assert new_coverage.json()["data"]["total_indicators"] == 30
    assert set(new_coverage.json()["data"]["empty_indicators"]) == {
        "inf_asphalt_road_village_pct"
    }

    old_values = await client.get(
        f"/api/v1/indicators/meta_dapodik_sync_rate/values",
        params={"mode": "live", "snapshot_id": old_id},
    )
    new_values = await client.get(
        f"/api/v1/indicators/meta_dapodik_sync_rate/values",
        params={"mode": "live", "snapshot_id": new_id},
    )
    assert old_values.status_code == 200
    assert new_values.status_code == 404

    asphalt = await client.get(
        "/api/v1/indicators/inf_asphalt_road_village_pct/values",
        params={"mode": "live", "snapshot_id": new_id},
    )
    assert asphalt.status_code == 200
    assert asphalt.json()["data"]["values_by_region"] == {}


@pytest.mark.asyncio
async def test_composite_rejects_retired_indicator_on_new_snapshot(client, retired_live_db):
    _, _, new_id = retired_live_db
    response = await client.post(
        "/api/v1/indicators/composite-query",
        params={"mode": "live", "snapshot_id": new_id},
        json={"weights": {"meta_dapodik_sync_rate": 5000, "soc_poverty_rate": 5000}},
    )
    assert response.status_code == 422
    assert "public catalog" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_snapshot_metadata_counts_and_aliases(client, retired_live_db):
    _, old_id, new_id = retired_live_db

    old = await client.get(f"/api/v1/snapshots/{old_id}", params={"mode": "live"})
    new = await client.get(f"/api/v1/snapshots/{new_id}", params={"mode": "live"})
    assert old.status_code == 200
    assert new.status_code == 200
    assert old.json()["data"]["indicator_count"] == 33
    assert old.json()["data"]["available_indicator_count"] == 29
    assert new.json()["data"]["indicator_count"] == 30
    assert new.json()["data"]["available_indicator_count"] == 29

    alias = await client.get(
        "/api/v1/indicators/coverage",
        params={"mode": "live", "snapshot": new_id},
    )
    legacy = await client.get(
        "/api/v1/indicators/coverage",
        params={"mode": "live", "snapshot_id": new_id},
    )
    assert alias.status_code == 200
    assert legacy.status_code == 200
    assert alias.json()["data"] == legacy.json()["data"]
    assert alias.headers["X-NusaMatra-Snapshot"] == new_id


def test_retirement_is_idempotent_and_preserves_digests(retired_live_db):
    db_path, old_id, new_id = retired_live_db
    conn = sqlite3.connect(db_path)
    before = conn.execute("SELECT COUNT(*) FROM data_snapshots").fetchone()[0]
    old_valid = verify_content_digest(conn, old_id)
    new_valid = verify_content_digest(conn, new_id)
    conn.close()

    second = _run_retirement(db_path)
    assert second.returncode == 0, second.stderr or second.stdout

    conn = sqlite3.connect(db_path)
    after = conn.execute("SELECT COUNT(*) FROM data_snapshots").fetchone()[0]
    conn.close()
    assert before == after
    assert old_valid is True
    assert new_valid is True


@pytest.mark.asyncio
async def test_two_cities_stay_insufficient_without_zero(client, retired_live_db):
    _, _, new_id = retired_live_db
    response = await client.post(
        "/api/v1/indicators/composite-query",
        params={"mode": "live", "snapshot_id": new_id},
        json={
            "weights": {
                "dis_multihazard_index": 3500,
                "dis_flood_hazard_idx": 1500,
                "inf_asphalt_road_village_pct": 2500,
                "inf_electrification_pct": 2500,
            }
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rankable"] is True

    excluded = {row["region_id"]: row for row in data["insufficient_data"]}
    for region_id in ("1277", "7371"):
        assert region_id in excluded
        row = excluded[region_id]
        assert row["coverage_pct"] < 70
        assert "dis_multihazard_index" in row["missing_indicators"]
        assert "composite_score" not in row
        assert all(
            score is None or isinstance(score, (int, float))
            for score in row["component_scores"].values()
        )
