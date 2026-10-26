"""
Public indicator visibility policy.

Some indicators cannot be published because the underlying government source is
restricted (PII, clinical credentials, or WAF-protected portals). They remain in
the warehouse for audit/history but are retired from the public catalog.

Snapshot immutability note: retiring an indicator must never delete rows from an
already published ``snapshot_indicators`` table. The digest of historical
snapshots covers those rows.
"""

from __future__ import annotations

RETIRED_PUBLIC_INDICATORS: dict[str, str] = {
    "meta_dapodik_sync_rate": (
        "Portal Dapodik dibatasi untuk operator/dinas; data operasional tidak "
        "tersedia sebagai API publik."
    ),
    "edu_school_travel_time_p90": (
        "Waktu tempuh rumah-sekolah membutuhkan koordinat rumah siswa yang "
        "dilindungi UU PDP dan tidak dipublikasikan."
    ),
    "hlt_realtime_icu_occupancy": (
        "Keterisian ICU real-time memerlukan kredensial fasilitas kesehatan "
        "SATUSEHAT/SIRS dan tidak tersedia untuk konsumsi publik."
    ),
}


def is_retired_indicator(indicator_id: str) -> bool:
    return indicator_id in RETIRED_PUBLIC_INDICATORS


def retirement_reason(indicator_id: str) -> str | None:
    return RETIRED_PUBLIC_INDICATORS.get(indicator_id)
