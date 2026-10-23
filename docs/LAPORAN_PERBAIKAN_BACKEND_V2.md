# Laporan Perbaikan Backend v2.1 — Nusa Matra Data Hub

**Untuk:** Tim Frontend / penanggung jawab Lab Prioritas LIVE  
**Dari:** Backend Nusa Matra Data Hub  
**Tanggal:** 23 Oktober 2026  
**Snapshot:** `2026.10.0-official-live`  
**Status:** 112/112 test lulus · 25 indikator berdata · 12.689 observasi · 514/514 kab/kota

---

## Ringkasan

Tiga blocker yang dilaporkan sudah diperbaiki:

1. **Missing per wilayah tidak lagi dihitung nol.** Wilayah dengan data parsial di-reweight; wilayah dengan cakupan terlalu rendah dikeluarkan ke `insufficient_data`.
2. **Arah skor diseragamkan.** `score_direction: "higher_is_need"` di DEMO dan LIVE. Skor 100 = paling rentan/paling butuh intervensi; rank 1 = paling prioritas.
3. **Data LIVE dibersihkan.** Crosswalk wilayah diperbaiki: 514/514 kab/kota, tidak ada lagi kota yang menerima nilai kabupatennya, dan `national_rank` maksimum 514.

Contoh respons di dokumen ini dihasilkan dari kode v2.1 dengan snapshot LIVE yang sama yang akan dipakai produksi setelah redeploy. Angka tidak dikarang dan setiap sumber data punya manifest provenance + SHA-256.

---

## 1. Missing data per wilayah

### Perilaku lama
- Ketersediaan indikator dicek **nasional**, bukan per wilayah.
- Jika indikator tersedia nasional tetapi kosong di suatu kab/kota, komponen itu tidak masuk perhitungan **dan bobotnya tidak dinormalisasi ulang** — kontribusinya otomatis nol.
- Semua wilayah yang punya minimal satu baris tetap diranking.

### Perilaku v2.1
- `coverage_pct` per wilayah = bobot yang punya observasi ÷ 10.000 × 100%.
- Wilayah dengan **coverage ≥ 70% dan minimal 2 komponen** tetap diranking. Bobot komponen yang ada diskalakan ulang ke 10.000 bps di `effective_weights_region`.
- Wilayah di bawah ambang **tidak diranking**; masuk `insufficient_data` beserta komponen yang tersedia dan `reason`.
- Missing **tidak pernah** dihitung nol dengan bobot penuh.

Ambang dapat diubah lewat environment:
- `NM_COMPOSITE_MIN_COVERAGE_PCT` (default `70`)
- `NM_COMPOSITE_MIN_COMPONENTS` (default `2`)

### Bukti pada data LIVE

| Wilayah | Rank lama | Skor lama | Perilaku v2.1 |
|---|---:|---:|---|
| Kota Surakarta | 28/31 | 62.04 | coverage 70%, bobot `4286/2857/2857`, **rank 35/35**, skor 9.57 |
| Kota Padangsidimpuan | 33/33 | 33.04 | coverage 33.3% → **excluded**, masuk `insufficient_data` |

Catatan penting: angka lama Surakarta tidak bisa dibandingkan langsung karena arah skor LIVE lama terbalik (skor tinggi = kondisi baik). Setelah arah diperbaiki, Surakarta memang wilayah dengan kebutuhan rendah pada komponen yang tersedia. Yang berubah secara metodologis adalah: **missing tidak lagi dianggap nol**, dan wilayah dengan 1 komponen tidak bisa melonjak ke ranking atas.

Contoh respons Surakarta:

