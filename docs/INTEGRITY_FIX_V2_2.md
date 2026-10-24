# INTEGRITY FIX v2.2 — Normalization, Coverage, and Composite Contract

**Status:** implementasi selesai di working tree; **belum di-push/deploy dan belum diverifikasi di production**.
**Test suite:** 134 passed.
**Snapshot lokal yang dihasilkan:** `2026.10.0-live-62354dfad392d985` (content SHA-256 `62354dfad392d985168450ac670b6c647ab097e800ee023768d5858387a984b5`).

---

## 1. P0-A — Lanny Jaya (`9507`) normalization

### Root cause

`inf_safe_water_pct` sebelumnya di-seed dalam **dua batch**:

1. Batch master provinsi: seluruh 514 kab/kota diberi nilai `inf_safe_water_prov_pct` dan dinormalisasi memakai min/max batch itu.
2. Batch VERIFIED kab/kota: 513 kab/kota dari BPS WebAPI var 2830 dinormalisasi ulang.

Batch kedua memakai `INSERT OR REPLACE` tanpa menghapus baris batch pertama. Lanny Jaya tidak memiliki nilai air minum di CSV VERIFIED (BPS var 2830 memang kosong untuk `9507`), sehingga baris lamanya tertinggal:

- raw `32.89` dari BPS Susenas 2025 provinsi (legacy BPS `9700`, **PAPUA PEGUNUNGAN**)
- normalized `100.0` dari min/max **batch pertama**
- `dim_indicators.national_min/max` kemudian ditimpa batch kedua (`14.93 / 100.0`)

Akibatnya satu baris memakai bounds lama sementara metadata indikator memakai bounds baru. Ini juga membuat rank air minum tidak konsisten: `9507` dan `9508` sama-sama rank 1 dari dua batch berbeda, sedangkan `9505` rank 2.

### Fix

- Logika normalisasi dipindahkan ke `app/services/normalization_service.py` (`v2.2-minmax-full-range`).
- Setiap indikator sekarang **menghapus baris snapshot lama** lalu menormalisasi **satu himpunan kanonik** sekali:
  - VERIFIED kab/kota jika tersedia;
  - fallback province-level **hanya** untuk air minum, dengan flag `IMPUTED_PROVINCE`;
  - dataset fallback: `bps_provincial_sdgs_2025`;
  - `source_record_ref`: `BPS Susenas 2025 Provinsi PAPUA PEGUNUNGAN (legacy BPS 9700)`.
- Tidak ada nilai nol yang disisipkan untuk data hilang; region tanpa nilai tetap tanpa observasi.
- Seeder menjalankan audit normalisasi pada seluruh observasi dan berhenti jika ada mismatch > 0.02.

### Before / after

| Field | Production before | Local after fix |
|---|---:|---:|
| `raw_value` | 32.89 | 32.89 |
| `normalized_score` | **100.0** | **78.89** |
| `national_rank` (indikator air) | 1 | 7 |
| `quality_flag` | `IMPUTED_PROVINCE` | `IMPUTED_PROVINCE` |
| `dataset_id` | `bps_susenas_sakernas_2025` | `bps_provincial_sdgs_2025` |
| provenance | `BPS Susenas Prov 2025` | `BPS Susenas 2025 Provinsi PAPUA PEGUNUNGAN (legacy BPS 9700)` |

Expected score from the documented min-max transform:
`(1 - (32.89 - 14.93) / (100.00 - 14.93)) × 100 = 78.89`.

Nearby observations remain monotonic (`31.88 → 80.08`, `32.97 → 78.79`, `14.93 → 100.0`).

### Audit

- 14.745 observasi LIVE diaudit ulang terhadap bounds tersimpan.
- **0 mismatch** di atas toleransi 0.02.
- **0 duplikat** `(region_id, indicator_id)`.
- `VERIFIED`, `DERIVED`, dan `IMPUTED_PROVINCE` semuanya terwakili.
- Seeder gagal keras jika audit menemukan mismatch atau pelanggaran foreign key.

### Composite impact

Scenario `kemiskinan_stunting` (`soc_poverty_rate 3000`, `hlt_stunting_prevalence 3000`, `inf_safe_water_pct 2000`, `inf_safe_sanitation_pct 2000`):

| Region | Before production | After (local) |
|---|---:|---:|
| Nduga `9508` | 88.98 (rank 1) | 88.98 (rank 1) |
| Lanny Jaya `9507` | **84.40 (rank 2)** | **80.18 (rank 3)** |
| Tolikara `9504` | 80.27 (rank 3) | 80.27 (rank 2) |
| Mamberamo Tengah `9505` | 79.49 (rank 4) | 79.49 (rank 4) |

Only `kemiskinan_stunting` and custom scenarios containing `inf_safe_water_pct` are affected. The other three bundled presets do not weight water. Production numbers above are **pre-deploy**; the after-fix values are locally reproduced and must be re-checked after deployment.

### Education audit (P0-C)

`edu_damaged_classrooms_pct` and `edu_student_teacher_ratio_sd` remain `VERIFIED` because the source workbooks are genuine **kab/kota** XLSX from Kemendikdasmen Pusdatin, **TA 2022/2023**:

