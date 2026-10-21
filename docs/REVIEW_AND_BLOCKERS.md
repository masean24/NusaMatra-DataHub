# Nusa Matra Data Hub — Review & Blockers (20 Oktober 2026)

**Status: RESEARCH DRAFT / NOT PRODUCTION VERIFIED.**

This package preserves Gemini's six Markdown research/design documents. The original `2_indicator_mapping.md` was reconstructed as `INDICATOR_MAPPING.csv` (33 indicators, 12 columns). One comma-bearing note on source line 2 needed proper CSV quoting; its wording is preserved, including inaccuracies listed below. It has **not** been silently corrected.

## MUST FIX before backend implementation or LIVE mode

1. **CRITICAL — LIVE MUST NOT fall back to DEMO.** `DATA_HUB_ARCHITECTURE.md` currently explicitly proposes falling back to DEMO when a LIVE query fails. Never do this. A LIVE request must fail closed with an explicit unavailable/stale-live response, or return a *previously verified LIVE snapshot clearly identified as such*; never substitute simulated data. Correct `X-NusaMatra-Mode`, snapshot metadata, cache headers and all examples accordingly.
2. **CRITICAL — Source verification is not complete at the dataset/resource level.** The Gemini table uses blanket labels such as “TERVERIFIKASI AKTIF”, “DIRECT”, “2025”, and open-license assertions. A working portal does **not** establish that a particular dataset has 514 district rows, a stable URL, permission to reproduce, or the claimed latest year. For each MVP indicator, obtain exact dataset IDs, resource/download URLs, a representative response/file, schema, dates, permitted reuse, and coverage evidence. Mark others UNVERIFIED / PLANNED until validated.
3. **CRITICAL — IRBI 2025 classification incorrect in indicator CSV.** Gemini wrote “Low <13, Medium 13–144, High >144”. BNPB's *Buku IRBI 2025*, page 35, defines aggregated IRBI 2025 classification as Low <14.67; Medium 14.67–176.00; High >176.00. These thresholds are edition-specific and should not be applied to 2024 or other indicators without inspecting the relevant methodology. Source: https://inarisk.bnpb.go.id/IRBI-2025/files/basic-html/page35.html . Preserve the raw CSV note until the data steward explicitly approves a correction.
4. **HIGH — API contract uses fractional weights** (`0.35`, `0.25`, etc.) while the approved Nusa Matra frontend MVP represents persisted weighting as integer *basis points summing to 10,000*. Decide ONE canonical wire type, ideally integer basis points, document sum validation, adapt UI percentages, and update samples before wiring frontend to backend.
5. **HIGH — API contract must be diffed against frontend `docs/08-API-SPECIFICATION.md`.** That document was not included in the Gemini batch. The declaration of compatibility is a claim, not a test. Confirm routes, request/response field names, timestamps, error envelopes, model version, region IDs and demo/live state.
6. **HIGH — SQL `fact_indicator_values` primary key omits `reference_year`.** Current `(snapshot_id, region_id, indicator_id)` permits one observation per indicator within each snapshot. If multi-year historical observations are required, add `reference_year` (and any relevant measurement or source dimensions) to key and document whether snapshots contain latest-only values or time series.
7. **HIGH — Exact region code bridging must be validated row by row.** Do not invent or infer BPS ↔ Kemendagri ↔ education codes from matching place names. Import dated official crosswalk with provenance; handle district splits, BPS domain namespaces and historical versioning. Official BPS relationship UI: https://sig.bps.go.id/bridging-kode/ .
8. **HIGH — TopoJSON GeoJSON contract mismatch.** Backend defaults to TopoJSON while the provided 3D renderer's `GeographyDataset` consumes validated GeoJSON Polygon/MultiPolygon. Add versioned TopoJSON→GeoJSON adapter or negotiate `?format=geojson`; include tests for holes, multi-island administrative regions, shared boundaries, simplification, and identifiers.
9. **MEDIUM — Sample values and availability must be labeled as examples.** Numbers in `API_CONTRACT_DRAFT.md` (priority scores, poverty percentages, ranks, coordinates, etc.) are mock examples and not evidence of official measurements. Mark `EXAMPLE / DEMO` and avoid `VERIFIED` as a fixture flag unless a source record supports it.
10. **MEDIUM — Scope and performance assumptions**: the 12-day roadmap, 1.8 MB TopoJSON target, 50 ms p95 target, and 95% data threshold are project targets, not measured results. Start with a smaller source-verified pilot, then expand. Review SQL constraints/types, missing indicators, and null handling before freezing snapshots.

## Partially confirmed via independent official sources

- BPS WebAPI developer portal exists and describes statistics tables & API: https://webapi.bps.go.id/developer — availability of **individual requested indicators at the stated geographic/year detail is not yet proven**.
- SIG-BPS has an official code relationship interface: https://sig.bps.go.id/bridging-kode/ .
- BNPB's raster ImageServer `INDEKS_BAHAYA_BANJIR` exists and reports a 100-unit pixel size in its native projected CRS: https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_BAHAYA_BANJIR/ImageServer — this does not establish year or permission for bulk extraction.
- BNPB CKAN documentation exposes a DataStore API interface: https://data.bnpb.go.id/api/1/util/snippet/api_info.html?resource_id=faeb2406-b800-4b8e-9e09-37d4b2aa5879 — specific IRBI resource still needs verification.
- Kemendikdasmen official data portal lists its release schedule: https://data.kemendikdasmen.go.id/ — requested row-level indicator files need checking.

## Acceptance gates for the next backend agent

- [ ] Investigate and patch 1–10 above with documented decisions.
- [ ] Verify one real dataset each for BPS and BNPB (exact resource, schema, year, region code, license).
- [ ] Obtain and test geography dataset and code crosswalk before showing LIVE joins.
- [ ] Agree API contract with `docs/08-API-SPECIFICATION.md` and 3D map input types.
- [ ] Produce a local deterministic DEMO fixture with unmissable DEMO labeling.
- [ ] Generate working code, migration tests, adapter tests, and endpoint contract tests.
- [ ] Fail closed for unavailable LIVE data and report actual verification results.
