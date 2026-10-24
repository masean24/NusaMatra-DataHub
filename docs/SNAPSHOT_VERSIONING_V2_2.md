# SNAPSHOT VERSIONING v2.2 — Immutable Identity and Content Digest

**Status:** implemented, not deployed.
**Hash spec:** `canonical-json-v1`
**Snapshot ID format:** `2026.10.0-live-<first 16 hex of content_sha256>`

---

## 1. Why the old snapshot ID was not immutable

The legacy `2026.10.0-official-live` ID was a constant in `scripts/seed_live_db.py`. Rebuilding the database changed facts, indicator coverage, ranking, and timestamps while keeping the same ID. `manifest_checksum` was a constant `sha256(b"nusa_matra_official_live_2026")`, so it could not detect content changes.

The legacy row is now explicitly marked:

```json
{
  "snapshot_id": "2026.10.0-official-live",
  "is_immutable": false,
  "is_reproducible": false,
  "content_sha256": null,
  "immutability_note": "Legacy snapshot ID was reused across publications; content cannot be reconstructed."
}
```

It remains retrievable for compatibility, but Evidence Passport must not use it as a reproducibility anchor.

---

## 2. New snapshot lifecycle

1. Seeder writes to `__nusa_matra_live_staging__` (not addressable as a published ID).
2. `snapshot_indicators` is populated with frozen metadata and national statistics for the staging facts.
3. Canonical SHA-256 is computed from the staging state.
4. Final ID is derived: `2026.10.0-live-<digest[:16]>`.
5. Final `data_snapshots` row is inserted, facts and snapshot indicator rows are moved to it, staging row is deleted.
6. `is_active_default=1` is set for the new LIVE snapshot; older snapshots keep their rows and facts.
7. If the same canonical content is rebuilt, the existing snapshot ID is reused; no duplicate is created.
8. Any changed observation produces a different digest and therefore a new snapshot ID.

The seeder never deletes historical immutable snapshots. The Docker image build starts from a clean image, so history across separate image builds is not retained; the current image contains the snapshot it baked. A persistent database volume is required if historical snapshots must survive deployments.

---

## 3. What is included in `content_sha256`

The digest is SHA-256 over compact, sorted JSON:

```json
{
  "spec": "canonical-json-v1",
  "environment_tag": "LIVE",
  "boundary_version": "BIG-20260601",
  "methodology_version": "v2.2-minmax-full-range",
  "scoring": {
    "score_direction": "higher_is_need",
    "total_basis_points": 10000,
    "min_coverage_pct": 70,
    "min_components": 2,
    "presets": [{"preset_id": "...", "weights": {"...": 0}}]
  },
  "datasets": ["..."],
  "indicators": ["..."],
  "regions": ["..."],
  "reference_periods": [2023, 2024, 2025, 2026],
  "observations": ["..."]
}
```

### Included tables/fields

- `snapshot_indicators`: identity, name, category, unit, polarity, availability, dataset, derivation, description, national min/max/mean/median, observation count, reference years.
- `dim_datasets`: ID, agency, title, official portal, download/API URL, access method, license, update frequency, `raw_sha256`.
- `dim_regions`: all canonical region fields, codes, area, label point, bbox, boundary version.
- `fact_indicator_values`: region, indicator, reference year, raw value, normalized score, percentile, rank, quality flag, dataset, source record reference.
- Scoring configuration: score direction, total basis points, coverage/component gates, all preset weights.

### Excluded

- Snapshot label, notes, `created_at`, `published_at`, `is_active_default`.
- `dim_datasets.last_ingested_at` (volatile ingestion timestamp).
- `snapshot_indicators.computed_at`.
- Snapshot ID itself (to avoid circularity).

### Canonicalization rules

- JSON keys sorted; compact separators `(",", ":")`; UTF-8; `ensure_ascii=False`.
- Observations sorted by `(indicator_id, region_id, reference_year)`.
- Indicators sorted by `indicator_id`; regions by `region_id`; datasets by `dataset_id`.
- Numeric values rounded to 6 decimal places; `-0.0` normalized to `0.0`; null stays `null`.
- Floats serialized through Python's deterministic JSON representation after rounding.
- `allow_nan=False`; NaN/Infinity is a build error.

## 4. `metadata_checksum` vs `content_sha256` vs `manifest_checksum`

| Field | What it hashes | Changes when |
|---|---|---|
| `content_sha256` | observations + indicator metadata + regions + datasets + scoring config | any included observation/metadata/config changes |
| `metadata_checksum` | catalog/region/dataset/scoring metadata; excludes observations and derived distribution statistics | catalog, region, dataset, or scoring config changes |
| `manifest_checksum` | legacy field; for new snapshots it equals `metadata_checksum` | same as metadata checksum |

`manifest_checksum` must never be presented as a dataset content digest.

---

## 5. Schema additions

`data_snapshots` adds:

- `content_sha256`, `metadata_checksum`, `content_hash_spec`
- `is_immutable`, `is_reproducible`
- `methodology_version`, `reference_periods`, `source_manifest`, `supersedes`
- `observation_count`, `indicator_count`, `available_indicator_count`, `region_count`, `dataset_count`
- `immutability_note`

