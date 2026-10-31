# v2.4 Fixtures

Generated from commit `ce49cdf` plus the percentile-direction patch in the
working tree, using the local LIVE snapshot
`2026.10.0-live-0de6ac68f0d55b3a`.

Production smoke test already passed on `https://api.orangkeren.me` for the
base v2.4 changes: `422` envelope, `WEIGHT_VALIDATION_ERROR`, `404 NOT_FOUND`,
`meta.boundary_version`, and `is_active_default`.

`production_smoke.json` was captured before the percentile-direction patch.
After that patch is deployed, `meta.score_direction` and per-indicator
`polarity` will also appear in production.

Each JSON file is:

```json
{
  "http_status": 422,
  "body": {}
}
```

| File | Request | Expected |
|---|---|---|
| `error_validation_query.json` | `GET /regions?level=invalid` | `422`, `VALIDATION_ERROR`, `detail` string |
| `error_validation_weight.json` | `POST /composite-query` with weight sum 8000 | `422`, `WEIGHT_VALIDATION_ERROR`, message contains `10000` |
| `error_not_found.json` | `GET /indicators/does_not_exist/values` | `404`, `NOT_FOUND` |
| `error_rate_limited.json` | second `GET /regions` after burst exhausted | `429`, `RATE_LIMITED`, `Retry-After` |
| `meta_values.json` | `GET /indicators/soc_poverty_rate/values?mode=live` | `200`, `meta.boundary_version`, `meta.content_sha256` |
| `meta_region_detail.json` | `GET /regions/1101?mode=live` | `200`, `meta.score_direction`, per-indicator `polarity` |
| `meta_coverage.json` | `GET /indicators/coverage?mode=live` | `200`, 30 indicators, 29 available, `meta.boundary_version` |
| `meta_datasets.json` | `GET /datasets?mode=live` | `200`, `meta.boundary_version`, `meta.content_sha256` |
| `meta_snapshots.json` | `GET /snapshots?mode=live` | `200`, active item has `is_active_default: true` |
| `meta_composite.json` | `POST /composite-query` valid weights | `200`, `meta.boundary_version`, `data.rankable` |

Expected error shape:

```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed.",
  "detail": "query.level: String should match pattern ..."
}
```

`detail` is a string. Weight errors use the same shape with
`code: "WEIGHT_VALIDATION_ERROR"`.

`national_percentile` is a need percentile. `meta.score_direction` is
`higher_is_need`, and each region-detail indicator carries `polarity`. Do not
interpret a high percentile as a high raw value without checking polarity.

`error_rate_limited.json` was captured locally with enforcement on
(`rate_limit_report_only=false`). Production is still `report_only=true`.
Before enforcement, the frontend must render `message` and `Retry-After`.
The relevant headers are `Retry-After`, `X-RateLimit-Limit`,
`X-RateLimit-Remaining`, `X-RateLimit-Reset`, `X-RateLimit-Bucket`, and
`X-RateLimit-Exceeded`.
