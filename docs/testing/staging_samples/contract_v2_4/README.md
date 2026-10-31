# v2.4 Contract Samples

Source: local LIVE database (`nusa_matra_live.db`) built from the current working tree.
These are contract samples, not a production deployment claim.
Active LIVE snapshot: `2026.10.0-live-0de6ac68f0d55b3a`.

## Error envelope

Every 422 and HTTP error now uses:

```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed.",
  "detail": "query.level: String should match pattern ..."
}
```

Weight validation uses `code: "WEIGHT_VALIDATION_ERROR"` with the same envelope.
`detail` is a readable string. The previous `{"detail": [...]}` shape is gone.

## Boundary metadata

`meta.boundary_version` is populated for snapshot-backed endpoints, including
`/indicators/coverage`, `/indicators/{id}/values`, `/datasets`,
`/snapshots`, `/regions`, `/boundaries/*`, and `/composite-query`.

## Percentile direction

Every response includes `meta.score_direction = "higher_is_need"`. Region detail
items also include `polarity` (`positive` or `negative`). `national_percentile`
is a need percentile: higher means greater need, regardless of raw-value
polarity.

## Snapshot active marker

`GET /snapshots` exposes the active marker as `data[].is_active_default`.
