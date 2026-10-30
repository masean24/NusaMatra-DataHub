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
    education_datasets = con.execute(
        "SELECT COUNT(*) FROM dim_datasets WHERE dataset_id IN "
        "('kemendikdasmen_npd_2025', 'kemendikdasmen_statistik_2025')"
    ).fetchone()[0]
    education_counts = dict(
        con.execute(
            "SELECT indicator_id, COUNT(*) FROM fact_indicator_values "
            "WHERE snapshot_id = ? AND indicator_id IN "
            "('edu_student_teacher_ratio_sd', 'edu_damaged_classrooms_pct') "
            "AND raw_value IS NOT NULL GROUP BY indicator_id",
            (snapshot_id,),
        ).fetchall()
    )
    ipm_dataset = con.execute(
        "SELECT 1 FROM dim_datasets WHERE dataset_id = 'bps_ipm_2025'"
    ).fetchone()
    ipm_counts = dict(
        con.execute(
            "SELECT indicator_id, COUNT(*) FROM fact_indicator_values "
            "WHERE snapshot_id = ? AND indicator_id IN "
            "('soc_hdi', 'hlt_life_expectancy') "
            "AND raw_value IS NOT NULL GROUP BY indicator_id",
            (snapshot_id,),
        ).fetchall()
    )
    affected_dataset = con.execute(
        "SELECT 1 FROM dim_datasets WHERE dataset_id = 'bnpb_dibi_affected_2025'"
    ).fetchone()
    affected_count = con.execute(
        "SELECT COUNT(*) FROM fact_indicator_values "
        "WHERE snapshot_id = ? AND indicator_id = 'dis_affected_pop_per_10k' "
        "AND raw_value IS NOT NULL",
        (snapshot_id,),
    ).fetchone()[0]
    ready = (
        has_dataset
        and stunting_count == 514
        and education_datasets == 2
        and education_counts.get("edu_student_teacher_ratio_sd") == 514
        and education_counts.get("edu_damaged_classrooms_pct") == 514
        and ipm_dataset
        and ipm_counts.get("soc_hdi") == 514
        and ipm_counts.get("hlt_life_expectancy") == 514
        and affected_dataset
        and affected_count == 514
    )
    sys.exit(0 if ready else 1)
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
    echo "[entrypoint] LIVE database missing current SSGI 2024 / education 2025 / IPM 2025 / DIBI 2025 data; seeding $LIVE_DB"
    python scripts/seed_live_db.py
else
    echo "[entrypoint] LIVE snapshot already has SSGI 2024, education 2025, IPM/UHH 2025, and DIBI 2025 impact."
fi

echo "[entrypoint] Applying public indicator retirement..."
python scripts/retire_public_indicators.py

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
