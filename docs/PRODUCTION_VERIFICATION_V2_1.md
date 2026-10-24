# Verifikasi Production v2.1 (historis) — Nusa Matra Data Hub

**Base URL:** `https://api.orangkeren.me`  
**Snapshot:** `2026.10.0-official-live`  
**Waktu verifikasi:** 23 Oktober 2026  
**Status historis:** LIVE v2.1, 25 indikator, 12.689 observasi, 514/514 wilayah

> **Update v2.2 (23 Oktober 2026):** snapshot LIVE kini memuat **29 indikator / 14.745 observasi**. Empat indikator baru: `edu_student_teacher_ratio_sd`, `edu_damaged_classrooms_pct`, `hlt_facilities_per_10k` (VERIFIED), dan `hlt_doctors_per_10k` (`IMPUTED_PROVINCE`). Angka 25/12.689 di bawah adalah sampel historis v2.1; gunakan `docs/LAPORAN_PERBAIKAN_BACKEND_V2.md` untuk cakupan terbaru.
>
> **Update integritas v2.2 (24 Oktober 2026):** dokumen ini **bukan** verifikasi production untuk perbaikan normalisasi/snapshot/composite terbaru. Lihat `docs/INTEGRITY_FIX_V2_2.md`, `docs/SNAPSHOT_VERSIONING_V2_2.md`, dan `docs/FRONTEND_HANDOFF_V2_2.md`. Jangan klaim production terverifikasi sampai endpoint production benar-benar dicek ulang.

---

## 1. Apakah v2.1 sudah redeploy?

Ya. Health check production menunjukkan database LIVE dengan **12.689 fact rows**, **33 indikator katalog**, dan **514 kab/kota**. Response composite sudah memakai kontrak v2.1 (`score_direction`, `coverage_pct`, `effective_weights_region`, `quality_flags`, `insufficient_data`).