```json
{
  "region_id": "3372",
  "region_name": "Kota Surakarta",
  "composite_score": 9.57,
  "rank": 35,
  "national_rank": 487,
  "coverage_pct": 70.0,
  "components_used": ["inf_safe_sanitation_pct", "inf_safe_water_pct", "soc_poverty_rate"],
  "missing_indicators": ["hlt_stunting_prevalence"],
  "effective_weights_region": {
    "inf_safe_sanitation_pct": 2857,
    "inf_safe_water_pct": 2857,
    "soc_poverty_rate": 4286
  },
  "component_scores": {
    "soc_poverty_rate": 14.24,
    "hlt_stunting_prevalence": null,
    "inf_safe_water_pct": 0.0,
    "inf_safe_sanitation_pct": 12.13
  },
  "quality_flags": {
    "inf_safe_sanitation_pct": "VERIFIED",
    "inf_safe_water_pct": "VERIFIED",
    "soc_poverty_rate": "VERIFIED"
  }
}
```

Contoh wilayah yang dikeluarkan:

```json
{
  "region_id": "1277",
  "region_name": "Kota Padangsidimpuan",
  "coverage_pct": 33.3,
  "components_used": ["inf_electrification_pct"],
  "missing_indicators": ["dis_multihazard_index", "dis_flood_hazard_idx", "inf_asphalt_road_village_pct"],
  "component_scores": {
    "dis_multihazard_index": null,
    "dis_flood_hazard_idx": null,
    "inf_asphalt_road_village_pct": null,
    "inf_electrification_pct": 0.9
  },
  "reason": "COVERAGE_BELOW_THRESHOLD"
}
```

---

## 2. Validitas dan arah ranking

### Arah skor
Kanonik v2.1:

```json
"score_direction": "higher_is_need"
```

- `normalized_score` 100 = paling rentan / paling butuh intervensi.
- `composite_score` 100 = paling prioritas.
- Rank 1 = wilayah paling prioritas.
- Berlaku sama di DEMO dan LIVE.

Verifikasi korelasi `raw_value` vs `normalized_score`:

| Indikator | DEMO | LIVE | Arti |
|---|---:|---:|---|
| `soc_poverty_rate` (negatif) | +1.000 | +1.000 | kemiskinan tinggi → skor tinggi |
| `soc_hdi` (positif) | −1.000 | −1.000 | HDI tinggi → skor rendah |

### Rank dan populasi eligible
- `national_rank` = posisi se-Indonesia, dihitung sebelum filter provinsi.
- `rank` = posisi di dalam hasil filter yang dikembalikan.
- `total_eligible_national` = jumlah wilayah yang lolos gate secara nasional.
- `total_excluded` = jumlah wilayah yang dikeluarkan **di dalam hasil filter**.
- `total_regions` = jumlah wilayah yang diranking dan dikembalikan.

Pada query Jawa Tengah: `total_regions = 35`, `total_eligible_national = 513`, `total_excluded = 0`.

### Tie
Skor yang sama mendapat rank yang sama (competition ranking: 1, 1, 3), dengan urutan deterministik berdasarkan `region_id`. Frontend tidak perlu melakukan sort ulang berdasarkan skor yang ditampilkan.

---

## 3. Contoh perhitungan dokumentasi

Dengan komponen `72.1`, `61.5`, `70.3` dan bobot efektif `43.75%`, `31.25%`, `25%`:

```text
72.1 × 0.4375 = 31.54375
61.5 × 0.3125 = 19.21875
70.3 × 0.2500 = 17.57500
------------------------------
Total         = 68.33750 → 68.34
```

Angka **68.42** pada dokumen v2 lama **salah**. Tidak ada presisi internal yang dapat menghasilkan 68.42 dari komponen tersebut. Dokumentasi sudah diperbaiki dan diberi golden test (`test_documented_math_is_68_34`).

Contoh lama juga memakai `region_id: "3201"` (Kabupaten Bogor) yang di LIVE tidak memiliki observasi, sehingga tidak mungkin muncul di ranking. Contoh sudah diganti dengan respons nyata Surakarta/Wonosobo.

---

## 4. Kontrak preset

