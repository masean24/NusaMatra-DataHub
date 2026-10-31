#!/usr/bin/env python3
"""Capture v2.4 frontend contract samples from the local LIVE database."""

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
    parser.add_argument("--out", default="docs/testing/staging_samples/contract_v2_4")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"LIVE database not found: {db_path}")
        return 1

    os.environ["NM_LIVE_DATABASE_PATH"] = str(db_path)
    os.environ["NM_ENABLE_LIVE_MODE"] = "true"
    os.environ.setdefault(
        "NM_ALLOWED_HOSTS",
        '["test","localhost","127.0.0.1","api.nusamatra.site"]',
    )

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag='LIVE' AND is_active_default=1 LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        print("Could not resolve the active LIVE snapshot")
        return 1
    snapshot_id = row[0]

    async def capture() -> None:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        params = {"mode": "live", "snapshot_id": snapshot_id}

        def write(name: str, response) -> None:
            (out / f"{name}.json").write_text(
                json.dumps(
                    {"http_status": response.status_code, "body": response.json()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            write(
                "error_validation_query",
                await client.get(
                    "/api/v1/regions",
                    params={**params, "level": "invalid"},
                ),
            )
            write(
                "error_validation_weight",
                await client.post(
                    "/api/v1/indicators/composite-query",
                    params=params,
                    json={
                        "weights": {
                            "dis_multihazard_index": 5000,
                            "soc_poverty_rate": 3000,
                        }
                    },
                ),
            )
            write(
                "error_not_found",
                await client.get(
                    "/api/v1/indicators/does_not_exist/values",
                    params=params,
                ),
            )
            write(
                "meta_values",
                await client.get(
                    "/api/v1/indicators/soc_poverty_rate/values",
                    params=params,
                ),
            )
            write(
                "meta_region_detail",
                await client.get("/api/v1/regions/1101", params=params),
            )
            write(
                "meta_coverage",
                await client.get("/api/v1/indicators/coverage", params=params),
            )
            write(
                "meta_datasets",
                await client.get("/api/v1/datasets", params=params),
            )
            write(
                "meta_snapshots",
                await client.get("/api/v1/snapshots", params=params),
            )
            write(
                "meta_composite",
                await client.post(
                    "/api/v1/indicators/composite-query",
                    params=params,
                    json={
                        "weights": {
                            "soc_poverty_rate": 3000,
                            "hlt_stunting_prevalence": 3000,
                            "inf_safe_water_pct": 2000,
                            "inf_safe_sanitation_pct": 2000,
                        },
                        "filter_province_id": "32",
                    },
                ),
            )

        (out / "README.md").write_text(
            f"""# v2.4 Contract Samples

Source: local LIVE database (`{db_path.name}`) built from the current working tree.
These are contract samples, not a production deployment claim.
Active LIVE snapshot: `{snapshot_id}`.

## Error envelope

Every 422 and HTTP error now uses:

```json
{{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed.",
  "detail": "query.level: String should match pattern ..."
}}
```

Weight validation uses `code: "WEIGHT_VALIDATION_ERROR"` with the same envelope.
`detail` is a readable string. The previous `{{"detail": [...]}}` shape is gone.

## Boundary metadata

`meta.boundary_version` is populated for snapshot-backed endpoints, including
`/indicators/coverage`, `/indicators/{{id}}/values`, `/datasets`,
`/snapshots`, `/regions`, `/boundaries/*`, and `/composite-query`.

## Percentile direction

Every response includes `meta.score_direction = "higher_is_need"`. Region detail
items also include `polarity` (`positive` or `negative`). `national_percentile`
is a need percentile: higher means greater need, regardless of raw-value
polarity.

## Snapshot active marker

`GET /snapshots` exposes the active marker as `data[].is_active_default`.
""",
            encoding="utf-8",
        )
        print(f"Wrote v2.4 samples for {snapshot_id} to {out}")

    asyncio.run(capture())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
