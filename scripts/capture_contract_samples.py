#!/usr/bin/env python3
"""Capture frontend contract samples for the retirement snapshots."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/nusa_matra_live.db")
    parser.add_argument("--out", default="docs/staging_samples/retirement")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"LIVE database not found: {db_path}")
        return 1

    os.environ["NM_LIVE_DATABASE_PATH"] = str(db_path)
    os.environ["NM_ENABLE_LIVE_MODE"] = "true"
    os.environ.setdefault(
        "NM_ALLOWED_HOSTS",
        '["test","localhost","127.0.0.1","api.orangkeren.me"]',
    )

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    conn = sqlite3.connect(db_path)
    old_row = conn.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag='LIVE' AND indicator_count=33 "
        "ORDER BY published_at LIMIT 1"
    ).fetchone()
    new_row = conn.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag='LIVE' AND is_active_default=1 LIMIT 1"
    ).fetchone()
    conn.close()
    if old_row is None or new_row is None:
        print("Could not resolve old/new LIVE snapshots")
        return 1
    old_id, new_id = old_row[0], new_row[0]

    async def capture() -> None:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for label, snapshot_id in (("old", old_id), ("new", new_id)):
                for name, path in (
                    ("indicators", "/api/v1/indicators"),
                    ("coverage", "/api/v1/indicators/coverage"),
                    ("snapshot", f"/api/v1/snapshots/{snapshot_id}"),
                ):
                    response = await client.get(
                        path,
                        params={"mode": "live", "snapshot_id": snapshot_id},
                    )
                    (out / f"{name}_{label}.json").write_text(
                        json.dumps(
                            {"http_status": response.status_code, "body": response.json()},
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

            for name, indicator_id, snapshot_id in (
                ("values_active_new", "soc_poverty_rate", new_id),
                ("values_inf_asphalt_new", "inf_asphalt_road_village_pct", new_id),
                ("values_retired_new", "meta_dapodik_sync_rate", new_id),
            ):
                response = await client.get(
                    f"/api/v1/indicators/{indicator_id}/values",
                    params={"mode": "live", "snapshot_id": snapshot_id},
                )
                (out / f"{name}.json").write_text(
                    json.dumps(
                        {"http_status": response.status_code, "body": response.json()},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            response = await client.post(
                "/api/v1/indicators/composite-query",
                params={"mode": "live", "snapshot_id": new_id},
                json={
                    "weights": {
                        "soc_poverty_rate": 3000,
                        "hlt_stunting_prevalence": 3000,
                        "inf_safe_water_pct": 2000,
                        "inf_safe_sanitation_pct": 2000,
                    },
                    "filter_province_id": "32",
                },
            )
            (out / "composite_new.json").write_text(
                json.dumps(
                    {"http_status": response.status_code, "body": response.json()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        (out / "README.md").write_text(
            f"""# Retirement Contract Samples

Source: local LIVE database (`{db_path.name}`) built from the current working tree.
These are contract samples, not a production deployment claim.

- Historical snapshot: `{old_id}` — 33 indicators, 29 available.
- New active snapshot: `{new_id}` — 30 indicators, 29 available.
- `meta_dapodik_sync_rate`, `edu_school_travel_time_p90`, and
  `hlt_realtime_icu_occupancy` are absent from the new public catalog.
- `inf_asphalt_road_village_pct` remains public with zero observations in LIVE.
- Historical snapshot remains pin-able via `snapshot` or `snapshot_id`.
""",
            encoding="utf-8",
        )
        print(f"Wrote samples for {old_id} and {new_id} to {out}")

    asyncio.run(capture())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