`GET /api/v1/indicators/composite-presets?mode=live` mengembalikan `data` sebagai **array langsung** (bukan `{ "presets": [...] }`). Setiap preset kini punya `availability`.

Contoh aktual (preset pertama):

```json
{
  "preset_id": "bencana_infrastruktur",
  "title": "Mitigasi Bencana & Ketahanan Infrastruktur",
  "category": "disaster_and_infrastructure",
  "description": "Menyorot kabupaten/kota rawan multi-bencana (IRBI & banjir) yang memerlukan penguatan infrastruktur jalan dan elektrifikasi.",
  "target_focus": "Infrastruktur dan Mitigasi Bencana",
  "weights": {
    "dis_multihazard_index": 3500,
    "dis_flood_hazard_idx": 1500,
    "inf_asphalt_road_village_pct": 2500,
    "inf_electrification_pct": 2500
  },
  "availability": {
    "available_indicators": ["dis_multihazard_index", "dis_flood_hazard_idx", "inf_electrification_pct"],
    "unavailable_indicators": ["inf_asphalt_road_village_pct"],
    "indicator_coverage_pct": {
      "dis_multihazard_index": 99.4,
      "dis_flood_hazard_idx": 77.0,
      "inf_asphalt_road_village_pct": 0.0,
      "inf_electrification_pct": 100.0
    },
    "effective_weights": {
      "dis_multihazard_index": 4667,
      "dis_flood_hazard_idx": 2000,
      "inf_electrification_pct": 3333
    },
    "coverage_weight_pct": 75.0,
    "rankable": true
  }
}
```

Status keempat preset di LIVE:

| Preset | Coverage bobot | Rankable | Catatan |
|---|---:|---|---|
| `bencana_infrastruktur` | 75.0% | ✅ | `inf_asphalt_road_village_pct` belum tersedia |
| `kemiskinan_stunting` | 100.0% | ✅ | stunting 94.7%, sanitasi 99.8% |
| `pendidikan_daerah_3t` | 45.0% | ❌ | baru mean years + internet; damaged classrooms & student-teacher ratio belum tersedia |
| `indeks_pembangunan_terpadu` | 100.0% | ✅ | semua komponen tersedia |

**Frontend wajib membaca `rankable`** sebelum menampilkan preset sebagai skenario ranking.

---

## 5. Contoh respons composite-query

### Skenario A — data parsial (LIVE, Jawa Tengah)

Request:

```json
{
  "weights": {
    "soc_poverty_rate": 3000,
    "hlt_stunting_prevalence": 3000,
    "inf_safe_water_pct": 2000,
    "inf_safe_sanitation_pct": 2000
  },
  "filter_province_id": "33"
}
```

Respons aktual (diringkas ke dua wilayah):