- `edu_student_teacher_ratio_sd`: direct official student/teacher ratio per kab/kota.
- `edu_damaged_classrooms_pct`: `(rusak sedang + rusak berat) / total ruang kelas × 100`, SD + SMP.
- 514/514 rows resolved by name + level + province crosswalk; SHA-256 raw files and derived CSV are in `data/kemendikdasmen_edu_kabkota_2023.provenance.json`.
- Dataset ID is historically named `kemendikdasmen_statistik_2026`; the dataset title and `reference_year` correctly say **TA 2022/2023**. The ID is retained for contract compatibility.

Health indicators:

- `hlt_facilities_per_10k`: VERIFIED kab/kota (Puskesmas Semester II 2025 + SIRS hospitals / BPS population 2026).
- `hlt_doctors_per_10k`: `IMPUTED_PROVINCE`; SATUSEHAT only publishes province-level doctor counts, so the same province rate is assigned to each kab/kota and flagged honestly.

---

## 2. P0-C — Coverage definitions

One field now has one meaning:

| Field | Meaning |
|---|---|
| `indicator_count` / `total_indicators` | Size of the published framework: **33** |
| `available_indicator_count` | Indicators with at least one observation in the snapshot: **29** |
| `indicator_completeness_pct` | `available / framework × 100` = **87.9** |
| `available_indicator_data_pct` | Available indicators with data / indicators marked available in this snapshot = **100.0** |
| `region_count` | Kab/kota with at least one observation: **514** |
| `region_coverage_pct` | `region_count / 514 × 100` = **100.0** |
| `meta.coverage.available` | Region coverage only; for `/indicators/coverage` this is **514/514** |
| `meta.indicator_coverage` | Explicit `{total_indicators, available_indicators, unavailable_indicators, indicator_completeness_pct, available_indicator_data_pct}` |

Previously `indicator_completeness_pct` was `29 / 29 = 100` because the denominator was "indicators not marked UNAVAILABLE". That was mathematically true but easy to misread as 33/33. It is now `29 / 33 = 87.9`.

---

## 3. P1 — Composite contract hardening

`POST /api/v1/indicators/composite-query` now enforces the same rankability rule as presets:

- `national_coverage_pct = sum(requested weights with national observations) / 100`
- `rankable = national_coverage_pct >= NM_COMPOSITE_MIN_COVERAGE_PCT`
  and `available_components >= NM_COMPOSITE_MIN_COMPONENTS`
- `required_components = min(NM_COMPOSITE_MIN_COMPONENTS, number_of_requested_indicators)`

If not rankable, the response is still HTTP 200 but contains **no rankings**:

```json
{
  "rankable": false,
  "not_rankable_reason": "national weight coverage 50.0% is below the 70% threshold; only 1 of the required 2 components have national observations",
  "national_coverage_pct": 50.0,
  "available_weight_basis_points": 5000,
  "regions": [],
  "total_regions": 0,
  "insufficient_data": []
}
```

Per-region `coverage_pct` is computed against the **original requested weights**, not the globally renormalized weights. A region is excluded when its original-weight coverage is below 70% or it has fewer than the required components. `effective_weights_region` still sums to 10,000 bp for every eligible region.

`rank` remains the position in the filtered province list; `national_rank` remains the position before province filtering. `score_direction` remains `"higher_is_need"`.

---

## 4. Files changed

- `scripts/seed_live_db.py`
- `app/services/normalization_service.py` (new)
- `app/services/snapshot_integrity.py` (new)
- `app/services/snapshot_registry.py` (new)
- `app/services/snapshot_service.py`
- `app/services/indicator_service.py`
- `app/services/region_service.py`
- `app/services/composite_service.py`
- `app/middleware/mode_selector.py`
- `app/database.py`
- `app/main.py`
- `app/models/common.py`
- `app/models/health.py`
- `app/models/indicators.py`
- `app/routers/indicators.py`
- `app/routers/regions.py`
- `app/routers/snapshots.py`
- `app/routers/health.py`
- `migrations/001_init_schema.sql`
- `data/seed_db.py`
- tests: `test_normalization_integrity.py`, `test_snapshot_integrity.py`, `test_live_data_integrity.py`, `test_composite.py`, `test_boundaries_and_meta.py`

---

## 5. Test results

```
134 passed in 10.21s
```

Coverage includes:

- Lanny Jaya regression and monotonic polarity for VERIFIED/DERIVED/IMPUTED_PROVINCE;
- all 14.745 LIVE observations checked against frozen bounds;
- composite recalculation (Lanny Jaya 80.18, rank 3);
- immutable snapshot digest stability and mutation sensitivity;
- two distinct snapshots with pinned data;
- unknown snapshot 404 and `snapshot` / `snapshot_id` alias;
- metadata/coverage consistency;
- rankable and non-rankable composite scenarios.

---

## 6. Deployment and rollback

See `docs/SNAPSHOT_VERSIONING_V2_2.md` sections **Migration** and **Rollback**. Do not deploy until the new image passes the full suite and the post-deploy checklist is run against the actual production endpoints.
