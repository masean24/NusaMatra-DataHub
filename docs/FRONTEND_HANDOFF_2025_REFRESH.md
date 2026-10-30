# Handoff FE — Refresh Data 2025

## Snapshot aktif

```text
2026.10.0-live-697986eb475b2b3e
```

Snapshot lama tetap immutable dan masih bisa diakses lewat `snapshot_id` lama. Hanya snapshot ini yang menjadi `is_active_default`.

## Ringkasan perubahan

| Indikator | Tahun | Coverage | Dataset |
|---|---:|---:|---|
| `soc_hdi` | 2025 | 514/514 | `bps_ipm_2025` |
| `hlt_life_expectancy` | 2025 | 514/514 | `bps_ipm_2025` |
| `dis_multihazard_index` | 2025 | 514/514 | `bnpb_irbi_2025` |
| `dis_earthquake_hazard_idx` | 2025 | 514/514 | `bnpb_irbi_2025` |
| `dis_flood_hazard_idx` | 2025 | 510/514 | `bnpb_irbi_2025` |
| `dis_affected_pop_per_10k` | 2025 | 514/514 | `bnpb_dibi_affected_2025` |
| `edu_student_teacher_ratio_sd` | 2025 | 514/514 | `kemendikdasmen_npd_2025` |
| `edu_damaged_classrooms_pct` | 2025 | 514/514 | `kemendikdasmen_statistik_2025` |
| `hlt_stunting_prevalence` | 2024 | 514/514 | `kemenkes_ssgi_2024` |
| `dis_landslide_hazard_idx` | 2024 | 510/514 | `bnpb_irbi_2024` |
| `dis_events_5yr_freq` | 2024 | 510/514 | `bnpb_dibi_kabkota_2024` |
| `inf_internet_household_pct` | 2024 | 514/514 | `bps_susenas_tik_2024` |

## Catatan penting

1. `dis_affected_pop_per_10k` tetap `IMPUTED_PROVINCE`: BNPB 2025 hanya menerbitkan angka provinsi, lalu disalin ke kab/kota.
2. `dis_events_5yr_freq` tetap 2024 karena BNPB 2025 hanya menerbitkan agregat provinsi, bukan tabel kab/kota.
3. `dis_landslide_hazard_idx` tetap 2024 karena coverage 2025 hanya 455/514, lebih rendah dari 510/514.
4. `dis_flood_hazard_idx` 2025 punya 4 wilayah null—jangan diubah menjadi 0:
   - `3101` Kepulauan Seribu
   - `5106` Bangli
   - `7109` Kep. Siau Tagulandang Biaro
   - `8271` Kota Ternate
5. Label/unit IRBI berubah:
   - “Indeks Bahaya …” → “Indeks Risiko Bencana … (IRBI)”
   - multi-hazard: score `0–300`
   - gempa/banjir/longsor: score `0–100`
6. Label `edu_student_teacher_ratio_sd` tetap “Rasio Murid terhadap Guru”; hanya tahun dan nilainya yang berubah.
7. Response API **tidak berubah bentuknya**. Perubahan ada di values, reference year, metadata label/unit, provenance, dan ranking.
8. Mode **DEMO tidak berubah**.

## Yang perlu dilakukan di FE

1. Jangan hardcode snapshot. Ambil `active_snapshot` dari:
   - `GET /api/v1/health?mode=live`
   - atau `GET /api/v1/snapshots`
2. Clear cache nilai, ranking, dan composite score.
3. Ambil label/unit dari metadata API; jangan hardcode label IRBI lama.
4. Jangan hardcode coverage, top 5, atau ranking komposit—ranking berubah.
5. Tampilkan tahun per indikator; jangan asumsikan semua indikator 2025.
6. Tampilkan badge/flag `IMPUTED_PROVINCE` untuk `dis_affected_pop_per_10k`, `inf_internet_household_pct`, dan indikator imputasi lain yang sudah ada.
7. Untuk 4 wilayah banjir null, tampilkan “tidak tersedia”; jangan coercing ke nol.
8. Endpoint health punya `Cache-Control: max-age=3600`; saat verifikasi deploy, bypass cache.

## Copy-paste untuk teman FE

```text
Backend Nusa Matra sudah update beberapa seri data ke 2025.
Snapshot aktif:
2026.10.0-live-697986eb475b2b3e

Ambil snapshot dari GET /api/v1/health?mode=live
(field active_snapshot), jangan hardcode snapshot lama.

Yang berubah:
- IPM & UHH: 2025, 514/514 (dataset bps_ipm_2025)
- IRBI 2025:
  * dis_multihazard_index 514/514
  * dis_earthquake_hazard_idx 514/514
  * dis_flood_hazard_idx 510/514 (sebelumnya 396)
- dis_affected_pop_per_10k: 2025, 514/514, masih IMPUTED_PROVINCE
- Pendidikan 2025:
  * edu_student_teacher_ratio_sd (NPD 2025)
  * edu_damaged_classrooms_pct (Kemendikdasmen 2025)
- Stunting tetap SSGI 2024, 514/514
- Longsor tetap 2024, 510/514
- Events tetap 2024, 510/514

Yang perlu dilakukan:
1. Jangan hardcode snapshot; baca active_snapshot dari health.
2. Clear cache nilai, ranking, dan composite.
3. Update label/unit dari metadata API:
   - "Indeks Bahaya" -> "Indeks Risiko Bencana (IRBI)"
   - multi-hazard: score 0-300
   - gempa/banjir/longsor: score 0-100
4. Jangan hardcode coverage/top 5/ranking.
5. Banjir 2025 punya 4 wilayah null pada banjir:
   3101, 5106, 7109, 8271
   Jangan diubah jadi 0.
6. Tampilkan tahun per indikator.
7. Response API tidak berubah bentuknya. DEMO tidak berubah.

Catatan: health punya cache max-age 3600; bypass cache saat verifikasi deploy.
```