```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "total_count": 35
  },
  "data": {
    "total_regions": 35,
    "total_eligible_national": 513,
    "total_excluded": 0,
    "score_direction": "higher_is_need",
    "min_coverage_pct": 70,
    "min_components": 2,
    "weights_basis_points": {
      "soc_poverty_rate": 3000,
      "hlt_stunting_prevalence": 3000,
      "inf_safe_water_pct": 2000,
      "inf_safe_sanitation_pct": 2000
    },
    "unavailable_indicators": [],
    "effective_weights": {
      "soc_poverty_rate": 3000,
      "hlt_stunting_prevalence": 3000,
      "inf_safe_water_pct": 2000,
      "inf_safe_sanitation_pct": 2000
    },
    "renormalized": false,
    "regions": [
      {
        "region_id": "3307",
        "region_name": "Kabupaten Wonosobo",
        "composite_score": 35.06,
        "rank": 1,
        "national_rank": 80,
        "coverage_pct": 100.0,
        "components_used": [
          "hlt_stunting_prevalence",
          "inf_safe_sanitation_pct",
          "inf_safe_water_pct",
          "soc_poverty_rate"
        ],
        "missing_indicators": [],
        "effective_weights_region": {
          "hlt_stunting_prevalence": 3000,
          "inf_safe_sanitation_pct": 2000,
          "inf_safe_water_pct": 2000,
          "soc_poverty_rate": 3000
        },
        "component_scores": {
          "soc_poverty_rate": 28.14,
          "hlt_stunting_prevalence": 56.79,
          "inf_safe_water_pct": 10.06,
          "inf_safe_sanitation_pct": 37.85
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3372",
        "region_name": "Kota Surakarta",
        "composite_score": 9.57,
        "rank": 35,
        "national_rank": 487,
        "coverage_pct": 70.0,
        "components_used": [
          "inf_safe_sanitation_pct",
          "inf_safe_water_pct",
          "soc_poverty_rate"
        ],
        "missing_indicators": ["hlt_stunting_prevalence"],
        "effective_weights_region": {
          "inf_safe_sanitation_pct": 2857,
          "inf_safe_water_pct": 2857,
          "soc_poverty_rate": 4286
        },
        "component_scores": {
          "soc_poverty_rate": 14.24,
          "hlt_stunting_prevalence": null,
          "inf_safe_water_pct": 0.0,
          "inf_safe_sanitation_pct": 12.13
        },
        "quality_flags": {
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      }
    ],
    "insufficient_data": []
  }
}
```

Catatan: `hlt_stunting_prevalence` **tidak ada sebagai key** di `component_scores` lama; sekarang key-nya ada dengan nilai `null`, dan `missing_indicators` menyebutkannya. Frontend bisa memakai `components_used` / `missing_indicators` tanpa menebak.

### Skenario B — wilayah dikeluarkan (LIVE, Sumatera Utara)

```json
{
  "total_regions": 32,
  "total_eligible_national": 511,
  "total_excluded": 1,
  "unavailable_indicators": ["inf_asphalt_road_village_pct"],
  "effective_weights": {
    "dis_multihazard_index": 4667,
    "dis_flood_hazard_idx": 2000,
    "inf_electrification_pct": 3333
  },
  "renormalized": true,
  "insufficient_data": [
    {
      "region_id": "1277",
      "region_name": "Kota Padangsidimpuan",
      "coverage_pct": 33.3,
      "components_used": ["inf_electrification_pct"],
      "missing_indicators": ["dis_multihazard_index", "dis_flood_hazard_idx", "inf_asphalt_road_village_pct"],
      "component_scores": {
        "dis_multihazard_index": null,
        "dis_flood_hazard_idx": null,
        "inf_asphalt_road_village_pct": null,
        "inf_electrification_pct": 0.9
      },
      "reason": "COVERAGE_BELOW_THRESHOLD"
    }
  ]
}
```

Padangsidimpuan **tidak** diberi rank dan tidak bisa melonjak ke peringkat 1 seperti pada perilaku lama.

---

## 6. Perbaikan integritas data LIVE

### Crosswalk wilayah
- Modul baru `app/services/crosswalk_service.py` memetakan data berdasarkan **nama + level + prefix provinsi**, bukan `bps_code` saja.
- Alasan: kode BPS lama bertabrakan dengan kode Kemendagri 2026. Contoh: CSV `9501` = Merauke, sedangkan kode 2026 `9501` = Jayawijaya.
- Hasil: **514/514 wilayah tercakup**, 0 unmatched, 0 ambiguous.
- 26 wilayah memiliki beberapa vintage data; nilainya digabung per indikator, bukan saling menimpa.

### Kontaminasi kota kembar
- `3201` Kabupaten Bogor: HDI **72.39**, kemiskinan **6.26**.
- `3271` Kota Bogor: HDI **78.52**, kemiskinan **5.89** (sebelumnya menerima nilai Kabupaten).
- `national_rank` maksimum sekarang **514** (sebelumnya 538).

### Flag kualitas
Setiap komponen membawa `quality_flags`:

