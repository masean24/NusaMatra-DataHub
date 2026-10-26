# Indicator Retirement & Snapshot Retention (v2.3)

## Status

- Local implementation: done.
- Production deploy: not yet.
- Historical snapshot retained: `2026.10.0-live-62354dfad392d985` (33 indicators, 29 available).
- New active local snapshot: `2026.10.0-live-0de6ac68f0d55b3a` (30 indicators, 29 available).

The new snapshot ID is content-addressed. A fresh LIVE seed may produce a different
ID because facts are re-ingested, but the catalog semantics are the same.

## Retired indicators

These are removed from the public catalog, not deleted from the warehouse:

- `meta_dapodik_sync_rate`
- `edu_school_travel_time_p90`
- `hlt_realtime_icu_occupancy`

Reasons: Dapodik access is restricted, student home coordinates are protected by
UU PDP, and real-time ICU occupancy requires clinical SATUSEHAT/SIRS credentials.

Historical snapshots keep their `snapshot_indicators` rows. `content_sha256` of
those snapshots remains valid.

## API behavior

| Request | Historical snapshot | New snapshot |
| --- | --- | --- |
| `GET /indicators` | 33 indicators | 30 indicators |
| `GET /indicators/coverage` | 33 total, 29 available | 30 total, 29 available |
| Retired indicator values | `200` with empty values | `404` |
| Composite with retired ID | recognized historically; likely unavailable | `422` public-catalog error |
| `inf_asphalt_road_village_pct` | public, unavailable | public, unavailable |
| `GET /snapshots/{id}` | 33 / 29 | 30 / 29 |

`snapshot` and `snapshot_id` remain equivalent pinning parameters.

## Deployment requirement

The LIVE database must be on a persistent volume. Current Docker path:

```env
NM_LIVE_DATABASE_PATH=/data/nusa_matra_live.db
NM_TELEMETRY_DB_PATH=/data/telemetry.db
```

`docker-compose.yml` keeps the historical volume name `nusa-matra-telemetry:/data`
so existing Coolify volumes are reused. It now stores both the LIVE database and
telemetry. The image no longer rebuilds the LIVE database at build time.

The container entrypoint:

1. Seeds LIVE only when the database file is absent.
2. Runs `scripts/retire_public_indicators.py` (idempotent).
3. Starts Uvicorn.

### One-time migration from the existing production container

Do this **before** the first deploy that mounts the new volume, otherwise the
existing `2026.10.0-live-62354dfad392d985` snapshot is not in the new volume and
pinned Evidence Passport links will 404.

```bash
# From the host running the OLD container
docker cp <old-container>:/app/data/nusa_matra_live.db ./nusa_matra_live.db

# Put it on the new persistent volume before the new container starts
docker run --rm \
  -v <coolify-volume-name>:/data \
  -v "$PWD":/backup \
  alpine sh -c "cp /backup/nusa_matra_live.db /data/nusa_matra_live.db"
```

If Coolify already provides a volume containing the old LIVE database, verify it
contains `62354dfad392d985` before removing the old container. Starting from an
empty volume creates a new 30-indicator snapshot but cannot recover the old one.

## Maintenance commands

```bash
python scripts/seed_live_db.py
python scripts/retire_public_indicators.py
python scripts/retire_public_indicators.py   # must be a no-op
python scripts/capture_contract_samples.py  # writes docs/staging_samples/retirement
python -m pytest -q
```

`retire_public_indicators.py` copies the active snapshot's public facts into a
new staging snapshot, recomputes `meta_indicator_completeness` and
`meta_freshness_lag_years` against the public core framework, publishes a new
immutable snapshot, and leaves the old snapshot untouched.

## Rollback

To return to the old snapshot:

```sql
UPDATE data_snapshots SET is_active_default = 0 WHERE environment_tag = 'LIVE';
UPDATE data_snapshots SET is_active_default = 1
WHERE snapshot_id = '2026.10.0-live-62354dfad392d985';
```

Do not delete the new snapshot; keep it as history. Do not mutate either
snapshot's `snapshot_indicators` or facts.

## Verification

- Old snapshot digest: valid.
- New snapshot digest: valid.
- Old snapshot pin works after new publication and after process restart.
- New snapshot has 30 indicators; only `inf_asphalt_road_village_pct` is empty.
- Padangsidimpuan and Makassar remain in `insufficient_data`, never zero-filled.
- Contract samples: `docs/staging_samples/retirement/`.
