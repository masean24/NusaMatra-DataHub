# Kontrak Tautan Sumber — Keputusan Final

Status: **implemented and live** with `reference_version=2026-11-sources-3`; pending source checks remain marked both in the matrix and in `source_verification`.

## Field dan enum

- `official_portal_url`: URL utama; boleh `null`.
- `official_url`: alias legacy untuk `/regions/{id}`; resolver mengisi nilai yang sama dengan `official_portal_url`.
- `source_link_level`: `table | dataset | publication | dashboard | portal | null`.
  - `dashboard`: halaman dashboard yang menampilkan angka tetapi bukan tabel ekspor langsung (mis. InaRISK IRBI dan NPD).
  - `portal`: hanya untuk dataset yang memang tidak punya halaman lebih spesifik; tidak dipakai untuk indikator individual.
- `source_verification`: `verified | pending | partial | problem_unresolved | not_applicable | null`.
  - `verified`: angka sudah dicocokkan dengan tabel/file/browser sumber.
  - `pending`: angka belum dicocokkan karena sumbernya dashboard, flipbook, PDF terpotong, atau tautan belum dapat dibaca.
  - `partial`: sebagian komponen/tingkat wilayah sudah tersedia atau dicocokkan, sebagian belum.
  - `problem_unresolved`: sumber yang tersedia tidak dapat memverifikasi indikator.
  - `not_applicable`: indikator internal/pensiun atau dataset referensi tanpa pemeriksaan angka.
- `verification_scope`: `all_rows | sample | province_level | not_applicable | null`.
  - `all_rows`: seluruh baris yang tersedia dicek (mis. APM 509 baris, kejadian bencana 510 wilayah).
  - `sample`: baru satu/beberapa baris contoh yang dicek; bukan seluruh baris.
  - `province_level`: pemeriksaan pada tingkat provinsi; nilai kab/kota hasil imputasi.
  - `not_applicable`: tidak ada pemeriksaan angka.
  - `null` untuk status `pending`, `partial`, atau `problem_unresolved`.
- `source_note_idn`: catatan publik bahasa Indonesia; tidak memuat angka contoh wilayah dan menyebut cakupan verifikasi bila `verified`.
- `source_note_en`: catatan publik bahasa Inggris; tidak memuat angka contoh wilayah.
- `source_link_level` harus `null` bila URL `null`.

## Cakupan overlay

Overlay berlaku pada:

- `GET /indicators` — `provenance.official_portal_url`, `provenance.dataset_id`, `source_link_level`, `source_verification`, `verification_scope`, `source_note_idn`, `source_note_en`.
- `GET /indicators/{id}/values` — `values_by_region.dataset_id` untuk koreksi yang disetujui.
- `GET /regions` dan `GET /regions/{id}` — `provenance.official_url`, `provenance.official_portal_url`, `source_verification`, `verification_scope`.
- `GET /datasets` — URL, `source_verification`, `verification_scope`, dan metadata tautan dataset.

Tidak ada endpoint detail `GET /indicators/{id}`. Rute indikator yang tersedia adalah
`GET /indicators` (katalog), `GET /indicators/{id}/values`, dan `GET /indicators/coverage`.

Resolver precedence: registry indikator → registry dataset → nilai database.

## Digest dan versi referensi

- `dim_datasets`, `dim_indicators`, `dim_regions`, `fact_indicator_values`, dan `content_sha256` **tidak diubah** oleh overlay.
- Field hasil overlay adalah **reference metadata di luar digest**.
- Setiap respons yang memakai overlay menambahkan `meta.reference_version`, misalnya `2026-11-sources-3`.
- FE menyimpan `content_sha256` + `reference_version` di Paspor dan JSON.
- Snapshot lama dan baru dapat menampilkan tautan hasil overlay yang sama; digest tetap membuktikan isi observasi aslinya.

## Koreksi dataset yang disetujui

- `edu_mean_years_schooling`, `edu_expected_years_schooling`, `soc_expenditure_per_capita`
  → `bps_ipm_2025`; overlay harus mengubah provenance **dan** `values_by_region.dataset_id`.
- `inf_electrification_pct` **tidak dikoreksi**. Dataset tetap `bps_susenas_sakernas_2025`; `source_record_ref` adalah `BPS Susenas Prov 2025`, dan file ingest `bps_provincial_sdgs_2025.csv` juga menyebut Susenas 2025. Catatan sumber menjelaskan ketidakpastian.
- `inf_safe_water_pct`: provenance indikator `bps_sdgs_kabkota_2025`; 513 baris memakai dataset tersebut. Baris `9507` Lanny Jaya adalah pengecualian `IMPUTED_PROVINCE` dengan dataset `bps_provincial_sdgs_2025`, nilai `32.89`, source ref `BPS Susenas 2025 Provinsi PAPUA PEGUNUNGAN (legacy BPS 9700)`. Pengecualian ini harus lulus tes kontrak.
- `inf_safe_water_pct` dan `inf_safe_sanitation_pct` memakai level `publication`, bukan `table`, selama URL yang tersedia baru memuat tingkat provinsi dan belum memuat rincian kab/kota.

## Dataset yang dipecah / null

- `bps_susenas_sakernas_2025` menggabungkan Susenas dan Sakernas. URL dataset dikosongkan sampai dataset dipecah.
- `nusa_matra_internal_audit` dan dua indikator NUSAMATRA memakai URL `null`; catatan menyebut hasil hitungan internal.

## Tes kontrak

1. `content_sha256` kelima snapshot tidak berubah setelah overlay:
   - `2026.10.0-live-b5ae83b957f0c660`
   - `2026.10.0-live-dc8fb17d066089f8`
   - `2026.10.0-live-697986eb475b2b3e`
   - `2026.10.0-live-0de6ac68f0d55b3a`
   - `2026.10.0-live-62354dfad392d985`
2. Untuk setiap indikator, `provenance.dataset_id` = dataset fakta, kecuali:
   - `inf_safe_water_pct` baris `9507` (`bps_provincial_sdgs_2025`).
   - Indikator yang memang tidak punya dataset fakta/URL.
3. `official_url` dan `official_portal_url` selalu sama bila tidak `null`.
4. `source_link_level` hanya dari enum di atas; URL air/sanitasi bukan `table`.
5. `source_verification` hanya dari enum di atas dan tidak boleh `verified` untuk baris yang masih `pending`/`partial`.
6. Setiap `verified` punya `verification_scope`; `sample` tidak boleh berarti seluruh baris.
7. `source_note_idn`/`source_note_en` tidak memuat angka contoh wilayah; contoh verifikasi hanya ada di `docs/audit`.
8. `meta.reference_version` ada pada respons yang memakai overlay dan tidak mengubah `meta.content_sha256`.
9. `9507` tetap `raw=32.89`, flag `IMPUTED_PROVINCE`, dataset `bps_provincial_sdgs_2025`; angka contoh ini hanya untuk tes, bukan catatan publik.