| Flag | Arti |
|---|---|
| `VERIFIED` | Nilai resmi pada granularitas kab/kota |
| `DERIVED` | Dihitung dari data resmi (mis. rasio ketergantungan, audit internal) |
| `IMPUTED_PROVINCE` | Nilai resmi provinsi yang diimputasi ke kab/kota; **bukan** angka kab/kota |
| `DEMO_EXAMPLE` | Hanya di mode DEMO |

Saat ini yang berstatus `IMPUTED_PROVINCE`: `inf_electrification_pct`, `inf_internet_household_pct`, `hlt_jkn_coverage_pct`, `dis_affected_pop_per_10k`, dan 1 wilayah fallback untuk `inf_safe_water_pct`.

---

## 7. Cakupan data saat ini

**25 indikator berdata · 12.689 observasi · 514/514 kab/kota**

| Indikator | Wilayah | Flag |
|---|---:|---|
| `dis_affected_pop_per_10k` | 514 | IMPUTED_PROVINCE |
| `dis_earthquake_hazard_idx` | 510 | VERIFIED |
| `dis_events_5yr_freq` | 510 | VERIFIED |
| `dis_flood_hazard_idx` | 396 | VERIFIED |
| `dis_landslide_hazard_idx` | 510 | VERIFIED |
| `dis_multihazard_index` | 511 | VERIFIED |
| `edu_expected_years_schooling` | 514 | VERIFIED |
| `edu_mean_years_schooling` | 514 | VERIFIED |
| `edu_net_enrollment_sma` | 514 | VERIFIED |
| `edu_net_enrollment_smp` | 514 | VERIFIED |
| `hlt_jkn_coverage_pct` | 514 | IMPUTED_PROVINCE |
| `hlt_life_expectancy` | 514 | VERIFIED |
| `hlt_stunting_prevalence` | 487 | VERIFIED |
| `inf_electrification_pct` | 514 | IMPUTED_PROVINCE |
| `inf_internet_household_pct` | 514 | IMPUTED_PROVINCE |
| `inf_safe_sanitation_pct` | 513 | VERIFIED |
| `inf_safe_water_pct` | 514 | 513 VERIFIED + 1 IMPUTED_PROVINCE |
| `meta_freshness_lag_years` | 514 | DERIVED |
| `meta_indicator_completeness` | 514 | DERIVED |
| `soc_dependency_ratio` | 514 | DERIVED |
| `soc_expenditure_per_capita` | 514 | VERIFIED |
| `soc_hdi` | 514 | VERIFIED |
| `soc_poverty_rate` | 514 | VERIFIED |
| `soc_poverty_severity_p2` | 514 | VERIFIED |
| `soc_unemployment_rate` | 514 | VERIFIED |

### 8 indikator yang belum berdata

**By design (tidak tersedia publik):**
- `edu_school_travel_time_p90`
- `hlt_realtime_icu_occupancy`

**Terblokir akses/granularitas:**
- `edu_student_teacher_ratio_sd`
- `edu_damaged_classrooms_pct`
- `meta_dapodik_sync_rate`
- `hlt_facilities_per_10k`
- `hlt_doctors_per_10k`
- `inf_asphalt_road_village_pct`

Alasan: portal Dapodik resmi dilindungi WAF (mirror non-`.go.id` tidak dipakai); Kemenkes/SATUSEHAT baru menyediakan agregat provinsi/dashboard; publikasi Podes nasional hanya sampai provinsi. Nilai-nilai ini **tidak** diisi tebakan.

### Sumber dan provenance
- BPS WebAPI: air minum & sanitasi kab/kota (var 2830 & 2748), proyeksi penduduk (var 2790), internet (var 398), JKN (var 2279).
- Kemendikdasmen Pusdatin: APK/APM 2024/2025 (PDF resmi).
- BNPB DIBI: kejadian 2020–2024 per kabupaten, korban terdampak/mengungsi 2024.
- BIG: batas wilayah 2026.
- BMKG: gempa real-time.