Catatan kecil: field `version` di `/health` masih `0.1.0` karena `app_version` belum dinaikkan. Ini hanya label; perilaku endpoint sudah v2.1. Kalau perlu, kita bump ke `2.1.0` pada deploy berikutnya.

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "mode": "LIVE",
  "active_snapshot": "2026.10.0-official-live",
  "database": {
    "status": "connected",
    "tables": {
      "dim_regions": 552,
      "dim_indicators": 33,
      "fact_indicator_values": 12689,
      "data_snapshots": 1
    },
    "detail": null
  },
  "redis": "not_configured",
  "static_fallback_ready": true
}
```

## 2. Contoh respons JSON production

### 2a. `GET /api/v1/indicators/coverage?mode=live`

```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "boundary_version": null,
    "total_count": 33,
    "coverage": {
      "available": 25,
      "total_regions": 514,
      "missing_region_ids": [],
      "mode": "LIVE"
    },
    "data_origin": null,
    "last_success_at": null,
    "is_stale": null
  },
  "data": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "total_indicators": 33,
    "available_indicators_count": 25,
    "empty_indicators_count": 8,
    "empty_indicators": [
      "meta_dapodik_sync_rate",
      "edu_damaged_classrooms_pct",
      "edu_school_travel_time_p90",
      "edu_student_teacher_ratio_sd",
      "hlt_doctors_per_10k",
      "hlt_facilities_per_10k",
      "hlt_realtime_icu_occupancy",
      "inf_asphalt_road_village_pct"
    ],
    "indicators": {
      "meta_dapodik_sync_rate": {
        "name": "Persentase Pengiriman Data Sinkronisasi Dapodik",
        "category": "data_reliability",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "meta_freshness_lag_years": {
        "name": "Rata-rata Usia Data Indikator (Freshness Lag)",
        "category": "data_reliability",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "meta_indicator_completeness": {
        "name": "Skor Kelengkapan Indikator Wilayah (Data Completeness)",
        "category": "data_reliability",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "dis_affected_pop_per_10k": {
        "name": "Penduduk Terdampak & Mengungsi per 10.000 Jiwa",
        "category": "disaster_risk",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "dis_earthquake_hazard_idx": {
        "name": "Indeks Bahaya Gempabumi (Rata-rata Wilayah)",
        "category": "disaster_risk",
        "available": true,
        "coverage_count": 510,
        "coverage_pct": 99.2
      },
      "dis_events_5yr_freq": {
        "name": "Frekuensi Kejadian Bencana (Akumulasi 5 Tahun)",
        "category": "disaster_risk",
        "available": true,
        "coverage_count": 510,
        "coverage_pct": 99.2
      },
      "dis_flood_hazard_idx": {
        "name": "Indeks Bahaya Banjir (Rata-rata Wilayah)",
        "category": "disaster_risk",
        "available": true,
        "coverage_count": 396,
        "coverage_pct": 77.0
      },
      "dis_landslide_hazard_idx": {
        "name": "Indeks Bahaya Tanah Longsor (Rata-rata Wilayah)",
        "category": "disaster_risk",
        "available": true,
        "coverage_count": 510,
        "coverage_pct": 99.2
      },
      "dis_multihazard_index": {
        "name": "Indeks Risiko Bencana Indonesia (IRBI) Multi-Bencana",
        "category": "disaster_risk",
        "available": true,
        "coverage_count": 511,
        "coverage_pct": 99.4
      },
      "edu_damaged_classrooms_pct": {
        "name": "Persentase Ruang Kelas Rusak Sedang/Berat (SD & SMP)",
        "category": "education_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "edu_expected_years_schooling": {
        "name": "Harapan Lama Sekolah (HLS / EYS)",
        "category": "education_access",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "edu_mean_years_schooling": {
        "name": "Rata-rata Lama Sekolah (RLS / MYS)",
        "category": "education_access",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "edu_net_enrollment_sma": {
        "name": "Angka Partisipasi Murni (APM) SMA/SMK/MA",
        "category": "education_access",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "edu_net_enrollment_smp": {
        "name": "Angka Partisipasi Murni (APM) SMP/MTs",
        "category": "education_access",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "edu_school_travel_time_p90": {
        "name": "Waktu Tempuh Riil Rumah-Sekolah Persentil ke-90",
        "category": "education_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "edu_student_teacher_ratio_sd": {
        "name": "Rasio Murid terhadap Guru Jenjang SD",
        "category": "education_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "hlt_doctors_per_10k": {
        "name": "Rasio Dokter per 10.000 Penduduk",
        "category": "healthcare_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "hlt_facilities_per_10k": {
        "name": "Rasio Rumah Sakit & Puskesmas per 10.000 Penduduk",
        "category": "healthcare_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "hlt_jkn_coverage_pct": {
        "name": "Cakupan Kepesertaan Jaminan Kesehatan (JKN/BPJS)",
        "category": "healthcare_access",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "hlt_life_expectancy": {
        "name": "Umur Harapan Hidup Saat Lahir (UHH)",
        "category": "healthcare_access",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "hlt_realtime_icu_occupancy": {
        "name": "Tingkat Keterisian Tempat Tidur ICU Rumah Sakit Real-Time",
        "category": "healthcare_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "hlt_stunting_prevalence": {
        "name": "Prevalensi Balita Stunting",
        "category": "healthcare_access",
        "available": true,
        "coverage_count": 487,
        "coverage_pct": 94.7
      },
      "inf_asphalt_road_village_pct": {
        "name": "Persentase Desa dengan Jalan Utama Aspal/Beton Dapat Dilalui Sepanjang Tahun",
        "category": "infrastructure",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      },
      "inf_electrification_pct": {
        "name": "Persentase Rumah Tangga Pengguna Listrik (PLN & Non-PLN)",
        "category": "infrastructure",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "inf_internet_household_pct": {
        "name": "Persentase Rumah Tangga Mengakses Internet",
        "category": "infrastructure",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "inf_safe_sanitation_pct": {
        "name": "Persentase Rumah Tangga Akses Sanitasi Layak",
        "category": "infrastructure",
        "available": true,
        "coverage_count": 513,
        "coverage_pct": 99.8
      },
      "inf_safe_water_pct": {
        "name": "Persentase Rumah Tangga Akses Air Minum Layak",
        "category": "infrastructure",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "soc_dependency_ratio": {
        "name": "Rasio Ketergantungan (Dependency Ratio)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "soc_expenditure_per_capita": {
        "name": "Pengeluaran per Kapita Disesuaikan",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "soc_hdi": {
        "name": "Indeks Pembangunan Manusia (IPM / HDI)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "soc_poverty_rate": {
        "name": "Persentase Penduduk Miskin (P0)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "soc_poverty_severity_p2": {
        "name": "Indeks Keparahan Kemiskinan (P2)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "soc_unemployment_rate": {
        "name": "Tingkat Pengangguran Terbuka (TPT)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      }
    }
  }
}
```

Ringkasan: `available_indicators_count = 25`, `empty_indicators_count = 8`, `meta.coverage.available = 25`, `total_regions = 514`.

### 2b. `GET /api/v1/indicators/composite-presets?mode=live`

```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "boundary_version": null,
    "total_count": 4,
    "coverage": null,
    "data_origin": null,
    "last_success_at": null,
    "is_stale": null
  },
  "data": [
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
        "available_indicators": [
          "dis_multihazard_index",
          "dis_flood_hazard_idx",
          "inf_electrification_pct"
        ],
        "unavailable_indicators": [
          "inf_asphalt_road_village_pct"
        ],
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
    },
    {
      "preset_id": "kemiskinan_stunting",
      "title": "Pengentasan Kemiskinan Ekstrem & Stunting",
      "category": "social_and_health",
      "description": "Fokus pada wilayah prioritas intervensi penanganan stunting balita, kemiskinan (P0), serta penyediaan air minum dan sanitasi layak.",
      "target_focus": "Sosial, Kesehatan, dan Sanitasi",
      "weights": {
        "soc_poverty_rate": 3000,
        "hlt_stunting_prevalence": 3000,
        "inf_safe_water_pct": 2000,
        "inf_safe_sanitation_pct": 2000
      },
      "availability": {
        "available_indicators": [
          "soc_poverty_rate",
          "hlt_stunting_prevalence",
          "inf_safe_water_pct",
          "inf_safe_sanitation_pct"
        ],
        "unavailable_indicators": [],
        "indicator_coverage_pct": {
          "soc_poverty_rate": 100.0,
          "hlt_stunting_prevalence": 94.7,
          "inf_safe_water_pct": 100.0,
          "inf_safe_sanitation_pct": 99.8
        },
        "effective_weights": {
          "soc_poverty_rate": 3000,
          "hlt_stunting_prevalence": 3000,
          "inf_safe_water_pct": 2000,
          "inf_safe_sanitation_pct": 2000
        },
        "coverage_weight_pct": 100.0,
        "rankable": true
      }
    },
    {
      "preset_id": "pendidikan_daerah_3t",
      "title": "Pemerataan Kualitas Pendidikan Daerah 3T",
      "category": "education_access",
      "description": "Identifikasi daerah tertinggal dengan kerusakan ruang kelas tinggi, rasio murid-guru belum ideal, dan keterbatasan akses internet.",
      "target_focus": "Fasilitas dan Akses Pendidikan",
      "weights": {
        "edu_damaged_classrooms_pct": 3000,
        "edu_mean_years_schooling": 2500,
        "edu_student_teacher_ratio_sd": 2500,
        "inf_internet_household_pct": 2000
      },
      "availability": {
        "available_indicators": [
          "edu_mean_years_schooling",
          "inf_internet_household_pct"
        ],
        "unavailable_indicators": [
          "edu_damaged_classrooms_pct",
          "edu_student_teacher_ratio_sd"
        ],
        "indicator_coverage_pct": {
          "edu_damaged_classrooms_pct": 0.0,
          "edu_mean_years_schooling": 100.0,
          "edu_student_teacher_ratio_sd": 0.0,
          "inf_internet_household_pct": 100.0
        },
        "effective_weights": {
          "edu_mean_years_schooling": 5556,
          "inf_internet_household_pct": 4444
        },
        "coverage_weight_pct": 45.0,
        "rankable": false
      }
    },
    {
      "preset_id": "indeks_pembangunan_terpadu",
      "title": "Prioritas Pembangunan Komprehensif Nasional",
      "category": "balanced_development",
      "description": "Penilaian menyeluruh lintas 4 pilar: IPM/HDI, harapan lama sekolah, usia harapan hidup, dan ketahanan risiko multi-bencana.",
      "target_focus": "Pembangunan Manusia dan Wilayah Holistik",
      "weights": {
        "soc_hdi": 2500,
        "dis_multihazard_index": 2500,
        "edu_expected_years_schooling": 2500,
        "hlt_life_expectancy": 2500
      },
      "availability": {
        "available_indicators": [
          "soc_hdi",
          "dis_multihazard_index",
          "edu_expected_years_schooling",
          "hlt_life_expectancy"
        ],
        "unavailable_indicators": [],
        "indicator_coverage_pct": {
          "soc_hdi": 100.0,
          "dis_multihazard_index": 99.4,
          "edu_expected_years_schooling": 100.0,
          "hlt_life_expectancy": 100.0
        },
        "effective_weights": {
          "soc_hdi": 2500,
          "dis_multihazard_index": 2500,
          "edu_expected_years_schooling": 2500,
          "hlt_life_expectancy": 2500
        },
        "coverage_weight_pct": 100.0,
        "rankable": true
      }
    }
  ]
}
```

Ringkasan `rankable`: bencana `true` (75%), kemiskinan `true` (100%), pendidikan `false` (45%), pembangunan terpadu `true` (100%).

### 2c. `POST /api/v1/indicators/composite-query?mode=live` — Jawa Tengah

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

Respons production lengkap:

```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "boundary_version": null,
    "total_count": 35,
    "coverage": null,
    "data_origin": null,
    "last_success_at": null,
    "is_stale": null
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
        "region_id": "3304",
        "region_name": "Kabupaten Banjarnegara",
        "composite_score": 31.7,
        "rank": 2,
        "national_rank": 118,
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
          "soc_poverty_rate": 27.99,
          "hlt_stunting_prevalence": 37.65,
          "inf_safe_water_pct": 11.95,
          "inf_safe_sanitation_pct": 48.1
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3303",
        "region_name": "Kabupaten Purbalingga",
        "composite_score": 29.47,
        "rank": 3,
        "national_rank": 150,
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
          "soc_poverty_rate": 26.19,
          "hlt_stunting_prevalence": 50.21,
          "inf_safe_water_pct": 10.23,
          "inf_safe_sanitation_pct": 22.52
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3325",
        "region_name": "Kabupaten Batang",
        "composite_score": 25.24,
        "rank": 4,
        "national_rank": 208,
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
          "soc_poverty_rate": 14.49,
          "hlt_stunting_prevalence": 47.53,
          "inf_safe_water_pct": 1.2,
          "inf_safe_sanitation_pct": 31.98
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3329",
        "region_name": "Kabupaten Brebes",
        "composite_score": 25.03,
        "rank": 5,
        "national_rank": 215,
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
          "soc_poverty_rate": 30.13,
          "hlt_stunting_prevalence": 41.15,
          "inf_safe_water_pct": 1.93,
          "inf_safe_sanitation_pct": 16.31
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3326",
        "region_name": "Kabupaten Pekalongan",
        "composite_score": 24.57,
        "rank": 6,
        "national_rank": 230,
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
          "soc_poverty_rate": 15.13,
          "hlt_stunting_prevalence": 54.73,
          "inf_safe_water_pct": 1.63,
          "inf_safe_sanitation_pct": 16.43
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3305",
        "region_name": "Kabupaten Kebumen",
        "composite_score": 24.53,
        "rank": 7,
        "national_rank": 232,
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
          "soc_poverty_rate": 28.73,
          "hlt_stunting_prevalence": 41.77,
          "inf_safe_water_pct": 10.87,
          "inf_safe_sanitation_pct": 6.03
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3323",
        "region_name": "Kabupaten Temanggung",
        "composite_score": 24.23,
        "rank": 8,
        "national_rank": 239,
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
          "soc_poverty_rate": 14.46,
          "hlt_stunting_prevalence": 48.35,
          "inf_safe_water_pct": 1.62,
          "inf_safe_sanitation_pct": 25.31
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3302",
        "region_name": "Kabupaten Banyumas",
        "composite_score": 23.72,
        "rank": 9,
        "national_rank": 252,
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
          "soc_poverty_rate": 22.75,
          "hlt_stunting_prevalence": 39.71,
          "inf_safe_water_pct": 10.45,
          "inf_safe_sanitation_pct": 14.45
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3306",
        "region_name": "Kabupaten Purworejo",
        "composite_score": 22.67,
        "rank": 10,
        "national_rank": 266,
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
          "soc_poverty_rate": 20.07,
          "hlt_stunting_prevalence": 39.09,
          "inf_safe_water_pct": 11.74,
          "inf_safe_sanitation_pct": 12.86
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3315",
        "region_name": "Kabupaten Grobogan",
        "composite_score": 22.38,
        "rank": 11,
        "national_rank": 272,
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
          "soc_poverty_rate": 21.47,
          "hlt_stunting_prevalence": 38.27,
          "inf_safe_water_pct": 19.43,
          "inf_safe_sanitation_pct": 2.84
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3375",
        "region_name": "Kota Pekalongan",
        "composite_score": 22.0,
        "rank": 12,
        "national_rank": 281,
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
          "soc_poverty_rate": 10.43,
          "hlt_stunting_prevalence": 54.73,
          "inf_safe_water_pct": 0.32,
          "inf_safe_sanitation_pct": 11.93
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3327",
        "region_name": "Kabupaten Pemalang",
        "composite_score": 21.8,
        "rank": 13,
        "national_rank": 284,
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
          "soc_poverty_rate": 28.09,
          "hlt_stunting_prevalence": 28.19,
          "inf_safe_water_pct": 7.79,
          "inf_safe_sanitation_pct": 16.8
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3316",
        "region_name": "Kabupaten Blora",
        "composite_score": 21.7,
        "rank": 14,
        "national_rank": 285,
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
          "soc_poverty_rate": 21.35,
          "hlt_stunting_prevalence": 40.33,
          "inf_safe_water_pct": 8.33,
          "inf_safe_sanitation_pct": 7.63
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3324",
        "region_name": "Kabupaten Kendal",
        "composite_score": 21.22,
        "rank": 15,
        "national_rank": 297,
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
          "soc_poverty_rate": 15.99,
          "hlt_stunting_prevalence": 42.8,
          "inf_safe_water_pct": 0.53,
          "inf_safe_sanitation_pct": 17.37
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3317",
        "region_name": "Kabupaten Rembang",
        "composite_score": 20.01,
        "rank": 16,
        "national_rank": 321,
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
          "soc_poverty_rate": 27.32,
          "hlt_stunting_prevalence": 36.83,
          "inf_safe_water_pct": 0.81,
          "inf_safe_sanitation_pct": 3.01
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3301",
        "region_name": "Kabupaten Cilacap",
        "composite_score": 19.58,
        "rank": 17,
        "national_rank": 328,
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
          "soc_poverty_rate": 18.47,
          "hlt_stunting_prevalence": 34.77,
          "inf_safe_water_pct": 5.5,
          "inf_safe_sanitation_pct": 12.54
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3308",
        "region_name": "Kabupaten Magelang",
        "composite_score": 19.49,
        "rank": 18,
        "national_rank": 329,
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
          "soc_poverty_rate": 19.68,
          "hlt_stunting_prevalence": 28.4,
          "inf_safe_water_pct": 6.05,
          "inf_safe_sanitation_pct": 19.28
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3328",
        "region_name": "Kabupaten Tegal",
        "composite_score": 19.1,
        "rank": 19,
        "national_rank": 335,
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
          "soc_poverty_rate": 10.48,
          "hlt_stunting_prevalence": 42.59,
          "inf_safe_water_pct": 6.99,
          "inf_safe_sanitation_pct": 8.9
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3311",
        "region_name": "Kabupaten Sukoharjo",
        "composite_score": 18.74,
        "rank": 20,
        "national_rank": 343,
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
          "soc_poverty_rate": 12.12,
          "hlt_stunting_prevalence": 46.71,
          "inf_safe_water_pct": 1.69,
          "inf_safe_sanitation_pct": 3.77
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3376",
        "region_name": "Kota Tegal",
        "composite_score": 17.93,
        "rank": 21,
        "national_rank": 364,
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
          "soc_poverty_rate": 13.23,
          "hlt_stunting_prevalence": 42.59,
          "inf_safe_water_pct": 0.0,
          "inf_safe_sanitation_pct": 5.94
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3313",
        "region_name": "Kabupaten Karanganyar",
        "composite_score": 17.86,
        "rank": 22,
        "national_rank": 366,
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
          "soc_poverty_rate": 16.18,
          "hlt_stunting_prevalence": 42.39,
          "inf_safe_water_pct": 0.08,
          "inf_safe_sanitation_pct": 1.36
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3314",
        "region_name": "Kabupaten Sragen",
        "composite_score": 17.83,
        "rank": 23,
        "national_rank": 368,
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
          "soc_poverty_rate": 22.92,
          "hlt_stunting_prevalence": 34.57,
          "inf_safe_water_pct": 0.22,
          "inf_safe_sanitation_pct": 2.7
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3312",
        "region_name": "Kabupaten Wonogiri",
        "composite_score": 17.22,
        "rank": 24,
        "national_rank": 383,
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
          "soc_poverty_rate": 18.91,
          "hlt_stunting_prevalence": 36.83,
          "inf_safe_water_pct": 1.06,
          "inf_safe_sanitation_pct": 1.43
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3318",
        "region_name": "Kabupaten Pati",
        "composite_score": 16.85,
        "rank": 25,
        "national_rank": 390,
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
          "soc_poverty_rate": 15.59,
          "hlt_stunting_prevalence": 34.77,
          "inf_safe_water_pct": 1.61,
          "inf_safe_sanitation_pct": 7.11
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3320",
        "region_name": "Kabupaten Jepara",
        "composite_score": 15.09,
        "rank": 26,
        "national_rank": 428,
        "coverage_pct": 70.0,
        "components_used": [
          "inf_safe_sanitation_pct",
          "inf_safe_water_pct",
          "soc_poverty_rate"
        ],
        "missing_indicators": [
          "hlt_stunting_prevalence"
        ],
        "effective_weights_region": {
          "inf_safe_sanitation_pct": 2857,
          "inf_safe_water_pct": 2857,
          "soc_poverty_rate": 4286
        },
        "component_scores": {
          "soc_poverty_rate": 9.57,
          "hlt_stunting_prevalence": null,
          "inf_safe_water_pct": 9.86,
          "inf_safe_sanitation_pct": 28.61
        },
        "quality_flags": {
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3322",
        "region_name": "Kabupaten Semarang",
        "composite_score": 14.42,
        "rank": 27,
        "national_rank": 438,
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
          "soc_poverty_rate": 10.82,
          "hlt_stunting_prevalence": 29.01,
          "inf_safe_water_pct": 0.2,
          "inf_safe_sanitation_pct": 12.15
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3321",
        "region_name": "Kabupaten Demak",
        "composite_score": 13.24,
        "rank": 28,
        "national_rank": 461,
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
          "soc_poverty_rate": 22.06,
          "hlt_stunting_prevalence": 16.26,
          "inf_safe_water_pct": 2.67,
          "inf_safe_sanitation_pct": 6.04
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3371",
        "region_name": "Kota Magelang",
        "composite_score": 13.22,
        "rank": 29,
        "national_rank": 462,
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
          "soc_poverty_rate": 9.3,
          "hlt_stunting_prevalence": 28.4,
          "inf_safe_water_pct": 0.02,
          "inf_safe_sanitation_pct": 9.54
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3319",
        "region_name": "Kabupaten Kudus",
        "composite_score": 12.93,
        "rank": 30,
        "national_rank": 466,
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
          "soc_poverty_rate": 11.53,
          "hlt_stunting_prevalence": 29.01,
          "inf_safe_water_pct": 0.34,
          "inf_safe_sanitation_pct": 3.48
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3373",
        "region_name": "Kota Salatiga",
        "composite_score": 12.34,
        "rank": 31,
        "national_rank": 471,
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
          "soc_poverty_rate": 5.66,
          "hlt_stunting_prevalence": 31.48,
          "inf_safe_water_pct": 0.13,
          "inf_safe_sanitation_pct": 5.85
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3309",
        "region_name": "Kabupaten Boyolali",
        "composite_score": 11.47,
        "rank": 32,
        "national_rank": 477,
        "coverage_pct": 70.0,
        "components_used": [
          "inf_safe_sanitation_pct",
          "inf_safe_water_pct",
          "soc_poverty_rate"
        ],
        "missing_indicators": [
          "hlt_stunting_prevalence"
        ],
        "effective_weights_region": {
          "inf_safe_sanitation_pct": 2857,
          "inf_safe_water_pct": 2857,
          "soc_poverty_rate": 4286
        },
        "component_scores": {
          "soc_poverty_rate": 16.75,
          "hlt_stunting_prevalence": null,
          "inf_safe_water_pct": 3.88,
          "inf_safe_sanitation_pct": 11.13
        },
        "quality_flags": {
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3310",
        "region_name": "Kabupaten Klaten",
        "composite_score": 10.92,
        "rank": 33,
        "national_rank": 483,
        "coverage_pct": 70.0,
        "components_used": [
          "inf_safe_sanitation_pct",
          "inf_safe_water_pct",
          "soc_poverty_rate"
        ],
        "missing_indicators": [
          "hlt_stunting_prevalence"
        ],
        "effective_weights_region": {
          "inf_safe_sanitation_pct": 2857,
          "inf_safe_water_pct": 2857,
          "soc_poverty_rate": 4286
        },
        "component_scores": {
          "soc_poverty_rate": 22.38,
          "hlt_stunting_prevalence": null,
          "inf_safe_water_pct": 0.39,
          "inf_safe_sanitation_pct": 4.27
        },
        "quality_flags": {
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3374",
        "region_name": "Kota Semarang",
        "composite_score": 10.59,
        "rank": 34,
        "national_rank": 484,
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
          "soc_poverty_rate": 4.67,
          "hlt_stunting_prevalence": 29.01,
          "inf_safe_water_pct": 0.65,
          "inf_safe_sanitation_pct": 1.8
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
        "missing_indicators": [
          "hlt_stunting_prevalence"
        ],
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
    "unavailable_indicators": [],
    "effective_weights": {
      "soc_poverty_rate": 3000,
      "hlt_stunting_prevalence": 3000,
      "inf_safe_water_pct": 2000,
      "inf_safe_sanitation_pct": 2000
    },
    "renormalized": false,
    "insufficient_data": []
  }
}
```

### 2d. Skenario wilayah dikeluarkan — Sumatera Utara

Request:

```json
{
  "weights": {
    "dis_multihazard_index": 3500,
    "dis_flood_hazard_idx": 1500,
    "inf_asphalt_road_village_pct": 2500,
    "inf_electrification_pct": 2500
  },
  "filter_province_id": "12"
}
```

Respons production (bagian `insufficient_data`):

```json
{
  "total_regions": 32,
  "total_eligible_national": 511,
  "total_excluded": 1,
  "unavailable_indicators": ["inf_asphalt_road_village_pct"],
  "insufficient_data": [
    {
      "region_id": "1277",
      "region_name": "Kota Padangsidimpuan",
      "coverage_pct": 33.3,
      "components_used": ["inf_electrification_pct"],
      "missing_indicators": [
        "dis_multihazard_index",
        "dis_flood_hazard_idx",
        "inf_asphalt_road_village_pct"
      ],
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

Full response tersimpan di `docs/production_samples/composite_sumut_exclusion.json`.

## 3. Apakah `normalized_score` di `/indicators/{id}/values` mengikuti `higher_is_need`?

Ya. Saya hitung korelasi `raw` vs `norm` langsung dari production:

| Indikator | n | Korelasi raw–norm | Arti |
|---|---:|---:|---|
| `soc_poverty_rate` (polaritas negatif) | 514 | **+1.0000** | kemiskinan tinggi → normalized tinggi |
| `soc_hdi` (polaritas positif) | 514 | **-1.0000** | HDI tinggi → normalized rendah |

Contoh production:

```json
{
  "soc_poverty_rate_examples": [
    {
      "region_id": "9119",
      "raw": 42.56,
      "norm": 100.0
    },
    {
      "region_id": "9407",
      "raw": 39.21,
      "norm": 91.76
    },
    {
      "region_id": "9408",
      "raw": 37.29,
      "norm": 87.04
    }
  ],
  "soc_hdi_highest_raw": [
    {
      "region_id": "3471",
      "raw": 88.77,
      "norm": 0.0
    }
  ],
  "soc_hdi_lowest_raw": [
    {
      "region_id": "9508",
      "raw": 36.3,
      "norm": 100.0
    }
  ]
}
```

## 4. Rekomendasi: wilayah coverage 70–99% vs 100%

**Jangan langsung dicampur tanpa penanda.** Skor 70–99% adalah estimasi setelah bobot komponen yang hilang didistribusikan ulang. Asumsinya missing tidak berkorelasi dengan skor; semakin rendah coverage, semakin besar ketidakpastian. Skor 100% dan 70% tidak sepenuhnya setara.

Rekomendasi saya:

1. **Tier 1 — lengkap:** `coverage_pct == 100.0`. Boleh dipakai untuk headline ranking.

2. **Tier 2 — parsial:** `70.0 <= coverage_pct < 100.0`. Tetap tampilkan skor dan rank, tetapi beri badge **“Data parsial (X%)”** dan jangan klaim setara dengan Tier 1.

3. **Tier 3 — tidak diranking:** `coverage_pct < 70.0` → panel `insufficient_data`, sesuai kontrak.

Kalau frontend butuh satu daftar, urutkan semua eligible tetapi tampilkan `coverage_pct` dan kelompokkan secara visual. Jangan menyembunyikan coverage. Untuk klaim ranking resmi di kompetisi, saya sarankan headline ranking hanya dari Tier 1, dengan Tier 2 sebagai “hasil parsial”.

## 5. Apakah `quality_flags` dan `effective_weights_region` lengkap di production?

Ya. Setiap region yang diranking memiliki:

- `coverage_pct`
- `components_used`
- `missing_indicators`
- `effective_weights_region` (jumlah = 10.000 bps)
- `quality_flags` untuk setiap komponen yang dipakai
- `rank` dan `national_rank`

Contoh dari production (Surakarta):

```json
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
  "missing_indicators": [
    "hlt_stunting_prevalence"
  ],
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

Catatan: `quality_flags` hanya berisi komponen yang benar-benar dipakai. Komponen yang hilang tidak memiliki key di `quality_flags`, dan namanya ada di `missing_indicators`.

## 6. File mentah

Respons mentah juga disimpan di `docs/production_samples/`:

- `coverage.json`
- `presets.json`
- `composite_jateng.json`
- `direction_check.json`

---

**Kesimpulan:** frontend dapat mengikuti kontrak v2.1 tanpa menebak metode skoring. Satu-satunya keputusan produk yang tersisa adalah apakah Tier 2 (coverage 70–99%) ditampilkan terpisah dari Tier 1 (100%). Rekomendasi backend: **pisahkan atau tandai sebagai parsial**.
