#!/bin/sh
set -eu

LIVE_DB="${NM_LIVE_DATABASE_PATH:-/app/data/nusa_matra_live.db}"
export NM_LIVE_DATABASE_PATH="$LIVE_DB"
mkdir -p "$(dirname "$LIVE_DB")"

needs_seed() {
    if [ ! -s "$LIVE_DB" ]; then
        return 0
    fi

    python - "$LIVE_DB" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
try:
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT snapshot_id FROM data_snapshots "
        "WHERE environment_tag = 'LIVE' AND is_active_default = 1 LIMIT 1"
    ).fetchone()
    if not row:
        sys.exit(1)
    snapshot_id = row[0]
    has_dataset = con.execute(
        "SELECT 1 FROM dim_datasets WHERE dataset_id = 'kemenkes_ssgi_2024'"
    ).fetchone()
    stunting_count = con.execute(
        "SELECT COUNT(*) FROM fact_indicator_values "
        "WHERE snapshot_id = ? AND indicator_id = 'hlt_stunting_prevalence' "
        "AND raw_value IS NOT NULL",
        (snapshot_id,),
    ).fetchone()[0]
    sys.exit(0 if has_dataset and stunting_count == 514 else 1)
except Exception:
    sys.exit(1)
finally:
    try:
        con.close()
    except Exception:
        pass
PY
}

if needs_seed; then
    echo "[entrypoint] LIVE database missing or not on SSGI 2024; seeding $LIVE_DB"
    python scripts/seed_live_db.py
else
    echo "[entrypoint] LIVE snapshot already has SSGI 2024 stunting."
fi

echo "[entrypoint] Applying public indicator retirement..."
python scripts/retire_public_indicators.py

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