Setiap dataset punya file `*.provenance.json` berisi URL resmi, SHA-256 raw, dan SHA-256 CSV turunan.

---

## 8. Verifikasi

```bash
python -m pytest -q
# 112 passed

python scripts/seed_live_db.py
# 12,689 fact rows, 25 indicators, 514/514 regions, max rank 514
```

Setelah deploy, cek:

```bash
curl "https://api.orangkeren.me/api/v1/indicators/coverage?mode=live"
curl "https://api.orangkeren.me/api/v1/indicators/composite-presets?mode=live"
curl -X POST "https://api.orangkeren.me/api/v1/indicators/composite-query?mode=live" \
  -H "Content-Type: application/json" \
  -d '{"weights":{"soc_poverty_rate":3000,"hlt_stunting_prevalence":3000,"inf_safe_water_pct":2000,"inf_safe_sanitation_pct":2000},"filter_province_id":"33"}'
```

Yang harus terlihat:
- `score_direction: "higher_is_need"`
- `min_coverage_pct: 70`, `min_components: 2`
- `total_eligible_national: 513` untuk skenario kemiskinan
- Surakarta `coverage_pct: 70.0`, `missing_indicators: ["hlt_stunting_prevalence"]`
- `insufficient_data` berisi Padangsidimpuan pada skenario bencana Sumut

---

## 9. Catatan implementasi untuk frontend

1. **Jangan menganggap rank 1 = kondisi terbaik.** Rank 1 = kebutuhan intervensi tertinggi.
2. **Gunakan `rank` dan `national_rank` secara terpisah.** Filter provinsi tidak mengubah `national_rank`.
3. **Tampilkan badge `coverage_pct`** dan `missing_indicators`. Jangan render wilayah parsial sebagai data lengkap.
4. **Tampilkan `insufficient_data` sebagai panel “data belum cukup”**, bukan sebagai ranking bernilai rendah.
5. **Baca `quality_flags`.** Jika Anda ingin ranking hanya dari data kab/kota, filter `IMPUTED_PROVINCE`.
6. **Cek `availability.rankable` pada preset** sebelum menjalankan preset sebagai skenario ranking.
7. **Jangan mengandalkan key komponen selalu ada.** Gunakan `components_used` / `missing_indicators`; nilai yang tidak tersedia sekarang muncul sebagai `null`.
8. **Tie policy:** skor sama = rank sama; jangan sort ulang berdasarkan skor yang ditampilkan.

---

## 10. Ringkasan perubahan file

- `app/services/crosswalk_service.py` — crosswalk deterministik nama+level+provinsi.
- `app/services/composite_service.py` — coverage gate, per-region weights, national rank, ties, preset availability.
- `app/models/indicators.py` — field baru: `coverage_pct`, `components_used`, `missing_indicators`, `effective_weights_region`, `quality_flags`, `national_rank`, `insufficient_data`, `score_direction`.
- `app/routers/indicators.py` — preset availability + perbaikan metadata coverage.
- `scripts/seed_live_db.py` — crosswalk, semantik kanonik, sumber data baru, audit quarantine.
- `scripts/fetch_bps_sdgs_kabkota.py` — penarikan ulang air minum & sanitasi kab/kota.
- `data/*.csv` + `data/*.provenance.json` — data turunan resmi + checksum.
- `tests/` — 110 test, termasuk crosswalk, eligibility, arah skor, integritas LIVE, dan BMKG deterministik.
- `docs/PANDUAN_INTEGRASI_FRONTEND_PRODUKSI.md`, `README.md`, `SESSION_HANDOFF.md` — dokumentasi diperbarui.

---

**Kesimpulan:** ranking LIVE sudah valid secara metodologis dan siap dipakai setelah redeploy. Yang tersisa adalah 6 indikator yang memang belum punya sumber kab/kota yang dapat diakses; dua indikator lain memang tidak tersedia publik.