New table `snapshot_indicators` freezes per-snapshot indicator metadata and national statistics.

`app/database.py` runs `ensure_snapshot_schema_async` on both DEMO and LIVE databases at startup, so an existing database is upgraded in place without deleting facts.

---

## 6. API contract

### Resolve the active snapshot

```http
GET /api/v1/snapshots?mode=live
```

### Pin a snapshot (new alias)

```http
GET /api/v1/indicators/coverage?mode=live&snapshot=2026.10.0-live-62354dfad392d985
POST /api/v1/indicators/composite-query?mode=live&snapshot=2026.10.0-live-62354dfad392d985
```

`snapshot_id` remains supported with identical behavior. If both are sent with different values, the API returns `422 SNAPSHOT_PARAM_CONFLICT`.

### Snapshot detail

```http
GET /api/v1/snapshots/2026.10.0-live-62354dfad392d985?mode=live
```

Example (abridged):

```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-live-62354dfad392d985",
    "mode": "LIVE",
    "content_sha256": "62354dfad392d985168450ac670b6c647ab097e800ee023768d5858387a984b5",
    "snapshot_immutable": true,
    "snapshot_reproducible": true,
    "methodology_version": "v2.2-minmax-full-range"
  },
  "data": {
    "snapshot_id": "2026.10.0-live-62354dfad392d985",
    "content_sha256": "62354dfad392d985168450ac670b6c647ab097e800ee023768d5858387a984b5",
    "metadata_checksum": "70e9350a10cbbc32112446d20eb9b44b3d0bed8e479c8931e9216af52fad67ff",
    "content_hash_spec": "canonical-json-v1",
    "is_immutable": true,
    "is_reproducible": true,
    "indicator_completeness_pct": 87.9,
    "available_indicator_data_pct": 100.0,
    "indicator_count": 33,
    "available_indicator_count": 29,
    "observation_count": 14745,
    "region_count": 514,
    "region_coverage_pct": 100.0,
    "dataset_count": 18,
    "reference_periods": [2023, 2024, 2025, 2026],
    "supersedes": "2026.10.0-official-live"
  }
}
```

Response headers on pinned data requests:

- `X-NusaMatra-Snapshot`
- `X-NusaMatra-Content-SHA256`
- `X-NusaMatra-Snapshot-Immutable`
- `X-NusaMatra-Snapshot-Reproducible`

### Errors

| Status | Code | Meaning |
|---:|---|---|
| 404 | `SNAPSHOT_NOT_FOUND` | explicit snapshot does not exist; no fallback to latest |
| 422 | `SNAPSHOT_MODE_MISMATCH` | snapshot exists in the other environment |
| 422 | `SNAPSHOT_PARAM_CONFLICT` | `snapshot` and `snapshot_id` disagree |

---

## 7. Reproducibility verification

Local:

```bash
python scripts/seed_live_db.py
python -m pytest -q
```

The seeder prints `content_sha256` and `metadata_checksum`; running it twice with unchanged inputs must reuse the same snapshot ID. `app/services/snapshot_integrity.py::verify_content_digest` recomputes the digest and compares it to the stored value.

Post-deploy checklist (do not claim success before these pass):

1. `GET /api/v1/snapshots?mode=live` shows one active immutable snapshot with non-null `content_sha256`.
2. `GET /api/v1/snapshots/{id}?mode=live` returns `is_immutable=true`, `is_reproducible=true`.
3. The `X-NusaMatra-Content-SHA256` header matches the snapshot detail.
4. `GET /api/v1/indicators/coverage?mode=live&snapshot={id}` returns 29/33 and `meta.indicator_coverage`.
5. `GET /api/v1/indicators/inf_safe_water_pct/values?...&snapshot={id}` returns `9507` raw 32.89, norm 78.89, flag `IMPUTED_PROVINCE`.
6. Requesting `?snapshot=does-not-exist` returns 404.
7. The legacy `2026.10.0-official-live` is marked unreproducible.

---

## 8. Migration

1. Back up the current LIVE database if it is on a persistent volume.
2. Deploy the new image. At startup, `ensure_snapshot_schema_async` adds columns/table to DEMO and LIVE databases.
3. Run `python scripts/seed_live_db.py` if the image build did not already run it. The seeder:
   - preserves existing snapshots;
   - rebuilds only the staging snapshot;
   - finalizes a digest-addressed snapshot;
   - marks legacy LIVE rows without `content_sha256` as unreproducible.
4. The API auto-selects `is_active_default=1` for `mode=live`; `NM_LIVE_SNAPSHOT_ID` is only a fallback.
5. Run the post-deploy checklist.

## 9. Rollback

Code rollback:

1. Redeploy the previous image/tag. The schema additions are backward-compatible; old code ignores the new columns.
2. If the previous image used a persistent database, it still has the legacy snapshot and facts. The new snapshot rows are extra and harmless.
3. If the new image used a fresh database, rollback restores the previous image's baked database.

Data rollback:

- Do not delete or rewrite the immutable snapshot row. To roll back serving, set `is_active_default=0` on the new snapshot and `=1` on the previous recoverable snapshot. If the previous snapshot is legacy/unreproducible, do not present it as Evidence Passport-compatible.
