# Nusa Matra Data Hub — Gemini Research Handoff

This is a **documentation/research package**, not an implemented backend and not a verified LIVE data feed.

## Files

1. `DATASET_CATALOG.md` — Gemini-proposed official sources and candidate datasets.
2. `INDICATOR_MAPPING.csv` — actual CSV converted from Gemini's `2_indicator_mapping.md`: 33 indicators, 12 columns, UTF-8 BOM for easy Excel opening. One malformed unquoted note repaired without changing its claims.
3. `GEOGRAPHY_AND_REGION_CODES.md` — regional codes and map boundary plan.
4. `DATA_SOURCE_VERIFICATION.md` — Gemini claims about portal/access availability.
5. `DATA_HUB_ARCHITECTURE.md` — proposed infrastructure and SQL.
6. `API_CONTRACT_DRAFT.md` — proposed endpoints and sample payloads.
7. `IMPLEMENTATION_ROADMAP.md` — Gemini's proposed phased implementation timeline.
8. `REVIEW_AND_BLOCKERS.md` — independent audit and mandatory corrections before agent implementation.

Start by reading `REVIEW_AND_BLOCKERS.md`; do not blindly mark catalogue sources as production-verified. The sample API payloads are illustrative, not sourced LIVE measurements. The frontend app is maintained separately.
