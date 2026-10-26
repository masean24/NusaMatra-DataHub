#!/bin/sh
set -eu

LIVE_DB="${NM_LIVE_DATABASE_PATH:-/app/data/nusa_matra_live.db}"
export NM_LIVE_DATABASE_PATH="$LIVE_DB"
mkdir -p "$(dirname "$LIVE_DB")"

if [ ! -s "$LIVE_DB" ]; then
    echo "[entrypoint] LIVE database not found; seeding $LIVE_DB"
    python scripts/seed_live_db.py
fi

echo "[entrypoint] Applying public indicator retirement..."
python scripts/retire_public_indicators.py

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
