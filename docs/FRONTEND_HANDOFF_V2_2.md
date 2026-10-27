# FRONTEND HANDOFF v2.2 — Integrity, Snapshot Pinning, and Composite Gates

Backend v2.2 keeps the v2.1 field names used by the frontend. The changes below are additive except where noted.

> **v2.3 retirement note:** `meta_dapodik_sync_rate`, `edu_school_travel_time_p90`, and `hlt_realtime_icu_occupancy` are removed from the public catalog. New snapshot: 30 indicators / 29 available; historical snapshots remain 33 / 29 and remain pin-able. See `docs/INDICATOR_RETIREMENT_V2_3.md` and `docs/staging_samples/retirement/`.
>
> **v2.4 contract note:** all validation errors now use the shared `{status, code, message, detail}` envelope, and `meta.boundary_version` is populated from the selected snapshot. See `docs/FRONTEND_HANDOFF_V2_4.md` and `docs/staging_samples/contract_v2_4/`.

---

## 1. Stop hardcoding the LIVE snapshot ID

The old `2026.10.0-official-live` ID was reused for different data and is now marked **unreproducible**.

Resolve the active snapshot at runtime:

```http
GET /api/v1/snapshots?mode=live
```

Use the item with `is_active_default: true` and `is_reproducible: true`. Cache the ID for the session; do not assume the old constant.

### Pin a snapshot

Both forms are supported and equivalent:

```http
GET /api/v1/indicators/coverage?mode=live&snapshot=<snapshot_id>
GET /api/v1/indicators/coverage?mode=live&snapshot_id=<snapshot_id>
```

Sending two different values returns `422 SNAPSHOT_PARAM_CONFLICT`.

Unknown snapshot returns `404 SNAPSHOT_NOT_FOUND`; the backend never silently falls back to latest.

---

## 2. New snapshot metadata

Every response `meta` may now include:

```json
{
  "boundary_version": "BIG-20260601",
  "content_sha256": "62354dfad392d985...",
  "snapshot_immutable": true,
  "snapshot_reproducible": true,
  "methodology_version": "v2.2-minmax-full-range"
}
```

Headers:

- `X-NusaMatra-Content-SHA256`
- `X-NusaMatra-Snapshot-Immutable`
- `X-NusaMatra-Snapshot-Reproducible`

`GET /api/v1/snapshots/{snapshot_id}?mode=live` returns the full metadata, including `metadata_checksum`, `content_hash_spec`, `observation_count`, `indicator_count`, `available_indicator_count`, `region_count`, `dataset_count`, `reference_periods`, `source_manifest`, and `supersedes`.

`manifest_checksum` is retained for compatibility but is **not** the content digest. Use `content_sha256` for Evidence Passport.

---

## 3. Coverage field semantics

`GET /api/v1/indicators/coverage` now separates indicator coverage from region coverage:

```json
{
  "total_indicators": 33,
  "available_indicators_count": 29,
  "empty_indicators_count": 4,
  "indicator_completeness_pct": 87.9,
  "available_indicator_data_pct": 100.0,
  "total_regions": 514,
  "region_coverage_pct": 100.0
}
```

`meta.coverage.available` now means **regions with observations** (514), not indicators. Indicator counts are in `meta.indicator_coverage`:

```json
"indicator_coverage": {
  "total_indicators": 33,
  "available_indicators": 29,
  "unavailable_indicators": 4,
  "indicator_completeness_pct": 87.9,
  "available_indicator_data_pct": 100.0
}
```

If the UI previously rendered `meta.coverage.available` as "29 indikator", change it to read `meta.indicator_coverage.available_indicators`.

`indicator_completeness_pct = 87.9` means 29/33 framework indicators have data. `available_indicator_data_pct = 100.0` means all 29 indicators marked available in this snapshot have data.

---

## 4. Composite query: handle non-rankable scenarios

`POST /api/v1/indicators/composite-query` now enforces backend rankability. A non-rankable scenario returns HTTP 200 with an explicit payload and **empty rankings**:

```json
{
  "rankable": false,
  "not_rankable_reason": "national weight coverage 50.0% is below the 70% threshold; only 1 of the required 2 components have national observations",
  "national_coverage_pct": 50.0,
  "available_weight_basis_points": 5000,
  "available_indicators": ["dis_multihazard_index"],
  "unavailable_indicators": ["edu_school_travel_time_p90"],
  "regions": [],
  "total_regions": 0,
  "insufficient_data": []
}
```

Required UI behavior:

1. Check `data.rankable` before rendering a ranking.
2. If false, show `not_rankable_reason` and do not render rank 1 or a map layer.
3. `rank` remains province-filtered position; `national_rank` remains national position.
4. `coverage_pct` is now computed against the **original requested weights**. A region below 70% original-weight coverage or below `min_components` goes to `insufficient_data`.
5. `effective_weights_region` still sums to 10.000 bp for eligible regions.
6. `score_direction` is still `"higher_is_need"`.

Preset objects still expose `availability.rankable`; the rules are now identical for presets and custom queries.

---

## 5. Lanny Jaya correction

`inf_safe_water_pct` / `9507`:

- raw `32.89`
- normalized `78.89` (was `100.0`)
- flag `IMPUTED_PROVINCE`
- `dataset_id`: `bps_provincial_sdgs_2025`
- `source_record_ref`: `BPS Susenas 2025 Provinsi PAPUA PEGUNUNGAN (legacy BPS 9700)`

`values_by_region` now also exposes `dataset_id` and `source_record_ref` per region, so Evidence Passport can show the exact observation-level provenance instead of only the indicator-level catalog source.

Scenario `kemiskinan_stunting`: Lanny Jaya composite is now **80.18** instead of 84.40. Locally it moves from rank 2 to rank 3. Re-check after production deployment; do not assume the old rank.

Evidence Passport should display the new provenance and flag, not the old `bps_susenas_sakernas_2025` source.

---

## 6. Backward compatibility

Preserved:

- `snapshot_id` query parameter.
- Response envelope `status/meta/data`.
- `manifest_checksum`, `indicator_completeness_pct`, `coverage`, composite fields, and preset fields.
- DEMO snapshot ID `2026.10.0-wia-demo`.

Changed values/semantics to update:

- `indicator_completeness_pct` for DEMO is now `93.9` (31/33), not `100.0`.
- `meta.coverage.available` for `/indicators/coverage` is now region count `514`, not indicator count `29`.
- Non-rankable composite queries return no regions instead of fabricated renormalized rankings.

New:

- `snapshot` alias.
- snapshot detail endpoint.
- digest/immutability metadata and headers.
- `rankable`, `not_rankable_reason`, `national_coverage_pct`, `available_weight_basis_points`, `available_indicators` on composite results.

---

## 7. Suggested frontend flow

1. On boot: `GET /snapshots?mode=live`, pick `is_active_default`.
2. Store `snapshot_id` and `content_sha256`.
3. All Evidence Passport requests include `snapshot=<id>`.
4. Compare the returned `meta.content_sha256`/header with the stored value; if different, invalidate the passport cache.
5. Before rendering a composite, require `data.rankable === true`.
6. For coverage widgets, use `meta.indicator_coverage` for indicators and `meta.coverage` for regions.
