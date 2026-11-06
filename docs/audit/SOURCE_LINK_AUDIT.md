# Audit Tautan Sumber Indikator

Status: **matrix untuk review**. API/overlay belum diubah. Keputusan kontrak ada di `SOURCE_LINK_CONTRACT.md`.

## Ringkasan

- Cakupan: 29 indikator publik, 24 dataset.
- Matrix indikator: `docs/audit/SOURCE_LINK_AUDIT.csv`
- Matrix dataset: `docs/audit/DATASET_LINK_AUDIT.csv`
- Nilai sampel: `3201` / Kabupaten Bogor; 26/27 indikator non-internal cocok dengan file ingest setelah koreksi crosswalk longsor.
- `inf_safe_water_pct` punya satu pengecualian: `9507` Lanny Jaya, `32.89`, `IMPUTED_PROVINCE`, dataset `bps_provincial_sdgs_2025`; 513 baris lainnya `bps_sdgs_kabkota_2025`.
- Verifikasi browser ke halaman penerbit **belum selesai**; BPS memblokir/timeout pada request otomatis, jadi kolom `external_check` masih `pending_browser`.

## Temuan crosswalk nilai

`dis_landslide_hazard_idx` sudah diperbaiki lewat snapshot baru `2026.10.0-live-b5ae83b957f0c660`: 26 pasangan Kabupaten/Kota yang namanya sama sebelumnya menerima nilai dari baris yang salah. Sekarang join memakai provinsi + level + nama. Rincian 26 nilai, arah koreksi, dan 357 pergeseran peringkat ada di `LANDSLIDE_CROSSWALK_CORRECTIONS.md`. Catatan: `9671` di CSV sudah benar **Kota Sorong**.

## Temuan mapping dataset

Mapping `provenance.dataset_id` yang perlu dikoreksi lewat overlay:

| Indikator | Dataset lama | Dataset baru |
|---|---|---|
| `edu_expected_years_schooling` | `bps_susenas_sakernas_2025` | `bps_ipm_2025` |
| `edu_mean_years_schooling` | `bps_susenas_sakernas_2025` | `bps_ipm_2025` |
| `soc_expenditure_per_capita` | `bps_susenas_sakernas_2025` | `bps_ipm_2025` |
| `edu_net_enrollment_smp` | `kemendikdasmen_ref_2026` | `kemendikdasmen_apm_2024_2025` |
| `edu_net_enrollment_sma` | `kemendikdasmen_ref_2026` | `kemendikdasmen_apm_2024_2025` |
| `hlt_jkn_coverage_pct` | `kemenkes_ski_2023` | `bps_susenas_jkn_2025` |
| `inf_internet_household_pct` | `bps_susenas_sakernas_2025` | `bps_susenas_tik_2024` |
| `inf_safe_sanitation_pct` | `bps_susenas_sakernas_2025` | `bps_sdgs_kabkota_2025` |
| `inf_safe_water_pct` | `bps_susenas_sakernas_2025` | `bps_sdgs_kabkota_2025` |
| `soc_dependency_ratio` | `bps_susenas_sakernas_2025` | `bps_proyeksi_penduduk_2026` |

`inf_electrification_pct` **tidak dikoreksi**: `source_record_ref` adalah `BPS Susenas Prov 2025`, dan file ingest `bps_provincial_sdgs_2025.csv` juga menyebut Susenas 2025. Dataset lama dipertahankan dan ketidakpastian ditulis di `source_note`.

RLS, HLS, dan pengeluaran berasal dari dokumentasi internal yang menyebut sumbernya BPS IPM, bukan Susenas. Overlay harus mengubah provenance **dan** `values_by_region.dataset_id`.

## Keputusan kontrak yang diusulkan

### URL dan alias

- `official_portal_url` adalah field utama.
- `official_url` di `/regions/{id}` dipertahankan sebagai **alias legacy** dan selalu diisi nilai yang sama dengan `official_portal_url` oleh resolver yang sama.
- FE tidak perlu mengubah urutan fallback.
- `null` berarti tidak ada tautan yang layak; FE menyembunyikan tautan atau menampilkan “Tautan sumber belum tersedia”.

### `source_link_level`

Enum: `table` | `dataset` | `publication` | `dashboard` | `portal` | `null`.

- `table`: halaman tabel statistik langsung.
- `dataset`: halaman dataset/resource (CKAN, SATUSEHAT, layanan BIG).
- `publication`: publikasi/PDF yang memuat angka.
- `dashboard`: dashboard yang menampilkan angka tetapi bukan tabel ekspor langsung (IRBI, NPD).
- `portal`: hanya dipakai untuk dataset yang memang tidak punya halaman lebih spesifik; tidak dipakai untuk indikator individual.
- `null` jika URL `null`.

### `source_note`

Disediakan dua field opsional:

- `source_note_idn`: bahasa Indonesia.
- `source_note_en`: bahasa Inggris.

Keduanya boleh `null`. FE dapat memakai `source_note_idn`/`source_note_en` sesuai locale.

### Batas digest

- `content_sha256` tetap dihitung dari data warehouse asli: observasi, scoring, metadata indikator, dan metadata dataset yang tersimpan.
- URL, `source_link_level`, `source_note_*`, dan **resolved `provenance.dataset_id`** adalah **reference overlay di luar digest**.
- `values_by_region.dataset_id` juga di-overlay untuk koreksi yang disetujui; provenance dan dataset fakta harus sama.
- `meta.reference_version` (mis. `2026-11-sources-1`) ditambahkan ke respons yang memakai overlay. FE menyimpan `content_sha256` + `reference_version`.
- Pengecualian air: `9507` tetap memakai dataset fakta `bps_provincial_sdgs_2025`, sementara provenance indikator `bps_sdgs_kabkota_2025`.

### Fallback dataset

- Untuk indikator NUSAMATRA, URL indikator **dan** URL dataset `nusa_matra_internal_audit` sama-sama `null`; catatan menyebut hasil hitungan internal.
- Untuk indikator lain yang URL-nya `null`, URL dataset tidak boleh berupa portal umum. Jika dataset juga tidak punya tautan layak, dataset tersebut juga `null`.
- `bps_susenas_sakernas_2025` menggabungkan Susenas dan Sakernas. URL dataset dikosongkan sampai dataset dipecah; jangan memakai publikasi Susenas sebagai fallback Sakernas.

## Sisa pekerjaan

1. Verifikasi browser untuk setiap URL (BPS sering timeout untuk request otomatis).
2. Cocokkan satu nilai wilayah di halaman penerbit, bukan hanya file ingest.
3. Review matrix, lalu implement overlay dan field opsional.
4. Test kontrak dan pastikan `meta.content_sha256` tidak berubah.
